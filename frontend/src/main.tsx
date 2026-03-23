import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { ColorModeProvider } from "./contexts/ColorModeContext";
import SetPasswordModal from "./components/SetPasswordModal";
import AppRoutes from "./AppRoutes";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ColorModeProvider>
        <AuthProvider>
          <AppRoutes />
          <SetPasswordModal />
        </AuthProvider>
      </ColorModeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
