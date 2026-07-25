import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import AuthLayout from "../../components/layout/AuthLayout";
import Button from "../../components/ui/Button";
import { authService } from "../../services/auth.service";
import { parseApiError } from "../../services/api";

const safeInvitationReturnTo = (value) => {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return "";
  }
  if (
    value.startsWith("/parent-invitations/") ||
    value.startsWith("/teacher-invitations/")
  ) {
    return value;
  }
  return "";
};

function Message({ type = "info", children }) {
  const isError = type === "error";
  const Icon = isError ? TriangleAlert : CheckCircle2;
  const styles = isError
    ? "border-error/20 bg-error-soft text-error"
    : "border-primary/20 bg-primary-subtle text-primary";

  return (
    <div className={`mb-4 flex gap-3 rounded-2xl border px-4 py-3 text-sm font-medium ${styles}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      {children}
    </div>
  );
}

function OTPValidationPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const emailParam = searchParams.get("email");
  const purpose = searchParams.get("purpose") || "verification";
  const returnTo = safeInvitationReturnTo(searchParams.get("returnTo"));
  const email = emailParam || (purpose === "verification" ? authService.getPendingVerificationEmail() || "" : "");
  const notice = location.state?.notice || null;
  const isPasswordResetFlow = purpose === "password_reset";
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [error, setError] = useState(null);
  const [resendMessage, setResendMessage] = useState(null);
  const inputRefs = useRef([]);

  useEffect(() => {
    if (!email) {
      if (isPasswordResetFlow) {
        navigate("/forgot-password", { replace: true });
      } else if (returnTo.startsWith("/parent-invitations/")) {
        navigate(`/parent/register?returnTo=${encodeURIComponent(returnTo)}`, {
          replace: true,
        });
      } else if (returnTo.startsWith("/teacher-invitations/")) {
        navigate(`/teacher/register?returnTo=${encodeURIComponent(returnTo)}`, {
          replace: true,
        });
      } else {
        navigate("/register", { replace: true });
      }
      return;
    }
    inputRefs.current[0]?.focus();
  }, [email, isPasswordResetFlow, navigate, returnTo]);

  const handleChange = (index, event) => {
    const value = event.target.value.replace(/\D/g, "");
    const nextOtp = [...otp];

    if (value.length > 1) {
      value.slice(0, 6).split("").forEach((digit, offset) => {
        if (index + offset < 6) nextOtp[index + offset] = digit;
      });
      setOtp(nextOtp);
      const nextEmptyIndex = nextOtp.findIndex((digit) => digit === "");
      inputRefs.current[nextEmptyIndex !== -1 ? nextEmptyIndex : 5]?.focus();
      return;
    }

    nextOtp[index] = value.slice(-1);
    setOtp(nextOtp);
    if (value && index < 5) inputRefs.current[index + 1]?.focus();
  };

  const handleKeyDown = (index, event) => {
    if (event.key === "Backspace" && otp[index] === "" && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const otpString = otp.join("");
    if (otpString.length < 6) {
      setError("Please enter a valid 6-digit code.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await authService.verifyOtp(email, otpString, purpose);
      if (purpose === "password_reset") {
        navigate("/forgot-password", { replace: true, state: { email, reset_token: result.reset_token } });
      } else {
        authService.clearPendingVerificationEmail();
        const query = new URLSearchParams({ verified: "true" });
        if (returnTo) query.set("returnTo", returnTo);
        navigate(`/login?${query.toString()}`, { replace: true });
      }
    } catch (err) {
      const apiError = parseApiError(err, "Invalid code. Please try again.");
      setError(apiError.fieldErrors.code || apiError.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    setError(null);
    setResendMessage(null);
    setIsResending(true);
    try {
      await authService.requestOtp(email, purpose);
      setResendMessage(isPasswordResetFlow ? "A new reset code has been sent to your email." : "A new verification code has been sent to your email.");
      setOtp(["", "", "", "", "", ""]);
      inputRefs.current[0]?.focus();
    } catch (err) {
      const apiError = parseApiError(err, "Failed to resend code.");
      setError(
        apiError.status === 429 && apiError.retryAfter
          ? `Too many requests. Please wait ${apiError.retryAfter} seconds before requesting another code.`
          : apiError.message
      );
    } finally {
      setIsResending(false);
    }
  };

  return (
    <AuthLayout
      title="Check your email"
      description={`${isPasswordResetFlow ? "We sent a password reset code to" : "We sent a verification code to"} ${email}.`}
      stepLabel={isPasswordResetFlow ? "Password reset" : "Email verification"}
    >
      {error && <Message type="error">{error}</Message>}
      {notice && !error && !resendMessage && <Message>{notice}</Message>}
      {resendMessage && !error && <Message>{resendMessage}</Message>}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-6 gap-2">
          {otp.map((digit, index) => (
            <input
              key={index}
              ref={(element) => (inputRefs.current[index] = element)}
              type="text"
              inputMode="numeric"
              maxLength={index === 0 ? 6 : 1}
              value={digit}
              onChange={(event) => handleChange(index, event)}
              onKeyDown={(event) => handleKeyDown(index, event)}
              className="h-14 rounded-2xl border border-border bg-surface text-center text-xl font-semibold text-text outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
            />
          ))}
        </div>

        <Button type="submit" className="w-full" disabled={isLoading || otp.join("").length < 6}>
          {isLoading ? "Verifying..." : isPasswordResetFlow ? "Verify reset code" : "Verify code"}
        </Button>
      </form>

      <p className="mt-7 text-center text-sm text-text-soft">
        Did not receive the code?{" "}
        <button
          type="button"
          className="font-semibold text-primary hover:text-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isLoading || isResending || !email}
          onClick={handleResend}
        >
          {isResending ? "Sending..." : "Resend"}
        </button>
      </p>
    </AuthLayout>
  );
}

export default OTPValidationPage;
