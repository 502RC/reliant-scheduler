import { NavLink } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

const NAV_ITEMS = [
  {
    section: "Overview",
    items: [
      { to: "/", label: "Dashboard", icon: DashboardIcon },
    ],
  },
  {
    section: "Workloads",
    items: [
      { to: "/jobs", label: "Jobs", icon: JobsIcon },
      { to: "/dag", label: "DAG Explorer", icon: DagIcon },
      { to: "/jobs/new", label: "Create Job", icon: PlusIcon },
    ],
  },
  {
    section: "Scheduling",
    roles: ["admin", "scheduler_admin", "scheduler"] as const,
    items: [
      { to: "/schedules", label: "Schedules", icon: ScheduleIcon },
      { to: "/calendars", label: "Calendars", icon: CalendarIcon },
      { to: "/sla-policies", label: "SLA Policies", icon: SlaIcon },
    ],
  },
  {
    section: "Infrastructure",
    roles: ["admin", "scheduler_admin", "scheduler"] as const,
    items: [
      { to: "/agents", label: "Agents", icon: AgentIcon },
      { to: "/connections", label: "Connections", icon: ConnectionIcon },
      { to: "/credentials", label: "Credentials", icon: CredentialIcon },
      { to: "/environments", label: "Environments", icon: EnvironmentIcon },
    ],
  },
  {
    section: "Event-Actions",
    roles: ["admin", "scheduler_admin", "scheduler"] as const,
    items: [
      { to: "/actions", label: "Actions", icon: ActionIcon },
      { to: "/event-bindings", label: "Event Bindings", icon: BindingIcon },
    ],
  },
  {
    section: "Administration",
    roles: ["admin", "scheduler_admin"] as const,
    items: [
      { to: "/admin/users", label: "Users", icon: UsersIcon },
      { to: "/admin/workgroups", label: "Workgroups", icon: WorkgroupIcon },
      { to: "/admin/security-policies", label: "Security Policies", icon: ShieldIcon },
      { to: "/admin/audit-log", label: "Audit Log", icon: AuditIcon },
    ],
  },
];

export default function Sidebar() {
  const { hasRole } = useAuth();

  return (
    <nav className="sidebar" aria-label="Main navigation">
      <div className="sidebar-brand" style={{ background: "#ffffff", borderRadius: 8, margin: "0 12px 8px", padding: "14px 12px", display: "flex", justifyContent: "center" }}>
        <img src="/logo-full.png" alt="Reliant Scheduler" style={{ maxWidth: "100%", height: "auto", maxHeight: 80 }} />
      </div>
      <div className="sidebar-nav">
        {NAV_ITEMS.map((section) => {
          if (section.roles && !hasRole(...section.roles)) return null;
          return (
            <div className="sidebar-section" key={section.section}>
              <div className="sidebar-section-title">{section.section}</div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `sidebar-link${isActive ? " active" : ""}`
                  }
                >
                  <item.icon />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

function DashboardIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function JobsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
      <rect x="9" y="3" width="6" height="4" rx="1" />
      <path d="M9 14l2 2 4-4" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v8M8 12h8" />
    </svg>
  );
}

function ScheduleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
      <rect x="7" y="14" width="3" height="3" rx="0.5" />
    </svg>
  );
}

function SlaIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

function AgentIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M9 9h6M9 13h6M9 17h4" />
    </svg>
  );
}

function ConnectionIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 7h3a5 5 0 010 10h-3M9 17H6a5 5 0 010-10h3" />
      <path d="M8 12h8" />
    </svg>
  );
}

function CredentialIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  );
}

function EnvironmentIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18" />
      <path d="M5.5 6.5l6.5 3 6.5-3" />
      <path d="M5.5 17.5l6.5-3 6.5 3" />
      <path d="M5.5 6.5v11" />
      <path d="M18.5 6.5v11" />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87" />
      <path d="M16 3.13a4 4 0 010 7.75" />
    </svg>
  );
}

function WorkgroupIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M12 8v8M8 12h8" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function AuditIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M16 13H8M16 17H8M10 9H8" />
    </svg>
  );
}

function ActionIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 01-3.46 0" />
    </svg>
  );
}

function BindingIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  );
}

function DagIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="5" cy="6" r="2.5" />
      <circle cx="5" cy="18" r="2.5" />
      <circle cx="19" cy="12" r="2.5" />
      <path d="M7.5 6h5.5a3 3 0 013 3v0a3 3 0 01-3 3H16.5" />
      <path d="M7.5 18h5.5a3 3 0 003-3v0a3 3 0 00-3-3H16.5" />
    </svg>
  );
}
