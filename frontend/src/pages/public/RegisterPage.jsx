import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, TriangleAlert } from "lucide-react";
import AuthLayout from "../../components/layout/AuthLayout";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import { tenantService } from "../../services/tenant.service";
import { authService } from "../../services/auth.service";
import { parseApiError, remapFieldErrors } from "../../services/api";
import {
  LANDING_PRICING_PLANS,
  formatPlanName,
  getSelectedSubscriptionPlan,
  saveSelectedSubscriptionPlan,
} from "../../features/subscriptions/subscriptionConfig";

const REGISTER_FIELD_MAP = {
  school_name: "schoolName",
};

const canonicalPlanCode = (value) =>
  String(value || "").toLowerCase() === "free_trial"
    ? "free"
    : String(value || "").toLowerCase();

function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({
    schoolName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [passwordStrength, setPasswordStrength] = useState(0);
  const selectedPlan = useMemo(() => {
    const queryPlan = canonicalPlanCode(searchParams.get("plan"));
    const queryBilling = searchParams.get("billing");
    const storedPlan = getSelectedSubscriptionPlan();
    return (
      (queryPlan && {
        planCode: queryPlan,
        billingInterval: queryBilling || "term",
      }) ||
      storedPlan
    );
  }, [searchParams]);
  const selectedPlanDetails = useMemo(
    () =>
      LANDING_PRICING_PLANS.find(
        (plan) => plan.planCode === selectedPlan?.planCode,
      ) || null,
    [selectedPlan],
  );

  useEffect(() => {
    if (selectedPlan) saveSelectedSubscriptionPlan(selectedPlan);
  }, [selectedPlan]);

  const getPasswordStrength = (password) => {
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    return score;
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => ({ ...prev, [name]: undefined }));
    setError(null);
    if (name === "password") setPasswordStrength(getPasswordStrength(value));
  };

  const redirectToVerification = (
    email,
    notice,
    purpose = "verification",
    redirectTo = "/verify-otp",
  ) => {
    if (!email) return;
    authService.setPendingVerificationEmail(email);
    navigate(
      `${redirectTo}?email=${encodeURIComponent(email)}&purpose=${encodeURIComponent(purpose)}`,
      {
        replace: true,
        state: { notice },
      },
    );
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setFieldErrors({});

    if (formData.password !== formData.confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match." });
      return;
    }

    if (formData.password.length < 8) {
      setFieldErrors({ password: "Password must be at least 8 characters." });
      return;
    }

    setIsLoading(true);

    try {
      const result = await tenantService.registerTenant({
        school_name: formData.schoolName,
        email: formData.email,
        password: formData.password,
        ...(selectedPlan?.planCode
          ? { initial_plan_intent: selectedPlan.planCode }
          : {}),
      });

      if (result?.verification_required) {
        redirectToVerification(
          result.email || formData.email,
          result.message ||
            "Please check your email for the verification code.",
          result.purpose || "verification",
          result.redirect_to || "/verify-otp",
        );
        return;
      }

      setError(
        "Something went wrong while processing your request. Please try again.",
      );
    } catch (err) {
      const apiError = parseApiError(
        err,
        "Something went wrong while processing your request. Please try again.",
      );
      if (apiError.verificationRequired) {
        redirectToVerification(
          apiError.email || formData.email,
          apiError.message,
          apiError.purpose || "verification",
          apiError.redirectTo || "/verify-otp",
        );
        return;
      }

      const mappedFieldErrors = remapFieldErrors(
        apiError.fieldErrors,
        REGISTER_FIELD_MAP,
      );
      if (Object.keys(mappedFieldErrors).length > 0)
        setFieldErrors(mappedFieldErrors);
      setError(apiError.message);
    } finally {
      setIsLoading(false);
    }
  };

  const strengthLabels = [
    "Too short",
    "Weak",
    "Fair",
    "Good",
    "Strong",
    "Very strong",
  ];

  return (
    <AuthLayout
      title="Create your school workspace"
      description="Set up your school workspace and verify the admin email."
      footer={
        <p className="mt-7 text-center text-sm text-text-soft">
          Already have an account?{" "}
          <Link
            to="/login"
            className="font-semibold text-primary hover:text-primary-hover"
          >
            Log in
          </Link>
        </p>
      }
    >
      {error && (
        <div className="mb-4 flex gap-3 rounded-2xl border border-error/20 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {selectedPlan?.planCode ? (
        <div className="mb-5 rounded-2xl border border-border/70 bg-surface-muted/25 px-4 py-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                First-term preference
              </p>
              <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <p className="text-base font-semibold text-text">
                  {formatPlanName(selectedPlan.planCode)}
                </p>
                {selectedPlanDetails?.priceLabel ? (
                  <span className="text-sm text-text-muted">
                    {selectedPlanDetails.priceLabel}
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-xs leading-5 text-text-muted">
                No payment is collected during registration. Your school starts
                on permanent Free access, and this preference is only suggested
                when you open an academic term.
              </p>
              <Link
                to="/pricing"
                className="mt-2 inline-flex text-xs font-semibold text-primary hover:text-primary-hover"
              >
                Change preference
              </Link>
            </div>
          </div>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <Input
          label="School name"
          name="schoolName"
          value={formData.schoolName}
          onChange={handleChange}
          placeholder="Greenfield International School"
          required
          error={fieldErrors.schoolName}
        />
        <Input
          label="Admin work email"
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          placeholder="admin@school.edu"
          required
          error={fieldErrors.email}
        />
        <Input
          label="Password"
          type="password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          placeholder="At least 8 characters"
          required
          minLength={8}
          error={fieldErrors.password}
          hint="Use 8+ characters with letters and numbers."
        />
        {formData.password && (
          <div className="-mt-1 space-y-1">
            <div className="grid grid-cols-5 gap-1">
              {[1, 2, 3, 4, 5].map((level) => (
                <span
                  key={level}
                  className={`h-1 rounded-full ${passwordStrength >= level ? "bg-primary" : "bg-surface-muted"}`}
                />
              ))}
            </div>
            <p className="text-[11px] leading-4 text-text-muted">
              {strengthLabels[passwordStrength]}
            </p>
          </div>
        )}
        <Input
          label="Confirm password"
          type="password"
          name="confirmPassword"
          value={formData.confirmPassword}
          onChange={handleChange}
          placeholder="Re-enter password"
          required
          error={fieldErrors.confirmPassword}
        />
        <Button type="submit" className="w-full" disabled={isLoading}>
          {isLoading ? "Creating workspace..." : "Create workspace"}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </form>
    </AuthLayout>
  );
}

export default RegisterPage;
