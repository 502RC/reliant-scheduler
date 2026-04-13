import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";
import ErrorBoundary from "@/components/shared/ErrorBoundary";
import AuthErrorToast from "@/components/auth/AuthErrorToast";
import ToastContainer from "@/components/shared/ToastContainer";
import { EventBusProvider } from "@/services/eventBus";

export default function AppLayout() {
  return (
    <EventBusProvider>
      <div className="app-layout">
        <Sidebar />
        <div className="main-content">
          <Header />
          <main className="page-content">
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
        <AuthErrorToast />
        <ToastContainer />
      </div>
    </EventBusProvider>
  );
}
