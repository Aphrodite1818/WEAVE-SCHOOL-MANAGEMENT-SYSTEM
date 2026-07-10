import { Route } from "react-router-dom";

import ForgotPasswordPage from "../pages/public/ForgotPasswordPage";
import InvitePage from "../pages/public/InvitePage";
import LandingPage from "../pages/public/LandingPage";
import LoginPage from "../pages/public/LoginPage";
import OTPValidationPage from "../pages/public/otp_validationPage";
import PricingPage from "../pages/public/PricingPage";
import RegisterPage from "../pages/public/RegisterPage";

export const publicRoutes = (
  <>
    <Route path="/" element={<LandingPage />} />
    <Route path="/pricing" element={<PricingPage />} />
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/verify-otp" element={<OTPValidationPage />} />
    <Route path="/invite" element={<InvitePage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
  </>
);
