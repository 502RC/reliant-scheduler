import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { formatDateTime } from "@/utils/format";
import ConnectionStatus from "@/components/shared/ConnectionStatus";
import NotificationDropdown from "@/components/shared/NotificationDropdown";
import { useEventBus } from "@/services/eventBus";

interface Props {
  waitingJobs?: number;
}

export default function Header({ waitingJobs }: Props) {
  const { user, logout } = useAuth();
  const { connectionStatus } = useEventBus();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const now = new Date();
  const prodDate = now.toLocaleDateString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const prodTime = now.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!dropdownOpen) return;
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen]);

  // Close dropdown on Escape
  useEffect(() => {
    if (!dropdownOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [dropdownOpen]);

  return (
    <header className="header" role="banner">
      <div className="header-left">
        <div className="header-stat">
          <span className="header-stat-label">Production Date</span>
          <span className="header-stat-value">{prodDate} {prodTime}</span>
        </div>
      </div>
      <div className="header-right">
        <ConnectionStatus status={connectionStatus} />
        <div className="header-stat">
          <span className="header-stat-label">Waiting Jobs</span>
          <span className="header-stat-value">{waitingJobs ?? 0}</span>
        </div>
        <NotificationDropdown />
        {user && (
          <div className="header-user-menu" ref={dropdownRef}>
            <button
              className="header-user"
              onClick={() => setDropdownOpen((prev) => !prev)}
              aria-expanded={dropdownOpen}
              aria-haspopup="true"
              aria-label={`User menu for ${user.displayName}`}
            >
              <div className="header-avatar" aria-hidden>
                {user.displayName.charAt(0).toUpperCase()}
              </div>
              <span>{user.displayName}</span>
              <span className="header-role-badge">{user.role}</span>
              <svg
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                aria-hidden
                style={{
                  transform: dropdownOpen ? "rotate(180deg)" : undefined,
                  transition: "transform 0.15s",
                }}
              >
                <path d="M3 4.5l3 3 3-3" />
              </svg>
            </button>
            {dropdownOpen && (
              <div className="user-dropdown" role="menu">
                <div className="user-dropdown-header">
                  <div className="user-dropdown-name">{user.displayName}</div>
                  <div className="user-dropdown-email">{user.email}</div>
                  <div className="user-dropdown-role">
                    Role: <strong>{user.role}</strong>
                  </div>
                  {user.lastLogin && (
                    <div className="user-dropdown-meta">
                      Last login: {formatDateTime(user.lastLogin)}
                    </div>
                  )}
                </div>
                <div className="user-dropdown-divider" />
                <button
                  className="user-dropdown-item user-dropdown-logout"
                  onClick={() => {
                    setDropdownOpen(false);
                    logout();
                  }}
                  role="menuitem"
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                  >
                    <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
