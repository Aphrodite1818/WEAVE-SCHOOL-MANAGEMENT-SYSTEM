import { useEffect, useRef } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import SubscriptionProvider from "../features/subscriptions/SubscriptionProvider";
import { APP_NAVIGATE_EVENT, NAVIGATION_ABORT_EVENT } from "../services/api";
import ProtectedRoute from "./ProtectedRoute";
import { adminRoutes } from "./adminRoutes";
import { parentRoutes } from "./parentRoutes";
import { publicRoutes } from "./publicRoutes";
import { studentRoutes } from "./studentRoutes";
import { superadminRoutes } from "./superadminRoutes";
import { teacherRoutes } from "./teacherRoutes";
import LegalPage from "../pages/shared/LegalPage";
import ProfileSettingsPage from "../pages/shared/ProfileSettingsPage";

function RouteChangeAbortBridge() {
  const location = useLocation();
  const navigate = useNavigate();
  const previousLocationKeyRef = useRef(location.key || `${location.pathname}${location.search}`);

  useEffect(() => {
    const nextLocationKey = location.key || `${location.pathname}${location.search}`;

    if (previousLocationKeyRef.current !== nextLocationKey) {
      window.dispatchEvent(new CustomEvent(NAVIGATION_ABORT_EVENT));
      previousLocationKeyRef.current = nextLocationKey;
    }
  }, [location.key, location.pathname, location.search]);

  useEffect(() => {
    const handleAppNavigation = (event) => {
      const path = event.detail?.path;
      if (typeof path === "string" && path && path !== location.pathname) {
        navigate(path, { replace: true });
      }
    };

    window.addEventListener(APP_NAVIGATE_EVENT, handleAppNavigation);
    return () => window.removeEventListener(APP_NAVIGATE_EVENT, handleAppNavigation);
  }, [location.pathname, navigate]);

  return null;
}

function AppRoutes() {
  return (
    <BrowserRouter>
      <SubscriptionProvider>
        <RouteChangeAbortBridge />
        <Routes>
          {publicRoutes}

          <Route element={<ProtectedRoute />}>
            <Route path="/profile" element={<ProfileSettingsPage />} />
            <Route path="/legal" element={<LegalPage />} />
            {adminRoutes}
            {teacherRoutes}
            {studentRoutes}
            {parentRoutes}
            {superadminRoutes}
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </SubscriptionProvider>
    </BrowserRouter>
  );
}

export default AppRoutes;
