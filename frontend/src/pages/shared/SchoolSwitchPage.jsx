import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, Building2, CheckCircle2, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { authSession, getErrorMessage } from "../../services/api";
import { authService } from "../../services/auth.service";
import { membershipService } from "../../services/membershipService";
import { cleanText } from "../../utils/academicDashboard";

const DASHBOARD_PATHS = {
  parent: "/parent/dashboard",
  teacher: "/teacher/dashboard",
};

const usableStatuses = {
  parent: new Set(["active", "read_only"]),
  teacher: new Set(["active"]),
};

const statusVariant = (status) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "active") return "success";
  if (normalized === "read_only") return "warning";
  if (["ended", "suspended", "inactive"].includes(normalized)) return "error";
  return "default";
};

function SchoolLogo({ membership }) {
  const [failed, setFailed] = useState(false);
  const label = membership.tenant_name || "School workspace";

  if (membership.tenant_logo_url && !failed) {
    return (
      <img
        src={membership.tenant_logo_url}
        alt={`${label} logo`}
        className="h-12 w-12 shrink-0 rounded-2xl border border-border/70 bg-surface object-contain p-1.5 shadow-sm"
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary shadow-sm">
      <Building2 className="h-6 w-6" />
    </span>
  );
}

function SchoolSwitchPage({ role }) {
  const navigate = useNavigate();
  const normalizedRole = String(role || "parent").toLowerCase();
  const storedUser = authSession.getUser() || {};
  const [memberships, setMemberships] = useState(() =>
    membershipService.getStoredMemberships()
  );
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [selectingId, setSelectingId] = useState(null);
  const currentMembershipId = useMemo(() => {
    const actorType = String(storedUser?.actor_type || "").toLowerCase();
    return actorType === normalizedRole ? String(storedUser?.id || "") : "";
  }, [normalizedRole, storedUser?.actor_type, storedUser?.id]);

  const loadMemberships = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const response = await membershipService.listMemberships(normalizedRole);
      setMemberships(response.items || []);
    } catch (error) {
      setLoadError(
        getErrorMessage(error, "Could not load your school memberships.")
      );
    } finally {
      setIsLoading(false);
    }
  }, [normalizedRole]);

  useEffect(() => {
    loadMemberships();
  }, [loadMemberships]);

  const handleSelect = async (membership) => {
    const membershipId = String(membership?.membership_id || "");
    if (!membershipId) return;

    if (membershipId === currentMembershipId) {
      navigate(DASHBOARD_PATHS[normalizedRole], { replace: true });
      return;
    }

    setSelectingId(membershipId);
    setLoadError(null);

    try {
      await authService.selectMembership(membershipId, {
        remember: authSession.getRememberPreference?.() ?? true,
      });
      navigate(DASHBOARD_PATHS[normalizedRole], { replace: true });
    } catch (error) {
      setLoadError(
        getErrorMessage(error, "Could not switch to that school workspace.")
      );
    } finally {
      setSelectingId(null);
    }
  };

  return (
    <DashboardLayout
      role={normalizedRole}
      title="School Workspaces"
      description="Choose the school workspace you want to use. Your account stays the same while permissions and records remain isolated per school."
      onboardingModalEnabled={false}
      actions={
        <Button
          type="button"
          variant="outline"
          onClick={loadMemberships}
          disabled={isLoading || Boolean(selectingId)}
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      }
    >
      {loadError ? (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      ) : null}

      {isLoading && memberships.length === 0 ? (
        <LoadingState label="Loading school workspaces..." />
      ) : memberships.length === 0 ? (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={Building2}
            title="No school memberships yet"
            description="Accept a school invitation first. Once the membership is active, the school will appear here."
          />
        </Card>
      ) : (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {memberships.map((membership) => {
            const membershipId = String(membership.membership_id || "");
            const normalizedStatus = String(
              membership.membership_status || "unknown"
            ).toLowerCase();
            const isCurrent = membershipId === currentMembershipId;
            const isUsable = usableStatuses[normalizedRole]?.has(
              normalizedStatus
            );
            const isSelecting = selectingId === membershipId;

            return (
              <Card key={membershipId || membership.tenant_id} className="p-5 sm:p-6">
                <div className="flex h-full flex-col gap-5">
                  <div className="flex min-w-0 items-start gap-3">
                    <SchoolLogo membership={membership} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="min-w-0 break-words text-base font-semibold text-text">
                          {membership.tenant_name || "School workspace"}
                        </h2>
                        {isCurrent ? (
                          <Badge variant="success">Current</Badge>
                        ) : null}
                      </div>
                      <p className="mt-1 text-sm text-text-muted">
                        {normalizedRole === "teacher"
                          ? "Teacher membership"
                          : "Parent membership"}
                      </p>
                    </div>
                    <Badge variant={statusVariant(normalizedStatus)}>
                      {cleanText(normalizedStatus)}
                    </Badge>
                  </div>

                  <div className="rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
                    {isCurrent
                      ? "You are currently working inside this school."
                      : isUsable
                        ? "Open this workspace to view the records and permissions attached to this school."
                        : "This membership is not currently available for workspace access."}
                  </div>

                  <div className="mt-auto">
                    <Button
                      type="button"
                      className="w-full"
                      variant={isCurrent ? "outline" : "primary"}
                      disabled={!isUsable || Boolean(selectingId)}
                      onClick={() => handleSelect(membership)}
                    >
                      {isCurrent ? (
                        <CheckCircle2 className="h-4 w-4" />
                      ) : (
                        <ArrowRight className="h-4 w-4" />
                      )}
                      {isSelecting
                        ? "Switching..."
                        : isCurrent
                          ? "Continue to workspace"
                          : isUsable
                            ? "Open workspace"
                            : "Unavailable"}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </section>
      )}
    </DashboardLayout>
  );
}

export default SchoolSwitchPage;
