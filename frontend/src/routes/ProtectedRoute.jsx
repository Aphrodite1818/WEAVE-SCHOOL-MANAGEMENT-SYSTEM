import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { authSession } from "../services/api";
import { authService } from "../services/auth.service";
import { getValidTokenPayload } from "../utils/auth";

const MAX_BOOTSTRAP_ATTEMPTS = 3;

const wait = (milliseconds) =>
  new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });

const isRetryableBootstrapError = (error) => {
  const status = error?.response?.status ?? error?.status ?? null;

  // Missing status normally means a network/transport failure. Retry gateway,
  // timeout, and backend failures, but never repeat permanent auth/permission
  // responses such as 401, 403, or rate-limit responses.
  return status == null || status === 408 || status >= 500;
};

function ProtectedRoute() {
  const location = useLocation();
  const [bootstrapDone, setBootstrapDone] = useState(() => Boolean(getValidTokenPayload()));
  const [bootstrapError, setBootstrapError] = useState(null);
  const [bootstrapVersion, setBootstrapVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (getValidTokenPayload()) {
        if (!cancelled) {
          setBootstrapError(null);
          setBootstrapDone(true);
        }
        return;
      }

      if (!cancelled) {
        setBootstrapError(null);
        setBootstrapDone(false);
      }

      for (let attempt = 1; attempt <= MAX_BOOTSTRAP_ATTEMPTS; attempt += 1) {
        try {
          await authService.bootstrapSession();

          if (!cancelled) {
            setBootstrapDone(true);
          }
          return;
        } catch (error) {
          if (cancelled) return;

          const shouldRetry =
            attempt < MAX_BOOTSTRAP_ATTEMPTS && isRetryableBootstrapError(error);

          if (shouldRetry) {
            await wait(attempt * 750);
            continue;
          }

          setBootstrapError(error);
          return;
        }
      }
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [bootstrapVersion]);

  if (bootstrapError) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-background px-6 py-10">
        <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 text-center shadow-sm">
          <h1 className="text-lg font-semibold text-text">Unable to restore your session</h1>
          <p className="mt-2 text-sm leading-6 text-text-soft">
            The server or your connection is temporarily unavailable. Your session has not been cleared.
          </p>
          <button
            type="button"
            className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-primary-hover"
            onClick={() => setBootstrapVersion((current) => current + 1)}
          >
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (!bootstrapDone) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-background px-6">
        <p className="text-sm font-medium text-text-soft" role="status">
          Restoring your session...
        </p>
      </main>
    );
  }

  const payload = getValidTokenPayload();

  if (!payload) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  const user = authSession.getUser();
  const isStudent = String(payload?.role || "").toLowerCase() === "student";
  const requiresPasswordReset = Boolean(user?.password_reset_required);
  const isPasswordResetRoute = location.pathname === "/student/change-password";

  if (isStudent && requiresPasswordReset && !isPasswordResetRoute) {
    return <Navigate to="/student/change-password" replace />;
  }

  if (isStudent && !requiresPasswordReset && isPasswordResetRoute) {
    return <Navigate to="/student/dashboard" replace />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
