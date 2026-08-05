import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, TriangleAlert } from "lucide-react";
import AuthLayout from "../../components/layout/AuthLayout";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import { authService } from "../../services/auth.service";
import { parseApiError, remapFieldErrors } from "../../services/api";

const RESET_PASSWORD_FIELD_MAP = {
  new_password: "password",
};

function Alert({ children }) {
  return (
    <div className="mb-4 flex gap-3 rounded-2xl border border-error/20 bg-error-soft px-4 py-3 text-sm font-medium text-error">
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
      {children}
    </div>
  );
}

function ForgotPasswordPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const resetToken = state?.reset_token;
  const resetEmail = state?.email;
  const step = resetToken ? "reset" : "request";

  const [inputEmail, setInputEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordStrength, setPasswordStrength] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  const getPasswordStrength = (value) => {
    let score = 0;
    if (value.length >= 8) score++;
    if (value.length >= 12) score++;
    if (/[A-Z]/.test(value)) score++;
    if (/[0-9]/.test(value)) score++;
    if (/[^A-Za-z0-9]/.test(value)) score++;
    return score;
  };

  const handleRequestOtp = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    setFieldErrors({});

    try {
      await authService.requestOtp(inputEmail, "password_reset");
      navigate(`/verify-otp?email=${encodeURIComponent(inputEmail)}&purpose=password_reset`, {
        state: { notice: "We sent a password reset code to your email." },
      });
    } catch (err) {
      const apiError = parseApiError(err, "Something went wrong. Please try again.");
      if (apiError.status === 429) {
        navigate(`/verify-otp?email=${encodeURIComponent(inputEmail)}&purpose=password_reset`, {
          state: {
            notice: apiError.retryAfter
              ? `A reset code was sent recently. Please wait ${apiError.retryAfter} seconds before requesting another one.`
              : "A reset code was sent recently. Please use that code or wait a moment before requesting another one.",
          },
        });
        return;
      }
      if (Object.keys(apiError.fieldErrors).length > 0) setFieldErrors(apiError.fieldErrors);
      setError(apiError.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (event) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match." });
      return;
    }
    if (password.length < 8) {
      setFieldErrors({ password: "Password must be at least 8 characters." });
      return;
    }

    setIsLoading(true);
    setError(null);
    setFieldErrors({});

    try {
      await authService.resetPassword(resetEmail, password, resetToken);
      navigate("/login?reset=true", { replace: true });
    } catch (err) {
      const apiError = parseApiError(err, "Failed to reset password. Please try again.");
      const mappedFieldErrors = remapFieldErrors(apiError.fieldErrors, RESET_PASSWORD_FIELD_MAP);
      if (Object.keys(mappedFieldErrors).length > 0) setFieldErrors(mappedFieldErrors);
      setError(apiError.message);
    } finally {
      setIsLoading(false);
    }
  };

  if (step === "request") {
    return (
      <AuthLayout
        title="Reset your password"
        description="Enter your work email and we will send a secure reset code."
        footer={
          <p className="mt-7 text-center text-sm text-text-soft">
            Remembered it?{" "}
            <Link to="/login" className="font-semibold text-primary hover:text-primary-hover">
              Back to login
            </Link>
          </p>
        }
      >
        {error && <Alert>{error}</Alert>}
        <form onSubmit={handleRequestOtp} className="space-y-5">
          <Input
            label="Work email"
            type="email"
            name="email"
            value={inputEmail}
            onChange={(event) => {
              setInputEmail(event.target.value);
              setFieldErrors((prev) => ({ ...prev, email: undefined }));
              setError(null);
            }}
            placeholder="name@school.edu"
            required
            error={fieldErrors.email}
          />
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Sending code..." : "Send reset code"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Set new password"
      description={`Enter a new password for ${resetEmail}.`}
      footer={
        <p className="mt-7 text-center text-sm text-text-soft">
          Remembered it?{" "}
          <Link to="/login" className="font-semibold text-primary hover:text-primary-hover">
            Back to login
          </Link>
        </p>
      }
    >
      {error && <Alert>{error}</Alert>}
      <form onSubmit={handleResetPassword} className="space-y-5">
        <Input
          label="New password"
          type="password"
          name="password"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            setPasswordStrength(getPasswordStrength(event.target.value));
            setFieldErrors((prev) => ({ ...prev, password: undefined }));
            setError(null);
          }}
          placeholder="At least 8 characters"
          required
          minLength={8}
          error={fieldErrors.password}
        />
        {password && (
          <div className="grid grid-cols-5 gap-1">
            {[1, 2, 3, 4, 5].map((level) => (
              <span key={level} className={`h-1.5 rounded-full ${passwordStrength >= level ? "bg-primary" : "bg-surface-muted"}`} />
            ))}
          </div>
        )}
        <Input
          label="Confirm new password"
          type="password"
          name="confirmPassword"
          value={confirmPassword}
          onChange={(event) => {
            setConfirmPassword(event.target.value);
            setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
            setError(null);
          }}
          placeholder="Re-enter password"
          required
          error={fieldErrors.confirmPassword}
        />
        <Button type="submit" className="w-full" disabled={isLoading}>
          {isLoading ? "Resetting..." : "Reset password"}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </form>
    </AuthLayout>
  );
}

export default ForgotPasswordPage;
