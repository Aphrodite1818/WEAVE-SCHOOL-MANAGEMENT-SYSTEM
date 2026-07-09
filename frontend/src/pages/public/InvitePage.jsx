import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, Clock3, TriangleAlert } from "lucide-react";
import AuthLayout from "../../components/layout/AuthLayout";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import { authService } from "../../services/auth.service";
import { parseApiError } from "../../services/api";

function StateMessage({ type = "info", title, children }) {
  const icons = { error: TriangleAlert, success: CheckCircle2, warning: Clock3, info: CheckCircle2 };
  const Icon = icons[type] || CheckCircle2;
  const styles = {
    error: "border-error/20 bg-error-soft text-error",
    success: "border-success/20 bg-success-soft text-emerald-700",
    warning: "border-warning/20 bg-warning-soft text-amber-700",
    info: "border-primary/20 bg-primary-subtle text-primary",
  };

  return (
    <div className={`mb-5 rounded-2xl border px-4 py-4 text-sm ${styles[type]}`}>
      <div className="flex gap-3">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          {title && <p className="font-semibold">{title}</p>}
          <div className={title ? "mt-1" : ""}>{children}</div>
        </div>
      </div>
    </div>
  );
}

function InvitePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");
  const [inviteMeta, setInviteMeta] = useState({ status: token ? "loading" : "invalid", purpose: null });
  const [formData, setFormData] = useState({ email: "", password: "", confirmPassword: "" });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [successMessage, setSuccessMessage] = useState(null);
  const [inviteStatusError, setInviteStatusError] = useState(null);

  useEffect(() => {
    if (!token) return;

    let isMounted = true;
    const timeoutId = window.setTimeout(() => {
      setInviteMeta({ status: "loading", purpose: null });

      const loadInviteStatus = async () => {
        try {
          setInviteStatusError(null);
          const result = await authService.getInviteStatus(token);
          if (!isMounted) return;
          setInviteMeta({ status: result?.status || "invalid", purpose: result?.purpose || null });
        } catch (err) {
          if (!isMounted) return;
          const apiError = parseApiError(err, "Something went wrong. Please try again.");
          setInviteStatusError(apiError.isNetworkError ? "Something went wrong. Please try again." : apiError.message);
          setInviteMeta({ status: "error", purpose: null });
        }
      };

      loadInviteStatus();
    }, 0);

    return () => {
      isMounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [token]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => ({
      ...prev,
      [name]: undefined,
      ...(name === "password" || name === "confirmPassword" ? { confirmPassword: undefined } : {}),
    }));
    setError(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!token) {
      setError("Invalid or missing invite token.");
      return;
    }

    setError(null);
    setFieldErrors({});

    if (formData.password !== formData.confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match." });
      return;
    }

    setIsLoading(true);

    try {
      const result =
        inviteMeta.purpose === "tenant_activation"
          ? await authService.activateTenant(formData.email, formData.password, token)
          : await authService.acceptInvite(formData.email, formData.password, token);

      setSuccessMessage(result?.detail || "Account setup completed successfully.");
      navigate("/login?invite=success", { replace: true });
    } catch (err) {
      const apiError = parseApiError(err, "Failed to complete account setup.");
      if (Object.keys(apiError.fieldErrors).length > 0) setFieldErrors(apiError.fieldErrors);
      if (apiError.isNetworkError) {
        setError("Something went wrong. Please try again.");
        return;
      }

      const normalizedMessage = apiError.message.toLowerCase();
      if (normalizedMessage.includes("already been used")) {
        setInviteMeta((prev) => ({ ...prev, status: "used" }));
      } else if (normalizedMessage.includes("invalid")) {
        setInviteMeta((prev) => ({ ...prev, status: "invalid" }));
      } else if (normalizedMessage.includes("expired")) {
        setInviteMeta((prev) => ({ ...prev, status: "expired" }));
      } else {
        setError(apiError.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const inviteStatus = token ? inviteMeta.status : "invalid";
  const invitePurpose = token ? inviteMeta.purpose : null;
  const isInviteValid = inviteStatus === "valid";
  const isTenantActivation = invitePurpose === "tenant_activation";
  const isSuperadminInvite = invitePurpose === "superadmin_invite";
  const heading = isTenantActivation ? "Activate your school" : isSuperadminInvite ? "Set up superadmin access" : "Join your school";
  const subheading = isTenantActivation
    ? "Confirm the admin email and set your password to activate this tenant."
    : isSuperadminInvite
      ? "Confirm your email address and activate platform-level access."
      : "Confirm your email address and set your password.";

  return (
    <AuthLayout
      title={heading}
      description={subheading}
      stepLabel="Invite acceptance"
      footer={
        <p className="mt-7 text-center text-sm text-text-soft">
          Already set up?{" "}
          <Link to="/login" className="font-semibold text-primary hover:text-primary-hover">
            Log in
          </Link>
        </p>
      }
    >
      {!token && <StateMessage type="error" title="Missing invite token">Please check your invitation link.</StateMessage>}
      {inviteStatus === "loading" && <StateMessage>Checking your invite link...</StateMessage>}
      {inviteStatusError && <StateMessage type="error">{inviteStatusError}</StateMessage>}
      {inviteStatus === "invalid" && <StateMessage type="error" title="This invite link is invalid">Open the latest email invite, or request a new link.</StateMessage>}
      {inviteStatus === "expired" && <StateMessage type="warning" title="This invite link has expired">Please request a new invite.</StateMessage>}
      {inviteStatus === "used" && <StateMessage type="success" title="This invite link has already been used">Your account setup is complete. Please log in instead.</StateMessage>}
      {error && <StateMessage type="error">{error}</StateMessage>}
      {successMessage && !error && <StateMessage type="success">{successMessage}</StateMessage>}

      {isInviteValid && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <Input label="Email" type="email" name="email" value={formData.email} onChange={handleChange} placeholder="name@school.edu" required error={fieldErrors.email} />
          <Input label="Create password" type="password" name="password" value={formData.password} onChange={handleChange} placeholder="At least 8 characters" required minLength={8} error={fieldErrors.password} />
          <Input label="Confirm password" type="password" name="confirmPassword" value={formData.confirmPassword} onChange={handleChange} placeholder="Re-enter password" required error={fieldErrors.confirmPassword} />
          <Button type="submit" className="w-full" disabled={isLoading || !token}>
            {isLoading ? "Setting up..." : isTenantActivation ? "Activate tenant" : "Set up account"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}

export default InvitePage;
