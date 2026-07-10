import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { authSession } from "../services/api";
import { authService } from "../services/auth.service";
import { getStoredTokenPayload } from "../utils/auth";

const MAX_BOOTSTRAP_ATTEMPTS = 3;

const wait = (milliseconds) =>
  new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });

function ProtectedRoute() {
  const location = useLocation();
  const [bootstrapDone, setBootstrapDone] = useState(() => Boolean(authSession.getToken()));
  const [bootstrapError, setBootstrapError] = useState(null);
  const [bootstrapVersion, setBootstrapVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (authSession.getToken()) {
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

          if (attempt < MAX_BOOTSTRAP_ATTEMPTS) {
            await wait(attempt * 750);
            continue;
          }

          setBootstrapError(error);
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

  const payload = getStoredTokenPayload();

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
