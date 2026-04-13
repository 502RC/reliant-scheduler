"""Action executor — dispatches actions to the appropriate handler.

Supports: email, webhook, Slack, Teams, ITSM incident, and recovery job.
Each handler receives the action config and event data, and returns
a (success: bool, error_message: str | None) tuple.
"""

import hashlib
import hmac
import json
from string import Template
from typing import Any

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)

MAX_RECOVERY_DEPTH = 3


async def execute_action(
    action_type: str,
    config: dict[str, Any],
    event_data: dict[str, Any],
) -> tuple[bool, str | None]:
    """Dispatch to the appropriate action handler.

    Returns (success, error_message).
    """
    handlers = {
        "email": _handle_email,
        "webhook": _handle_webhook,
        "slack": _handle_slack,
        "teams": _handle_teams,
        "itsm_incident": _handle_itsm_incident,
        "recovery_job": _handle_recovery_job,
    }

    handler = handlers.get(action_type)
    if not handler:
        return False, f"Unknown action type: {action_type}"

    try:
        return await handler(config, event_data)
    except Exception as exc:
        logger.exception("action_execution_error", action_type=action_type)
        return False, str(exc)


def _render_template(template_str: str, event_data: dict[str, Any]) -> str:
    """Render a template string with event data using safe substitution."""
    tpl = Template(template_str.replace("{{", "${").replace("}}", "}"))
    return tpl.safe_substitute(event_data)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

async def _handle_email(config: dict, event_data: dict) -> tuple[bool, str | None]:
    """Send email via aiosmtplib.

    Config keys: to_addresses, subject_template, body_template,
    smtp_host (optional), smtp_port (optional).
    """
    to_addresses = config.get("to_addresses", [])
    subject_template = config.get("subject_template", "Reliant Scheduler Alert")
    body_template = config.get("body_template", "Event: ${event_type}")

    if not to_addresses:
        return False, "No recipients configured"

    subject = _render_template(subject_template, event_data)
    body = _render_template(body_template, event_data)

    try:
        import aiosmtplib
        smtp_host = config.get("smtp_host", "localhost")
        smtp_port = config.get("smtp_port", 587)
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = config.get("from_address", "reliant-scheduler@noreply.local")
        msg["To"] = ", ".join(to_addresses)
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            start_tls=True,
        )
        logger.info("email_sent", to=to_addresses, subject=subject)
        return True, None
    except ImportError:
        logger.warning("aiosmtplib_not_installed")
        return False, "aiosmtplib is not installed"
    except Exception as exc:
        return False, f"SMTP error: {exc}"


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

async def _handle_webhook(config: dict, event_data: dict) -> tuple[bool, str | None]:
    """HTTP POST to a configured URL with optional HMAC signature.

    Config keys: url, headers (optional), body_template (optional),
    hmac_secret (optional).
    """
    url = config.get("url")
    if not url:
        return False, "No webhook URL configured"

    headers = dict(config.get("headers", {}))
    headers.setdefault("Content-Type", "application/json")

    body_template = config.get("body_template")
    if body_template:
        body = _render_template(body_template, event_data)
    else:
        body = json.dumps(event_data)

    hmac_secret = config.get("hmac_secret")
    if hmac_secret:
        sig = hmac.new(hmac_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Signature-SHA256"] = sig

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, content=body, headers=headers)
            if resp.status_code >= 400:
                return False, f"Webhook returned {resp.status_code}: {resp.text[:200]}"
        logger.info("webhook_sent", url=url, status=resp.status_code)
        return True, None
    except ImportError:
        logger.warning("httpx_not_installed")
        return False, "httpx is not installed"
    except Exception as exc:
        return False, f"Webhook error: {exc}"


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

async def _handle_slack(config: dict, event_data: dict) -> tuple[bool, str | None]:
    """Send Slack notification via incoming webhook.

    Config keys: webhook_url, channel (optional), message_template.
    """
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return False, "No Slack webhook URL configured"

    message_template = config.get("message_template", "Reliant Scheduler: ${event_type}")
    text = _render_template(message_template, event_data)

    payload: dict[str, Any] = {"text": text}
    if config.get("channel"):
        payload["channel"] = config["channel"]

    # Support Slack Block Kit if blocks_template is provided
    blocks_template = config.get("blocks_template")
    if blocks_template:
        try:
            blocks_str = _render_template(json.dumps(blocks_template), event_data)
            payload["blocks"] = json.loads(blocks_str)
        except (json.JSONDecodeError, TypeError):
            pass  # fall back to text

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code >= 400:
                return False, f"Slack returned {resp.status_code}: {resp.text[:200]}"
        logger.info("slack_notification_sent")
        return True, None
    except ImportError:
        return False, "httpx is not installed"
    except Exception as exc:
        return False, f"Slack error: {exc}"


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

async def _handle_teams(config: dict, event_data: dict) -> tuple[bool, str | None]:
    """Send Microsoft Teams notification via incoming webhook.

    Config keys: webhook_url, message_template.
    """
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return False, "No Teams webhook URL configured"

    message_template = config.get("message_template", "Reliant Scheduler: ${event_type}")
    text = _render_template(message_template, event_data)

    # Adaptive Card format
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": text, "wrap": True},
                    ],
                },
            }
        ],
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code >= 400:
                return False, f"Teams returned {resp.status_code}: {resp.text[:200]}"
        logger.info("teams_notification_sent")
        return True, None
    except ImportError:
        return False, "httpx is not installed"
    except Exception as exc:
        return False, f"Teams error: {exc}"


# ---------------------------------------------------------------------------
# ITSM Incident
# ---------------------------------------------------------------------------

async def _handle_itsm_incident(config: dict, event_data: dict) -> tuple[bool, str | None]:
    """Create an ITSM incident via REST API (ServiceNow/PagerDuty/Opsgenie).

    Config keys: endpoint, auth_type (api_key|oauth), auth_value,
    payload_template.
    """
    endpoint = config.get("endpoint")
    if not endpoint:
        return False, "No ITSM endpoint configured"

    auth_type = config.get("auth_type", "api_key")
    auth_value = config.get("auth_value", "")

    payload_template = config.get("payload_template")
    if payload_template:
        body = _render_template(json.dumps(payload_template), event_data)
    else:
        body = json.dumps({
            "short_description": f"Reliant Scheduler: {event_data.get('event_type', 'unknown')}",
            "description": json.dumps(event_data, default=str),
            "urgency": "2",
            "impact": "2",
        })

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if auth_type == "api_key":
        headers["Authorization"] = f"Bearer {auth_value}"
    elif auth_type == "oauth":
        headers["Authorization"] = f"Bearer {auth_value}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, content=body, headers=headers)
            if resp.status_code >= 400:
                return False, f"ITSM returned {resp.status_code}: {resp.text[:200]}"
        logger.info("itsm_incident_created", endpoint=endpoint)
        return True, None
    except ImportError:
        return False, "httpx is not installed"
    except Exception as exc:
        return False, f"ITSM error: {exc}"


# ---------------------------------------------------------------------------
# Recovery Job
# ---------------------------------------------------------------------------

async def _handle_recovery_job(config: dict, event_data: dict) -> tuple[bool, str | None]:
    """Trigger a recovery job on failure.

    Config keys: recovery_job_id, pass_context (bool).
    Prevents infinite loops via max_recovery_depth check.
    """
    recovery_job_id = config.get("recovery_job_id")
    if not recovery_job_id:
        return False, "No recovery_job_id configured"

    current_depth = event_data.get("recovery_depth", 0)
    if current_depth >= MAX_RECOVERY_DEPTH:
        logger.warning(
            "recovery_depth_exceeded",
            recovery_job_id=recovery_job_id,
            depth=current_depth,
        )
        return False, f"Max recovery depth ({MAX_RECOVERY_DEPTH}) exceeded"

    # Recovery jobs are created by the event router via the scheduler.
    # We signal success here — the actual job creation is handled by the
    # router which has DB access.
    logger.info(
        "recovery_job_triggered",
        recovery_job_id=recovery_job_id,
        pass_context=config.get("pass_context", False),
        depth=current_depth + 1,
    )
    return True, None
