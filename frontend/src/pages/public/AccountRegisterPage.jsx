import { useState } from "react";
import { ArrowRight, TriangleAlert } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import AuthLayout from "../../components/layout/AuthLayout";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import { authService } from "../../services/auth.service";
import { parseApiError } from "../../services/api";
import { parentService } from "../../services/parentService";
import { teacherService } from "../../services/teacherService";

const ROLE_CONFIG = {
  parent: {
    title: "Create parent account",
    description:
      "Create one parent account that can securely join multiple school workspaces.",
    service: parentService,
  },
  teacher: {
    title: "Create teacher account",
    description:
      "Create one teacher account that can securely join multiple school workspaces.",
    service: teacherService,
  },
};

const safeReturnTo = (value) => {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return "";
  }
  return value;
};

function AccountRegisterPage({ role }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.parent;
  const returnTo = safeReturnTo(searchParams.get("returnTo"));
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

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
    <AuthLayout
      title={config.title}
      description={config.description}
      stepLabel={`${role === "teacher" ? "Teacher" : "Parent"} registration`}
      footer={
        <p className="mt-7 text-center text-sm text-text-soft">
          Already have an account?{" "}
          <Link
            to={`/login${loginQuery}`}
            className="font-semibold text-primary hover:text-primary-hover"
          >
            Log in
          </Link>
        </p>
      }
    >
      {error ? (
        <div className="mb-4 flex gap-3 rounded-2xl border border-error/20 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Input
          label="Email"
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          placeholder="name@example.com"
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
          minLength={8}
          required
          error={fieldErrors.password}
        />
        <Input
          label="Confirm password"
          type="password"
          name="confirmPassword"
          value={formData.confirmPassword}
          onChange={handleChange}
          placeholder="Re-enter password"
          minLength={8}
          required
          error={fieldErrors.confirmPassword}
        />
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Creating account..." : "Create account"}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </form>
    </AuthLayout>
  );
}

export default AccountRegisterPage;
