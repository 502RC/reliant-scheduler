import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AUTH_DISABLED } from "@/services/auth";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import AppLayout from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import JobsList from "@/pages/JobsList";
import JobDetail from "@/pages/JobDetail";
import JobForm from "@/pages/JobForm";
import JobRunDetail from "@/pages/JobRunDetail";
import JobDependencyDag from "@/pages/JobDependencyDag";
import DagExplorer from "@/pages/DagExplorer";
import SchedulesList from "@/pages/SchedulesList";
import ScheduleForm from "@/pages/ScheduleForm";
import ConnectionsList from "@/pages/ConnectionsList";
import ConnectionForm from "@/pages/ConnectionForm";
import CredentialsList from "@/pages/CredentialsList";
import CredentialForm from "@/pages/CredentialForm";
import EnvironmentsList from "@/pages/EnvironmentsList";
import AgentsList from "@/pages/AgentsList";
import CalendarsList from "@/pages/CalendarsList";
import CalendarDetail from "@/pages/CalendarDetail";
import CalendarForm from "@/pages/CalendarForm";
import SlaPoliciesList from "@/pages/SlaPoliciesList";
import SlaPolicyDetail from "@/pages/SlaPolicyDetail";
import SlaPolicyForm from "@/pages/SlaPolicyForm";
import UsersList from "@/pages/UsersList";
import WorkgroupsList from "@/pages/WorkgroupsList";
import SecurityPoliciesList from "@/pages/SecurityPoliciesList";
import AuditLogViewer from "@/pages/AuditLogViewer";
import ActionsList from "@/pages/ActionsList";
import ActionForm from "@/pages/ActionForm";
import ActionHistory from "@/pages/ActionHistory";
import EventBindings from "@/pages/EventBindings";
import Login from "@/pages/Login";
import ErrorBoundary from "@/components/shared/ErrorBoundary";

function AuthenticatedRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        {/* Overview */}
        <Route path="/" element={<Dashboard />} />

        {/* Workloads */}
        <Route path="/jobs" element={<JobsList />} />
        <Route path="/jobs/new" element={<JobForm />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
        <Route path="/jobs/:id/edit" element={<JobForm />} />
        <Route path="/jobs/:id/runs/:runId" element={<JobRunDetail />} />
        <Route path="/jobs/:id/dependencies" element={<JobDependencyDag />} />
        <Route path="/dag" element={<DagExplorer />} />

        {/* Scheduling */}
        <Route path="/schedules" element={<SchedulesList />} />
        <Route path="/schedules/new" element={<ScheduleForm />} />
        <Route path="/schedules/:id/edit" element={<ScheduleForm />} />
        <Route path="/calendars" element={<CalendarsList />} />
        <Route path="/calendars/new" element={<CalendarForm />} />
        <Route path="/calendars/:id" element={<CalendarDetail />} />
        <Route path="/calendars/:id/edit" element={<CalendarForm />} />
        <Route path="/sla-policies" element={<SlaPoliciesList />} />
        <Route path="/sla-policies/new" element={<SlaPolicyForm />} />
        <Route path="/sla-policies/:id" element={<SlaPolicyDetail />} />
        <Route path="/sla-policies/:id/edit" element={<SlaPolicyForm />} />

        {/* Infrastructure */}
        <Route path="/connections" element={<ConnectionsList />} />
        <Route path="/connections/new" element={<ConnectionForm />} />
        <Route path="/connections/:id/edit" element={<ConnectionForm />} />
        <Route path="/credentials" element={<CredentialsList />} />
        <Route path="/credentials/new" element={<CredentialForm />} />
        <Route path="/credentials/:id/edit" element={<CredentialForm />} />
        <Route path="/environments" element={<EnvironmentsList />} />
        <Route path="/agents" element={<AgentsList />} />

        {/* Event-Action Framework */}
        <Route path="/actions" element={<ActionsList />} />
        <Route path="/actions/new" element={<ActionForm />} />
        <Route path="/actions/:id/edit" element={<ActionForm />} />
        <Route path="/actions/:id/history" element={<ActionHistory />} />
        <Route path="/event-bindings" element={<EventBindings />} />

        {/* Route aliases for common shorthand URLs */}
        <Route path="/sla" element={<Navigate to="/sla-policies" replace />} />
        <Route path="/event-actions" element={<Navigate to="/actions" replace />} />

        {/* Administration (RBAC-gated in sidebar, accessible if URL known) */}
        <Route path="/admin/users" element={<UsersList />} />
        <Route path="/admin/workgroups" element={<WorkgroupsList />} />
        <Route path="/admin/security-policies" element={<SecurityPoliciesList />} />
        <Route path="/admin/audit-log" element={<AuditLogViewer />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  // Dev mode: skip MSAL entirely, render app directly
  if (AUTH_DISABLED) {
    return (
      <ErrorBoundary>
        <BrowserRouter>
          <AuthenticatedRoutes />
        </BrowserRouter>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ProtectedRoute fallback={<Login />}>
          <AuthenticatedRoutes />
        </ProtectedRoute>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
