import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, TriangleAlert } from "lucide-react";
import AuthLayout from "../../components/layout/AuthLayout";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import { authService } from "../../services/auth.service";
import { parseApiError } from "../../services/api";

const ROLE_ROUTES = {
  SUPERADMIN: "/superadmin/dashboard",
  ADMIN: "/admin/dashboard",
  TEACHER: "/teacher/dashboard",
  STUDENT: "/student/dashboard",
  PARENT: "/parent/dashboard",
};

function Notice({ type = "success", children }) {
  const Icon = type === "error" ? TriangleAlert : CheckCircle2;
  const styles =
    type === "error"
      ? "border-error/20 bg-error-soft text-error"
      : "border-success/20 bg-success-soft text-emerald-700";

  return (
    <div className={`mb-4 flex gap-3 rounded-2xl border px-4 py-3 text-sm font-medium ${styles}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      {children}
    </div>
  );
}

function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const justVerified = searchParams.get("verified") === "true";
  const passwordReset = searchParams.get("reset") === "true";
  const inviteCompleted = searchParams.get("invite") === "success";

  const [formData, setFormData] = useState({
    email: "",
    password: "",
    remember: true,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  const redirectToVerification = (email, notice, purpose = "verification", redirectTo = "/verify-otp") => {
    if (!email) return;
    authService.setPendingVerificationEmail(email);
    navigate(`${redirectTo}?email=${encodeURIComponent(email)}&purpose=${encodeURIComponent(purpose)}`, {
      replace: true,
      state: { notice },
    });
  };

  const handleChange = (event) => {
    const { checked, name, type, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: type === "checkbox" ? checked : value }));
    setFieldErrors((prev) => ({ ...prev, [name]: undefined }));
    setError(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    setFieldErrors({});

    try {
      const data = await authService.login(formData.email, formData.password, {
        remember: formData.remember,
      });

      authService.clearPendingVerificationEmail();
      const role = String(data?.role || data?.user?.role || "").toUpperCase();
      const passwordResetRequired = Boolean(
        data?.user?.password_reset_required ?? data?.password_reset_required
      );

      if (role === "STUDENT" && passwordResetRequired) {
        navigate("/student/change-password", { replace: true });
        return;
      }
      navigate(ROLE_ROUTES[role] || "/", { replace: true });
    } catch (err) {
      const apiError = parseApiError(err, "Invalid email or password.");
      if (Object.keys(apiError.fieldErrors || {}).length > 0) {
        setFieldErrors(apiError.fieldErrors);
      }
      if (apiError.verificationRequired) {
        redirectToVerification(
          apiError.email || formData.email,
          apiError.message,
          apiError.purpose || "verification",
          apiError.redirectTo || "/verify-otp"
        );
        return;
      }
      setError(apiError.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Welcome back"
      description="Log in to continue into your school workspace."
      iconPosition="below"
      footer={
        <p className="mt-7 text-center text-sm text-text-soft">
          Need a workspace?{" "}
          <Link to="/register" className="font-semibold text-primary hover:text-primary-hover">
            Start free
          </Link>
        </p>
      }
    >
      {justVerified && <Notice>Account verified. You can now log in.</Notice>}
      {passwordReset && <Notice>Password reset successful. You can now log in.</Notice>}
      {inviteCompleted && <Notice>Account setup completed. You can now log in.</Notice>}
      {error && <Notice type="error">{error}</Notice>}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Input label="Email or admission number" type="text" name="email" value={formData.email} onChange={handleChange} placeholder="name@school.edu or NHS-2026-12345" required error={fieldErrors.email} />
        <Input label="Password" type="password" name="password" value={formData.password} onChange={handleChange} placeholder="Enter your password" required error={fieldErrors.password} />
        <div className="flex items-center justify-between gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" name="remember" checked={formData.remember} onChange={handleChange} className="h-4 w-4 rounded border-border accent-primary" />
            <span className="text-text-soft">Remember me</span>
          </label>
          <Link to="/forgot-password" className="font-semibold text-primary hover:text-primary-hover">
            Forgot password?
          </Link>
        </div>
        <Button type="submit" className="w-full" disabled={isLoading}>
          {isLoading ? "Logging in..." : "Log in to workspace"}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </form>
    </AuthLayout>
  );
}

export default LoginPage;
