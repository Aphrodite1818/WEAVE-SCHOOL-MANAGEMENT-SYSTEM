import { Route } from "react-router-dom";

import AccountRegisterPage from "../pages/public/AccountRegisterPage";
import ForgotPasswordPage from "../pages/public/ForgotPasswordPage";
import InvitationAcceptancePage from "../pages/public/InvitationAcceptancePage";
import JoinPage from "../pages/public/JoinPage";
import LoginPage from "../pages/public/LoginPage";
import MaintenanceModePage from "../pages/public/MaintenanceModePage";
import NetworkBlockedPage from "../pages/public/NetworkBlockedPage";
import OTPValidationPage from "../pages/public/otp_validationPage";
import PricingPage from "../pages/public/PricingPage";
import PwaAwareLandingPage from "../pages/public/PwaAwareLandingPage";
import RegisterPage from "../pages/public/RegisterPage";

export const publicRoutes = (
  <>
    <Route path="/" element={<PwaAwareLandingPage />} />
    <Route path="/pricing" element={<PricingPage />} />
    <Route path="/join" element={<JoinPage />} />
    <Route path="/login" element={<LoginPage />} />
    <Route path="/maintenance" element={<MaintenanceModePage />} />
    <Route path="/network-blocked" element={<NetworkBlockedPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/parent/register" element={<AccountRegisterPage role="parent" />} />
    <Route path="/teacher/register" element={<AccountRegisterPage role="teacher" />} />
    <Route path="/verify-otp" element={<OTPValidationPage />} />
    <Route
      path="/parent-invitations/:token"
      element={<InvitationAcceptancePage role="parent" />}
    />
    <Route
      path="/teacher-invitations/:token"
      element={<InvitationAcceptancePage role="teacher" />}
    />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
  </>
);
