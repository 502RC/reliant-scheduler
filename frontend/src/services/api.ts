import { acquireAccessToken, loginRedirect, AUTH_DISABLED } from "@/services/auth";
import type {
  PaginatedResponse,
  JobResponse,
  JobCreate,
  JobUpdate,
  JobRunResponse,
  JobDependencyResponse,
  JobDependencyCreate,
  ScheduleResponse,
  ScheduleCreate,
  ScheduleUpdate,
  AgentResponse,
  EnvironmentResponse,
  EnvironmentCreate,
  EnvironmentUpdate,
  ConnectionResponse,
  ConnectionCreate,
  ConnectionUpdate,
  CredentialResponse,
  CredentialCreate,
  CredentialUpdate,
  CredentialTemplate,
  DashboardSummary,
  UserMeResponse,
  UserResponse_Admin,
  UserCreate_Admin,
  UserUpdate_Admin,
  WorkgroupResponse,
  WorkgroupCreate,
  WorkgroupUpdate,
  WorkgroupMemberResponse,
  WorkgroupMemberAdd,
  SecurityPolicyResponse,
  SecurityPolicyCreate,
  AuditLogResponse,
  CalendarResponse,
  CalendarCreate,
  CalendarUpdate,
  CalendarDateEntry,
  CalendarRule,
  SlaPolicyResponse,
  SlaPolicyCreate,
  SlaPolicyUpdate,
  SlaConstraintResponse,
  SlaConstraintCreate,
  SlaEventResponse,
  EventDefinitionResponse,
  EventDefinitionCreate,
  EventDefinitionUpdate,
  ActionResponse,
  ActionCreate,
  ActionUpdate,
  EventActionBindingResponse,
  EventActionBindingCreate,
  EventActionBindingUpdate,
  ActionExecutionResponse,
  ActionTestResult,
} from "@/types/api";

const BASE_URL = "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retried = false
): Promise<T> {
  const token = await acquireAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && !retried && !AUTH_DISABLED) {
    // Attempt silent token refresh, then retry once
    try {
      const freshToken = await acquireAccessToken();
      if (freshToken) {
        return request<T>(path, options, true);
      }
    } catch {
      // Token refresh failed — redirect to login
    }
    await loginRedirect();
    throw new ApiError(401, "Unauthorized", "Session expired. Redirecting to login.");
  }

  if (!response.ok) {
    const text = await response.text();
    let body: unknown;
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
    throw new ApiError(response.status, response.statusText, body);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function queryString(params: Record<string, string | number | boolean | undefined>): string {
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string | number | boolean] => entry[1] !== undefined
  );
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

// ── Jobs ──

export const jobs = {
  list(page = 1, pageSize = 20, status?: string) {
    return request<PaginatedResponse<JobResponse>>(
      `/jobs${queryString({ page, page_size: pageSize, status })}`
    );
  },
  get(id: string) {
    return request<JobResponse>(`/jobs/${id}`);
  },
  create(data: JobCreate) {
    return request<JobResponse>("/jobs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: JobUpdate) {
    return request<JobResponse>(`/jobs/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/jobs/${id}`, { method: "DELETE" });
  },
  trigger(id: string) {
    return request<JobRunResponse>(`/jobs/${id}/trigger`, { method: "POST", body: JSON.stringify({}) });
  },
  runs(id: string, page = 1, pageSize = 20) {
    return request<PaginatedResponse<JobRunResponse>>(
      `/jobs/${id}/runs${queryString({ page, page_size: pageSize })}`
    );
  },
  dependencies(id: string) {
    return request<JobDependencyResponse[]>(`/jobs/${id}/dependencies`);
  },
  addDependency(id: string, data: JobDependencyCreate) {
    return request<JobDependencyResponse>(`/jobs/${id}/dependencies`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  removeDependency(jobId: string, depId: string) {
    return request<void>(`/jobs/${jobId}/dependencies/${depId}`, {
      method: "DELETE",
    });
  },
};

// ── Schedules ──

export const schedules = {
  list(page = 1, pageSize = 20) {
    return request<PaginatedResponse<ScheduleResponse>>(
      `/schedules${queryString({ page, page_size: pageSize })}`
    );
  },
  get(id: string) {
    return request<ScheduleResponse>(`/schedules/${id}`);
  },
  create(data: ScheduleCreate) {
    return request<ScheduleResponse>("/schedules", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: ScheduleUpdate) {
    return request<ScheduleResponse>(`/schedules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/schedules/${id}`, { method: "DELETE" });
  },
};

// ── Agents ──

export const agents = {
  list(page = 1, pageSize = 20, status?: string) {
    return request<PaginatedResponse<AgentResponse>>(
      `/agents${queryString({ page, page_size: pageSize, status })}`
    );
  },
  get(id: string) {
    return request<AgentResponse>(`/agents/${id}`);
  },
};

// ── Environments ──

export const environments = {
  list(page = 1, pageSize = 20, isProduction?: boolean) {
    return request<PaginatedResponse<EnvironmentResponse>>(
      `/environments${queryString({ page, page_size: pageSize, is_production: isProduction })}`
    );
  },
  get(id: string) {
    return request<EnvironmentResponse>(`/environments/${id}`);
  },
  create(data: EnvironmentCreate) {
    return request<EnvironmentResponse>("/environments", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: EnvironmentUpdate) {
    return request<EnvironmentResponse>(`/environments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/environments/${id}`, { method: "DELETE" });
  },
};

// ── Connections ──

export const connections = {
  list(page = 1, pageSize = 20, connectionType?: string) {
    return request<PaginatedResponse<ConnectionResponse>>(
      `/connections${queryString({ page, page_size: pageSize, connection_type: connectionType })}`
    );
  },
  get(id: string) {
    return request<ConnectionResponse>(`/connections/${id}`);
  },
  create(data: ConnectionCreate) {
    return request<ConnectionResponse>("/connections", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: ConnectionUpdate) {
    return request<ConnectionResponse>(`/connections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/connections/${id}`, { method: "DELETE" });
  },
};

// ── Credentials ──

export const credentials = {
  list(page = 1, pageSize = 20, credentialType?: string) {
    return request<PaginatedResponse<CredentialResponse>>(
      `/credentials${queryString({ page, page_size: pageSize, credential_type: credentialType })}`
    );
  },
  get(id: string) {
    return request<CredentialResponse>(`/credentials/${id}`);
  },
  create(data: CredentialCreate) {
    return request<CredentialResponse>("/credentials", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: CredentialUpdate) {
    return request<CredentialResponse>(`/credentials/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/credentials/${id}`, { method: "DELETE" });
  },
  templates() {
    return request<CredentialTemplate[]>("/credentials/templates");
  },
  template(type: string) {
    return request<CredentialTemplate>(`/credentials/templates/${type}`);
  },
};

// ── Dashboard ──

export const dashboard = {
  summary() {
    return request<DashboardSummary>("/dashboard/summary");
  },
};

// ── Logs ──

export const logs = {
  async fetchContent(logUrl: string): Promise<string> {
    const token = await acquireAccessToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const response = await fetch(logUrl, { headers });
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText, null);
    }
    return response.text();
  },
};

// ── Auth ──

export const auth = {
  me() {
    return request<UserMeResponse>("/auth/me");
  },
};

// ── Users (admin) ──

export const users = {
  list(page = 1, pageSize = 50, role?: string, status?: string) {
    return request<PaginatedResponse<UserResponse_Admin>>(
      `/users${queryString({ page, page_size: pageSize, role, status })}`
    );
  },
  get(id: string) {
    return request<UserResponse_Admin>(`/users/${id}`);
  },
  create(data: UserCreate_Admin) {
    return request<UserResponse_Admin>("/users", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: UserUpdate_Admin) {
    return request<UserResponse_Admin>(`/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/users/${id}`, { method: "DELETE" });
  },
};

// ── Workgroups ──

export const workgroups = {
  list(page = 1, pageSize = 50) {
    return request<PaginatedResponse<WorkgroupResponse>>(
      `/workgroups${queryString({ page, page_size: pageSize })}`
    );
  },
  get(id: string) {
    return request<WorkgroupResponse>(`/workgroups/${id}`);
  },
  create(data: WorkgroupCreate) {
    return request<WorkgroupResponse>("/workgroups", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: WorkgroupUpdate) {
    return request<WorkgroupResponse>(`/workgroups/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/workgroups/${id}`, { method: "DELETE" });
  },
  members(id: string) {
    return request<WorkgroupMemberResponse[]>(`/workgroups/${id}/members`);
  },
  addMember(id: string, data: WorkgroupMemberAdd) {
    return request<WorkgroupMemberResponse>(`/workgroups/${id}/members`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  removeMember(workgroupId: string, userId: string) {
    return request<void>(`/workgroups/${workgroupId}/members/${userId}`, {
      method: "DELETE",
    });
  },
};

// ── Security Policies ──

export const securityPolicies = {
  list(page = 1, pageSize = 50, resourceType?: string, principalType?: string) {
    return request<PaginatedResponse<SecurityPolicyResponse>>(
      `/security-policies${queryString({ page, page_size: pageSize, resource_type: resourceType, principal_type: principalType })}`
    );
  },
  get(id: string) {
    return request<SecurityPolicyResponse>(`/security-policies/${id}`);
  },
  create(data: SecurityPolicyCreate) {
    return request<SecurityPolicyResponse>("/security-policies", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/security-policies/${id}`, { method: "DELETE" });
  },
};

// ── Audit Log ──

export const auditLog = {
  list(
    page = 1,
    pageSize = 50,
    filters?: {
      user_id?: string;
      resource_type?: string;
      action?: string;
      start_date?: string;
      end_date?: string;
    }
  ) {
    return request<PaginatedResponse<AuditLogResponse>>(
      `/audit-log${queryString({ page, page_size: pageSize, ...filters })}`
    );
  },
};

// ── Calendars ──

export const calendars = {
  list(page = 1, pageSize = 20, calendarType?: string) {
    return request<PaginatedResponse<CalendarResponse>>(
      `/calendars${queryString({ page, page_size: pageSize, calendar_type: calendarType })}`
    );
  },
  get(id: string) {
    return request<CalendarResponse>(`/calendars/${id}`);
  },
  create(data: CalendarCreate) {
    return request<CalendarResponse>("/calendars", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: CalendarUpdate) {
    return request<CalendarResponse>(`/calendars/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/calendars/${id}`, { method: "DELETE" });
  },
  dates(id: string, year?: number, month?: number) {
    return request<CalendarDateEntry[]>(
      `/calendars/${id}/dates${queryString({ year, month })}`
    );
  },
  addDate(id: string, date: string, label?: string, isBusinessDay = true) {
    return request<CalendarDateEntry>(`/calendars/${id}/dates`, {
      method: "POST",
      body: JSON.stringify({ date, label, is_business_day: isBusinessDay }),
    });
  },
  removeDate(calendarId: string, dateId: string) {
    return request<void>(`/calendars/${calendarId}/dates/${dateId}`, {
      method: "DELETE",
    });
  },
  rules(id: string) {
    return request<CalendarRule[]>(`/calendars/${id}/rules`);
  },
};

// ── SLA Policies ──

export const slaPolicies = {
  list(page = 1, pageSize = 20, status?: string) {
    return request<PaginatedResponse<SlaPolicyResponse>>(
      `/sla-policies${queryString({ page, page_size: pageSize, status })}`
    );
  },
  get(id: string) {
    return request<SlaPolicyResponse>(`/sla-policies/${id}`);
  },
  create(data: SlaPolicyCreate) {
    return request<SlaPolicyResponse>("/sla-policies", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: SlaPolicyUpdate) {
    return request<SlaPolicyResponse>(`/sla-policies/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/sla-policies/${id}`, { method: "DELETE" });
  },
  constraints(id: string) {
    return request<SlaConstraintResponse[]>(`/sla-policies/${id}/constraints`);
  },
  addConstraint(id: string, data: SlaConstraintCreate) {
    return request<SlaConstraintResponse>(`/sla-policies/${id}/constraints`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  removeConstraint(policyId: string, constraintId: string) {
    return request<void>(`/sla-policies/${policyId}/constraints/${constraintId}`, {
      method: "DELETE",
    });
  },
  events(id: string, page = 1, pageSize = 50) {
    return request<PaginatedResponse<SlaEventResponse>>(
      `/sla-policies/${id}/events${queryString({ page, page_size: pageSize })}`
    );
  },
};

// ── Events (Event-Action Framework) ──

export const events = {
  list(page = 1, pageSize = 20) {
    return request<PaginatedResponse<EventDefinitionResponse>>(
      `/event-types${queryString({ page, page_size: pageSize })}`
    );
  },
  get(id: string) {
    return request<EventDefinitionResponse>(`/event-types/${id}`);
  },
  create(data: EventDefinitionCreate) {
    return request<EventDefinitionResponse>("/event-types", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: EventDefinitionUpdate) {
    return request<EventDefinitionResponse>(`/event-types/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/event-types/${id}`, { method: "DELETE" });
  },
};

// ── Actions (Event-Action Framework) ──

export const actions = {
  list(page = 1, pageSize = 20) {
    return request<PaginatedResponse<ActionResponse>>(
      `/actions${queryString({ page, page_size: pageSize })}`
    );
  },
  get(id: string) {
    return request<ActionResponse>(`/actions/${id}`);
  },
  create(data: ActionCreate) {
    return request<ActionResponse>("/actions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: ActionUpdate) {
    return request<ActionResponse>(`/actions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/actions/${id}`, { method: "DELETE" });
  },
  test(id: string) {
    return request<ActionTestResult>(`/actions/${id}/test`, { method: "POST" });
  },
  executions(id: string, page = 1, pageSize = 20) {
    return request<PaginatedResponse<ActionExecutionResponse>>(
      `/actions/${id}/executions${queryString({ page, page_size: pageSize })}`
    );
  },
};

// ── Event-Action Bindings ──

export const eventActions = {
  list(eventId?: string) {
    return request<PaginatedResponse<EventActionBindingResponse>>(
      `/event-action-bindings${queryString({ event_id: eventId })}`
    );
  },
  create(data: EventActionBindingCreate) {
    return request<EventActionBindingResponse>("/event-action-bindings", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: EventActionBindingUpdate) {
    return request<EventActionBindingResponse>(`/event-action-bindings/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  delete(id: string) {
    return request<void>(`/event-action-bindings/${id}`, { method: "DELETE" });
  },
};

export { ApiError };
