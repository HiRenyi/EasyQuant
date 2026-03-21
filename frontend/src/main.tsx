import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import SetPasswordModal from "./components/SetPasswordModal";
import AppRoutes from "./AppRoutes";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <SetPasswordModal />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
