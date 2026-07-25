import { useEffect, useState } from "react";
import { ArrowRight, GraduationCap, TriangleAlert, Users } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import { authService } from "../../services/auth.service";
import { parseApiError } from "../../services/api";
import { parentService } from "../../services/parentService";
import { teacherService } from "../../services/teacherService";

const ROLE_CONFIG = {
  teacher: {
    label: "Teacher",
    title: "Create teacher account",
    description:
      "Create one teacher account, verify your email, and use school invitations to join each workspace.",
    submitLabel: "Create teacher account",
    service: teacherService,
    icon: GraduationCap,
  },
  parent: {
    label: "Parent",
    title: "Create parent account",
    description:
      "Create one parent account, verify your email, and accept invitations for your children.",
    submitLabel: "Create parent account",
    service: parentService,
    icon: Users,
  },
};

const INITIAL_FORM = {
  email: "",
  password: "",
  confirmPassword: "",
};

function AccountRegistrationForm({
  role = "teacher",
  allowRoleSwitch = false,
  returnTo = "",
  showHeading = true,
  onRoleChange,
}) {
  const navigate = useNavigate();
  const [activeRole, setActiveRole] = useState(
    ROLE_CONFIG[role] ? role : "teacher",
  );
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  useEffect(() => {
    if (!allowRoleSwitch && ROLE_CONFIG[role]) {
      setActiveRole(role);
    }
  }, [allowRoleSwitch, role]);

  const config = ROLE_CONFIG[activeRole];

  const changeRole = (nextRole) => {
    if (!ROLE_CONFIG[nextRole] || nextRole === activeRole || isSubmitting) return;
    setActiveRole(nextRole);
    setError(null);
    setFieldErrors({});
    onRoleChange?.(nextRole);
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => ({
      ...current,
      [name]: undefined,
      ...(name === "password" ? { confirmPassword: undefined } : {}),
    }));
    setError(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setFieldErrors({});

    if (formData.password !== formData.confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match." });
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await config.service.registerAccount({
        email: formData.email.trim().toLowerCase(),
        password: formData.password,
      });
      const email = result?.email || formData.email.trim().toLowerCase();
      authService.setPendingVerificationEmail(email);

      const nextQuery = new URLSearchParams({
        email,
        purpose: result?.purpose || "verification",
      });
      if (returnTo) nextQuery.set("returnTo", returnTo);

      navigate(`/verify-otp?${nextQuery.toString()}`, {
        replace: true,
        state: {
          notice:
            result?.message ||
            "Check your email for the verification code to complete account setup.",
        },
      });
    } catch (err) {
      const apiError = parseApiError(err, "Could not create the account.");
      setFieldErrors(apiError.fieldErrors || {});
      setError(apiError.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const loginQuery = returnTo
    ? `?returnTo=${encodeURIComponent(returnTo)}`
    : "";

  return (
    <div>
      {allowRoleSwitch ? (
        <div
          className="grid grid-cols-2 gap-1 rounded-2xl border border-border/70 bg-surface-muted/50 p-1"
          role="tablist"
          aria-label="Choose account type"
        >
          {Object.entries(ROLE_CONFIG).map(([roleKey, roleConfig]) => {
            const Icon = roleConfig.icon;
            const selected = activeRole === roleKey;
            return (
              <button
                key={roleKey}
                type="button"
                role="tab"
                aria-selected={selected}
                disabled={isSubmitting}
                onClick={() => changeRole(roleKey)}
                className={`flex min-h-12 items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition ${
                  selected
                    ? "bg-surface text-primary shadow-sm ring-1 ring-border/60"
                    : "text-text-muted hover:bg-surface/60 hover:text-text"
                }`}
              >
                <Icon className="h-4 w-4" />
                {roleConfig.label}
              </button>
            );
          })}
        </div>
      ) : null}

      {showHeading ? (
        <div className={allowRoleSwitch ? "mt-5" : ""}>
          <h3 className="text-xl font-semibold text-text sm:text-2xl">
            {config.title}
          </h3>
          <p className="mt-2 text-sm leading-6 text-text-muted">
            {config.description}
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="mt-5 flex gap-3 rounded-2xl border border-error/20 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        <Input
          label="Email address"
          type="email"
          name="email"
          autoComplete="email"
          value={formData.email}
          onChange={handleChange}
          placeholder="name@example.com"
          required
          error={fieldErrors.email}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Password"
            type="password"
            name="password"
            autoComplete="new-password"
            value={formData.password}
            onChange={handleChange}
            placeholder="At least 8 characters"
            minLength={8}
            required
            error={fieldErrors.password}
          />
          <Input
            label="Confirm password"
            type="password"
            name="confirmPassword"
            autoComplete="new-password"
            value={formData.confirmPassword}
            onChange={handleChange}
            placeholder="Re-enter password"
            minLength={8}
            required
            error={fieldErrors.confirmPassword}
          />
        </div>

        <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-xs leading-5 text-text-muted">
          Your account remains global. School access is added only after you accept an invitation from that school.
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Creating account..." : config.submitLabel}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-text-soft">
        Already have an account?{" "}
        <Link
          to={`/login${loginQuery}`}
          className="font-semibold text-primary hover:text-primary-hover"
        >
          Log in
        </Link>
      </p>
    </div>
  );
}

export default AccountRegistrationForm;
