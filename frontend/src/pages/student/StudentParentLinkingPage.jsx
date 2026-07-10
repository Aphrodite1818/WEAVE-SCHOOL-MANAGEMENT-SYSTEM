import { useEffect, useMemo, useState } from "react";
import { Check, Link2, UserRound, X } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { getErrorMessage } from "../../services/api";
import { studentService } from "../../services/studentService";
import { displayName } from "../../utils/user";
import { cleanText } from "../../utils/academicDashboard";
import { asStatus, statusVariant } from "./studentPageUtils";
import { useToast } from "../../hooks/useToast";

function StudentParentLinkingPage() {
  const [parentLinks, setParentLinks] = useState([]);
  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionId, setActionId] = useState(null);
  const { showSuccess, showError } = useToast();

  const loadParentLinks = async () => {
    const [linksResponse, requestsResponse] = await Promise.all([
      studentService.getMyParentLinks(),
      studentService.getMyParentLinkRequests(),
    ]);
    setParentLinks(linksResponse?.items || []);
    setRequests(requestsResponse?.items || []);
  };

  useEffect(() => {
    let mounted = true;

    async function loadPage() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const [linksResponse, requestsResponse] = await Promise.all([
          studentService.getMyParentLinks(),
          studentService.getMyParentLinkRequests(),
        ]);
        if (!mounted) return;
        setParentLinks(linksResponse?.items || []);
        setRequests(requestsResponse?.items || []);
      } catch (error) {
        if (mounted) setLoadError(getErrorMessage(error, "Failed to load parent linking."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadPage();

    return () => {
      mounted = false;
    };
  }, []);

  const handleRequestResponse = async (requestId, action) => {
    setActionId(requestId);

    try {
      await studentService.respondToParentLinkRequest(requestId, { action });
      await loadParentLinks();
      showSuccess(action === "approve" ? "Parent link approved." : "Parent link declined.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not update parent link request."));
    } finally {
      setActionId(null);
    }
  };

  const summary = useMemo(() => {
    const pending = requests.filter((request) => asStatus(request.status) === "pending");
    const declined = requests.filter((request) => ["rejected", "declined"].includes(asStatus(request.status)));
    return { pending, declined };
  }, [requests]);

  if (isLoading) {
    return (
      <DashboardLayout role="student" title="Parent Linking">
        <LoadingState label="Loading parent links..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="student"
      title="Parent Linking"
      description="Manage who can view your academic record and receive school updates."
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard
          label="Active Links"
          value={parentLinks.length}
          description="approved contacts"
          icon={Link2}
          tone={parentLinks.length > 0 ? "success" : "warning"}
          compact
        />
        <StatCard
          label="Pending Requests"
          value={summary.pending.length}
          description="waiting for your decision"
          icon={UserRound}
          tone={summary.pending.length > 0 ? "warning" : "primary"}
          compact
        />
        <StatCard
          label="Declined"
          value={summary.declined.length}
          description="rejected requests"
          icon={X}
          tone={summary.declined.length > 0 ? "error" : "primary"}
          compact
        />
      </section>

      <Card className="p-4 sm:p-5 md:p-6">
        <h2 className="section-title">Pending requests</h2>
        <p className="mt-1 text-sm text-text-muted">
          These parents have asked to be linked to your profile. Review before approving.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {summary.pending.length === 0 ? (
            <div className="sm:col-span-2 xl:col-span-3">
              <EmptyState
                icon={UserRound}
                title="No pending requests"
                description="New parent access requests will appear here for approval."
              />
            </div>
          ) : (
            summary.pending.map((request) => (
              <div key={request.id} className="rounded-[1.25rem] border border-border bg-surface px-4 py-4">
                <div className="flex h-full flex-col gap-4">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-sm font-bold text-primary">
                      {displayName(request.parent).slice(0, 2).toUpperCase()}
                    </span>
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-text">
                        {displayName(request.parent)} · {cleanText(request.relationship_type)}
                      </p>
                      <p className="mt-1 break-words text-xs text-text-muted">
                        {request.parent?.email || "No email provided"}
                      </p>
                    </div>
                  </div>
                  <div className="mt-auto grid gap-2 grid-cols-2">
                    <Button
                      type="button"
                      onClick={() => handleRequestResponse(request.id, "approve")}
                      disabled={actionId === request.id}
                    >
                      <Check className="h-4 w-4" />
                      {actionId === request.id ? "Saving..." : "Approve"}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleRequestResponse(request.id, "reject")}
                      disabled={actionId === request.id}
                    >
                      Decline
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      <Card className="p-4 sm:p-5 md:p-6">
        <h2 className="section-title">Linked contacts</h2>
        <p className="mt-1 text-sm text-text-muted">People currently connected to your academic record.</p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {parentLinks.length === 0 ? (
            <div className="sm:col-span-2 xl:col-span-3">
              <EmptyState
                icon={Link2}
                title="No linked contacts"
                description="Approved parent contacts will appear here."
              />
            </div>
          ) : (
            parentLinks.map((link) => (
              <div key={link.id} className="rounded-[1.25rem] border border-border bg-surface px-4 py-4">
                <div className="flex h-full flex-col gap-4">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-sm font-bold text-primary">
                      {displayName(link.parent).slice(0, 2).toUpperCase()}
                    </span>
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-text">
                        {displayName(link.parent)} · {cleanText(link.relationship_type)}
                      </p>
                      <p className="mt-1 break-words text-xs text-text-muted">
                        {link.parent?.email || "No email provided"}
                      </p>
                    </div>
                  </div>
                  <div className="mt-auto">
                    <Badge variant={statusVariant("active")}>
                      {link.is_primary_contact ? "Primary contact" : "Active"}
                    </Badge>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </DashboardLayout>
  );
}

export default StudentParentLinkingPage;
