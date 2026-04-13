import React from "react";
import ReactDOM from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import { msalInstance, initializeMsal, AUTH_DISABLED } from "@/services/auth";
import App from "./App";
import "./styles.css";

initializeMsal().then(() => {
  const root = ReactDOM.createRoot(document.getElementById("root")!);

  if (AUTH_DISABLED) {
    // Dev mode: render without MSAL provider
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  } else {
    root.render(
      <React.StrictMode>
        <MsalProvider instance={msalInstance}>
          <App />
        </MsalProvider>
      </React.StrictMode>
    );
  }
});
