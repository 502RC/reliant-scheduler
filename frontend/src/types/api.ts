/** TypeScript types matching backend Pydantic schemas */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ── Jobs ──

export type JobStatus = "active" | "inactive" | "paused";

export interface JobCreate {
  name: string;
  description?: string | null;
  job_type: string;
  command?: string | null;
  parameters?: Record<string, unknown> | null;
  connection_id?: string | null;
  environment_id?: string | null;
  max_retries?: number;
  timeout_seconds?: number;
  tags?: Record<string, string> | null;
}

export type JobUpdate = Partial<JobCreate>;

export interface JobResponse {
  id: string;
  name: string;
  description: string | null;
  status: string;
  job_type: string;
  command: string | null;
  parameters: Record<string, unknown> | null;
  connection_id: string | null;
  environment_id: string | null;
  max_retries: number;
  timeout_seconds: number;
  tags: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

// ── Job Runs ──

export type RunStatus =
  | "pending"
  | "queued"
  | "running"
  | "success"
  | "failed"
  | "cancelled"
  | "timed_out";

export interface JobRunResponse {
  id: string;
  job_id: string;
  agent_id: string | null;
  status: RunStatus;
  triggered_by: "schedule" | "manual";
  parameters: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  error_message: string | null;
  log_url: string | null;
  metrics: Record<string, unknown> | null;
  attempt_number: number;
  created_at: string;
  updated_at: string;
}

// ── Job Dependencies ──

export interface JobDependencyResponse {
  id: string;
  dependent_job_id: string;
  depends_on_job_id: string;
}

export interface JobDependencyCreate {
  depends_on_job_id: string;
  condition?: string;
}

// ── Schedules ──

export type TriggerType = "cron" | "event" | "dependency" | "manual";

export interface ScheduleCreate {
  job_id: string;
  trigger_type: TriggerType;
  cron_expression?: string | null;
  timezone?: string;
  event_source?: string | null;
  event_filter?: Record<string, unknown> | null;
  enabled?: boolean;
}

export type ScheduleUpdate = Partial<Omit<ScheduleCreate, "job_id">>;

export interface ScheduleResponse {
  id: string;
  job_id: string;
  trigger_type: TriggerType;
  cron_expression: string | null;
  timezone: string;
  event_source: string | null;
  event_filter: Record<string, unknown> | null;
  enabled: boolean;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

// ── Environments ──

export interface EnvironmentCreate {
  name: string;
  description?: string | null;
  variables?: Record<string, string> | null;
  is_production?: boolean;
}

export type EnvironmentUpdate = Partial<EnvironmentCreate>;

export interface EnvironmentResponse {
  id: string;
  name: string;
  description: string | null;
  variables: Record<string, string> | null;
  is_production: boolean;
  created_at: string;
  updated_at: string;
}

// ── Connections ──

export type ConnectionType =
  | "ssh"
  | "database"
  | "rest_api"
  | "sftp"
  | "azure_blob"
  | "azure_servicebus"
  | "azure_eventhub"
  | "winrm"
  | "custom";

export interface ConnectionCreate {
  name: string;
  connection_type: ConnectionType;
  host?: string | null;
  port?: number | null;
  description?: string | null;
  extra?: Record<string, unknown> | null;
  credential_id?: string | null;
}

export type ConnectionUpdate = Partial<ConnectionCreate>;

export interface ConnectionResponse {
  id: string;
  name: string;
  connection_type: string;
  host: string | null;
  port: number | null;
  description: string | null;
  extra: Record<string, unknown> | null;
  credential_id: string | null;
  created_at: string;
  updated_at: string;
}

// ── Credentials ──

export type CredentialType =
  | "windows_ad"
  | "ssh_password"
  | "ssh_private_key"
  | "api_key"
  | "api_key_secret"
  | "bearer_token"
  | "oauth2_client"
  | "database"
  | "smtp"
  | "azure_service_principal"
  | "certificate"
  | "custom";

export interface CredentialFieldDefinition {
  name: string;
  label: string;
  field_type: "string" | "password" | "textarea" | "number" | "boolean" | "select";
  required: boolean;
  is_secret: boolean;
  default?: string | null;
  placeholder?: string | null;
  options?: { value: string; label: string }[] | null;
}

export interface CredentialTemplate {
  type_key: CredentialType;
  display_name: string;
  description: string;
  fields: CredentialFieldDefinition[];
}

export interface CredentialCreate {
  name: string;
  credential_type: CredentialType;
  description?: string | null;
  fields: Record<string, string | number | boolean>;
}

export type CredentialUpdate = Partial<CredentialCreate>;

export interface CredentialResponse {
  id: string;
  name: string;
  credential_type: string;
  description: string | null;
  fields: Record<string, unknown> | null;
  secret_fields: string[];
  usage_count: number;
  created_at: string;
  updated_at: string;
}

// ── Agents ──

export type AgentStatus = "online" | "offline" | "draining";

export interface AgentResponse {
  id: string;
  hostname: string;
  status: AgentStatus;
  labels: Record<string, string> | null;
  max_concurrent_jobs: number;
  last_heartbeat_at: string | null;
  agent_version: string | null;
  created_at: string;
  updated_at: string;
}

// ── Auth / RBAC ──

export type UserRole =
  | "admin"
  | "scheduler_admin"
  | "scheduler"
  | "operator"
  | "user"
  | "inquiry";

export interface UserProfile {
  id: string;
  displayName: string;
  email: string;
  role: UserRole;
  lastLogin: string | null;
}

/** Response from GET /api/auth/me — matches backend AuthMeResponse */
export interface UserMeResponse {
  user: UserResponse_Admin;
  permissions: string[];
}

/** Admin-facing user record from the backend */
export interface UserResponse_Admin {
  id: string;
  entra_object_id: string | null;
  email: string;
  display_name: string;
  role: string;
  status: "active" | "disabled";
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserPermission {
  permission_key: string;
  scope: "global" | "workgroup" | "object";
  effect: "allow" | "deny";
}

/** Resolved permission for frontend use. Maps resource:action pairs. */
export type PermissionCheck = `${string}:${string}`;

// ── Users (admin) ──

export interface UserCreate_Admin {
  email: string;
  display_name: string;
  role?: string;
  entra_object_id?: string | null;
}

export interface UserUpdate_Admin {
  display_name?: string;
  role?: string;
  status?: string;
}

// ── Workgroups ──

export interface WorkgroupCreate {
  name: string;
  description?: string | null;
}

export type WorkgroupUpdate = Partial<WorkgroupCreate>;

export interface WorkgroupResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkgroupMemberAdd {
  user_id: string;
  role?: string;
}

export interface WorkgroupMemberResponse {
  id: string;
  user_id: string;
  workgroup_id: string;
  role: string;
}

// ── Security Policies ──

export type SecurityResourceType =
  | "job"
  | "schedule"
  | "connection"
  | "calendar"
  | "environment";

export type SecurityPermission = "read" | "write" | "execute" | "admin";

export interface SecurityPolicyCreate {
  name: string;
  resource_type: SecurityResourceType;
  resource_id?: string | null;
  principal_type: "user" | "workgroup";
  principal_id: string;
  permission: SecurityPermission;
}

export interface SecurityPolicyResponse {
  id: string;
  name: string;
  resource_type: string;
  resource_id: string | null;
  principal_type: string;
  principal_id: string;
  permission: string;
  created_at: string;
  updated_at: string;
}

// ── Audit Log ──

export interface AuditLogResponse {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details_json: Record<string, unknown> | null;
  ip_address: string | null;
  correlation_id: string | null;
  timestamp: string;
}

// ── Calendars ──

export type CalendarType = "business" | "financial" | "holiday" | "custom";

export interface CalendarCreate {
  name: string;
  calendar_type: CalendarType;
  timezone?: string;
  description?: string | null;
}

export type CalendarUpdate = Partial<CalendarCreate>;

export interface CalendarResponse {
  id: string;
  name: string;
  calendar_type: CalendarType;
  timezone: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarDateEntry {
  id: string;
  calendar_id: string;
  date: string;
  label: string | null;
  is_business_day: boolean;
}

export interface CalendarRule {
  id: string;
  calendar_id: string;
  rule_type: string;
  description: string | null;
  config: Record<string, unknown>;
}

// ── SLA Policies ──

export type SlaStatus = "on_track" | "at_risk" | "breached" | "met";

export interface SlaPolicyCreate {
  name: string;
  target_completion_time: string;
  risk_window_minutes: number;
  breach_window_minutes: number;
  description?: string | null;
}

export type SlaPolicyUpdate = Partial<SlaPolicyCreate>;

export interface SlaPolicyResponse {
  id: string;
  name: string;
  description: string | null;
  target_completion_time: string;
  risk_window_minutes: number;
  breach_window_minutes: number;
  status: SlaStatus;
  compliance_rate: number | null;
  created_at: string;
  updated_at: string;
}

export interface SlaConstraintCreate {
  job_id: string;
  track_critical_path?: boolean;
}

export interface SlaConstraintResponse {
  id: string;
  sla_policy_id: string;
  job_id: string;
  track_critical_path: boolean;
}

export interface SlaEventResponse {
  id: string;
  sla_policy_id: string;
  event_type: SlaStatus;
  message: string | null;
  timestamp: string;
}

// ── Dashboard ──

export interface DashboardSummary {
  total_jobs: number;
  active_runs: number;
  agents_online: number;
  agents_total: number;
  recent_failures: number;
  waiting_jobs: number;
}

// ── WebSocket Events ──

export type WsEventType =
  | "job.status_changed"
  | "job.started"
  | "job.completed"
  | "job.failed"
  | "job.timed_out"
  | "agent.status_changed"
  | "sla.at_risk"
  | "sla.breached"
  | "sla.met"
  | "system.info";

export interface WsEvent {
  type: WsEventType;
  timestamp: string;
  payload: WsJobStatusPayload | WsAgentStatusPayload | WsSlaPayload | WsSystemPayload;
}

export interface WsJobStatusPayload {
  job_id: string;
  job_name: string;
  run_id: string;
  previous_status: RunStatus | null;
  status: RunStatus;
  agent_id?: string | null;
  exit_code?: number | null;
  error_message?: string | null;
}

export interface WsAgentStatusPayload {
  agent_id: string;
  hostname: string;
  previous_status: AgentStatus;
  status: AgentStatus;
}

export interface WsSlaPayload {
  sla_policy_id: string;
  sla_policy_name: string;
  status: SlaStatus;
  message?: string | null;
}

export interface WsSystemPayload {
  message: string;
  severity: "info" | "warning" | "error";
}

// ── Notifications ──

export type NotificationSeverity = "info" | "warning" | "error" | "success";

export interface AppNotification {
  id: string;
  type: WsEventType;
  title: string;
  message: string;
  severity: NotificationSeverity;
  timestamp: string;
  read: boolean;
  linkTo?: string;
}

// ── WebSocket Connection ──

export type WsConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

// ── Events & Actions (Event-Action Framework) ──

export type EventDefinitionType = "file_arrival" | "database_change" | "sla_event" | "system_event" | "job_event";

export interface EventDefinitionCreate {
  name: string;
  event_type: EventDefinitionType;
  definition: Record<string, unknown>;
  enabled?: boolean;
}

export type EventDefinitionUpdate = Partial<EventDefinitionCreate>;

export interface EventDefinitionResponse {
  id: string;
  name: string;
  event_type: EventDefinitionType;
  definition: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export type ActionType = "email" | "webhook" | "slack" | "teams" | "itsm";

export interface ActionCreate {
  name: string;
  action_type: ActionType;
  definition: Record<string, unknown>;
}

export type ActionUpdate = Partial<ActionCreate>;

export interface ActionResponse {
  id: string;
  name: string;
  action_type: ActionType;
  definition: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EventActionBindingCreate {
  event_id: string;
  action_id: string;
  order?: number;
  active?: boolean;
  filters?: Record<string, unknown> | null;
}

export type EventActionBindingUpdate = Partial<Omit<EventActionBindingCreate, "event_id" | "action_id">>;

export interface EventActionBindingResponse {
  id: string;
  event_id: string;
  action_id: string;
  order: number;
  active: boolean;
  filters: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ActionExecutionResponse {
  id: string;
  action_id: string;
  event_id: string;
  status: "success" | "failed" | "pending";
  triggered_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface ActionTestResult {
  success: boolean;
  message: string;
  response_time_ms: number;
}
