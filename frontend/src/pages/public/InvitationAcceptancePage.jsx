import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock3,
  GraduationCap,
  LogIn,
  TriangleAlert,
} from "lucide-react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import AuthLayout from "../../components/layout/AuthLayout";
import Button from "../../components/ui/Button";
import { queueInitialTour } from "../../features/guides/workspaceTourState";
import { authSession, parseApiError } from "../../services/api";
import { authService } from "../../services/auth.service";
import { guideService } from "../../services/guideService";
import { parentService } from "../../services/parentService";
import { teacherService } from "../../services/teacherService";
import { getValidTokenPayload } from "../../utils/auth";

const ROLE_CONFIG = {
  parent: {
    title: "Parent invitation",
    description:
      "Review the student details and request access through your parent account.",
    accountActor: "parent_account",
    membershipActor: "parent",
    schoolPath: "/parent/schools",
    registerPath: "/parent/register",
  },
  teacher: {
    title: "Teacher invitation",
    description:
      "Accept the invitation to create or activate your teacher membership for this school.",
    accountActor: "teacher_account",
    membershipActor: "teacher",
    schoolPath: "/teacher/schools",
    registerPath: "/teacher/register",
  },
};

function StateMessage({ type = "info", title, children }) {
  const Icon =
    type === "error"
      ? TriangleAlert
      : type === "warning"
        ? Clock3
        : CheckCircle2;
  const styles =
    type === "error"
      ? "border-error/20 bg-error-soft text-error"
      : type === "warning"
        ? "border-warning/30 bg-warning-soft text-amber-800"
        : "border-primary/20 bg-primary-subtle text-primary";

  return (
    <div className={`rounded-2xl border px-4 py-4 text-sm ${styles}`}>
      <div className="flex gap-3">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          {title ? <p className="font-semibold">{title}</p> : null}
          <div className={title ? "mt-1 leading-6" : "leading-6"}>{children}</div>
        </div>
      </div>
    </div>
  );
}

function InvitationAcceptancePage({ role }) {
  const { token = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.parent;
  const [context, setContext] = useState(null);
  const [contextStatus, setContextStatus] = useState(
    token ? "loading" : "ready",
  );
  const [isAccepting, setIsAccepting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const payload = getValidTokenPayload();
  const storedUser = authSession.getUser() || {};
  const actorType = String(
    payload?.actor_type || storedUser?.actor_type || "",
  ).toLowerCase();
  const isAuthenticated = Boolean(payload && authSession.getToken());
  const isCorrectAccount =
    actorType === config.accountActor || actorType === config.membershipActor;
  const returnTo = `${location.pathname}${location.search}`;
  const loginPath = `/login?returnTo=${encodeURIComponent(returnTo)}`;
  const registerPath = `${config.registerPath}?returnTo=${encodeURIComponent(returnTo)}`;

  useEffect(() => {
    if (!token) return undefined;
    let mounted = true;

    async function loadContext() {
      setContextStatus("loading");
      setError(null);
      try {
        const result =
          role === "parent"
            ? await parentService.getInvitationContext(token)
            : await teacherService.getInvitationContext(token);
        if (!mounted) return;
        setContext(result);
        setContextStatus(String(result?.status || "ready").toLowerCase());
      } catch (err) {
        if (!mounted) return;
        const apiError = parseApiError(
          err,
          `Could not load this ${role} invitation.`,
        );
        setError(apiError.message);
        setContextStatus("error");
      }
    }

    loadContext();
    return () => {
      mounted = false;
    };
  }, [role, token]);

  const invitationAvailable = useMemo(() => {
    if (!token) return false;
    return ["pending", "ready", "valid"].includes(contextStatus);
  }, [contextStatus, token]);

  const handleDifferentAccount = async () => {
    await authService.logout();
    navigate(loginPath, { replace: true });
  };

  const handleAccept = async (event) => {
    event.preventDefault();
    if (!isAuthenticated || !isCorrectAccount || !invitationAvailable) return;

    const admissionNumber = String(context?.admission_number || "")
      .trim()
      .toUpperCase();
    if (role === "parent" && !admissionNumber) {
      setError(
        "The invitation is missing its student admission reference. Ask the school to resend it.",
      );
      return;
    }

    setIsAccepting(true);
    setError(null);

    try {
      const result =
        role === "parent"
          ? await parentService.acceptInvitation(token, admissionNumber)
          : await teacherService.acceptInvitation(token);
      setSuccess(result);

      // Teacher/parent guide state is account-global. Queue the first-workspace
      // invitation at the membership boundary, but consume it only after legal
      // and profile onboarding are complete and a tenant dashboard is entered.
      try {
        await queueInitialTour(role, true, guideService);
      } catch {
        // Membership acceptance is authoritative and must not fail because an
        // optional guide-state write is temporarily unavailable.
      }
    } catch (err) {
      const apiError = parseApiError(err, "Could not accept this invitation.");
      setError(apiError.message);
    } finally {
      setIsAccepting(false);
    }
  };

  const status = String(context?.status || contextStatus || "").toLowerCase();
  const expiredOrUnavailable = ["expired", "revoked", "accepted", "error"].includes(
    status,
  );
  const recommendedAction = String(context?.recommended_action || "").toLowerCase();
  const authActionCopy =
    recommendedAction === "register"
      ? {
          primaryLabel: `Create ${role} account first`,
          primaryPath: registerPath,
        }
      : {
          primaryLabel: "Log in to accept",
          primaryPath: loginPath,
        };

  return (
    <AuthLayout
      title={config.title}
      description={config.description}
      stepLabel="School invitation"
      footer={
        <p className="mt-7 text-center text-sm text-text-soft">
          Need help? Contact the school that sent the invitation.
        </p>
      }
    >
      <div className="space-y-4">
        {!token ? (
          <StateMessage type="error" title="Missing invitation token">
            Open the complete link from the latest invitation email.
          </StateMessage>
        ) : null}

        {contextStatus === "loading" ? (
          <StateMessage>Checking the invitation...</StateMessage>
        ) : null}

        {role === "parent" && context && !expiredOrUnavailable ? (
          <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
            <div className="flex items-start gap-3">
              {context.tenant_logo_url ? (
                <img
                  src={context.tenant_logo_url}
                  alt={`${context.tenant_name} logo`}
                  className="h-11 w-11 shrink-0 rounded-2xl border border-border/70 bg-surface object-contain p-1"
                />
              ) : (
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Building2 className="h-5 w-5" />
                </span>
              )}
              <div className="min-w-0">
                <p className="break-words text-sm font-semibold text-text">
                  {context.tenant_name}
                </p>
                <p className="mt-1 flex items-center gap-1.5 text-sm text-text-muted">
                  <GraduationCap className="h-4 w-4" />
                  {context.student_display_name}
                </p>
                <p className="mt-1 text-xs font-semibold text-text-soft">
                  Admission number: {context.admission_number || context.admission_number_hint}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  Relationship: {String(context.relationship_type || "guardian").replaceAll("_", " ")}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {role === "teacher" && context && !expiredOrUnavailable && !success ? (
          <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
            <div className="flex items-start gap-3">
              {context.tenant_logo_url ? (
                <img
                  src={context.tenant_logo_url}
                  alt={`${context.tenant_name} logo`}
                  className="h-11 w-11 shrink-0 rounded-2xl border border-border/70 bg-surface object-contain p-1"
                />
              ) : (
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Building2 className="h-5 w-5" />
                </span>
              )}
              <div>
                <p className="text-sm font-semibold text-text">{context.tenant_name}</p>
                <p className="mt-1 text-sm leading-6 text-text-muted">
                  Teacher membership invitation for {context.invited_email}.
                </p>
                {context.staff_id ? (
                  <p className="mt-1 text-xs font-semibold text-text-soft">
                    Staff ID: {context.staff_id}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {expiredOrUnavailable && !error ? (
          <StateMessage
            type={status === "accepted" ? "info" : "warning"}
            title={
              status === "accepted"
                ? "Invitation already accepted"
                : "Invitation unavailable"
            }
          >
            {status === "accepted"
              ? "Open your School Workspaces page to continue."
              : "Request a new invitation from the school administrator."}
          </StateMessage>
        ) : null}

        {error ? (
          <StateMessage type="error">{error}</StateMessage>
        ) : null}

        {success ? (
          <>
            <StateMessage title={role === "parent" ? "Request submitted" : "Membership accepted"}>
              {role === "parent"
                ? "The parent link is pending approval from the student or school administrator."
                : "The school membership has been added to your teacher account."}
            </StateMessage>
            <Button
              type="button"
              className="w-full"
              onClick={() => navigate(config.schoolPath, { replace: true })}
            >
              Open school workspaces
              <ArrowRight className="h-4 w-4" />
            </Button>
          </>
        ) : null}

        {!success && invitationAvailable && !isAuthenticated && recommendedAction === "contact_school" ? (
          <StateMessage type="warning" title="Contact the school">
            This invited email is already connected to a different account type. Ask the school to resend the invitation to the correct {role} email.
          </StateMessage>
        ) : null}

        {!success && invitationAvailable && !isAuthenticated && recommendedAction !== "contact_school" ? (
          <Link to={authActionCopy.primaryPath} className="block">
            <Button type="button" className="w-full">
              {recommendedAction === "register" ? null : <LogIn className="h-4 w-4" />}
              {authActionCopy.primaryLabel}
            </Button>
          </Link>
        ) : null}

        {!success && invitationAvailable && isAuthenticated && !isCorrectAccount ? (
          <div className="space-y-3">
            <StateMessage type="warning" title={`Use a ${role} account`}>
              The current session belongs to a different account type.
            </StateMessage>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={handleDifferentAccount}
            >
              Log in with another account
            </Button>
          </div>
        ) : null}

        {!success && invitationAvailable && isAuthenticated && isCorrectAccount ? (
          <form onSubmit={handleAccept} className="space-y-4">
            {role === "parent" ? (
              <p className="rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm leading-6 text-text-muted">
                The student reference is already attached to this invitation. Review the details above, then submit the access request.
              </p>
            ) : null}
            <Button
              type="submit"
              className="w-full"
              disabled={
                isAccepting ||
                (role === "parent" && !context?.admission_number)
              }
            >
              {isAccepting ? "Accepting invitation..." : "Accept invitation"}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
        ) : null}
      </div>
    </AuthLayout>
  );
}

export default InvitationAcceptancePage;
