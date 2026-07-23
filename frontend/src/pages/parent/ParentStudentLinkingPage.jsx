import { useEffect, useMemo, useState } from "react";
import { Link2, MailCheck, UserRound, X } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { getErrorMessage } from "../../services/api";
import { parentService } from "../../services/parentService";
import { displayName } from "../../utils/user";
import { cleanText } from "../../utils/academicDashboard";

function asStatus(value) {
  return String(value || "").trim().toLowerCase();
}

function ParentStudentLinkingPage() {
  const [requests, setRequests] = useState([]);
  const [children, setChildren] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const loadPageData = async () => {
    const [studentsResponse, requestsResponse] = await Promise.all([
      parentService.getMyStudents(),
      parentService.getMyStudentLinkRequests(),
    ]);
    setChildren(studentsResponse?.items || []);
    setRequests(requestsResponse?.items || []);
  };

  useEffect(() => {
    let mounted = true;

    async function loadPage() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const [studentsResponse, requestsResponse] = await Promise.all([
          parentService.getMyStudents(),
          parentService.getMyStudentLinkRequests(),
        ]);
        if (!mounted) return;
        setChildren(studentsResponse?.items || []);
        setRequests(requestsResponse?.items || []);
      } catch (error) {
        if (mounted) {
          setLoadError(getErrorMessage(error, "Failed to load student linking."));
        }
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadPage();

    return () => {
      mounted = false;
    };
  }, []);

  const summary = useMemo(() => {
    const pending = requests.filter((request) => asStatus(request.status) === "pending");
    const approved = requests.filter((request) => asStatus(request.status) === "approved");
    const declined = requests.filter((request) => ["rejected", "declined"].includes(asStatus(request.status)));
    return { pending, approved, declined };
  }, [requests]);

  if (isLoading) {
    return (
      <DashboardLayout role="parent" title="Student Linking">
        <LoadingState label="Loading student linking..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="parent"
      title="Student Linking"
      description="Track school-issued invitations and the approval status for children connected to this school membership."
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard
          label="Linked Students"
          value={children.length}
          description="approved children"
          icon={Link2}
          tone={children.length > 0 ? "success" : "warning"}
          compact
        />
        <StatCard
          label="Pending Requests"
          value={summary.pending.length}
          description="awaiting approval"
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

      <Card className="p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
            <MailCheck className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h2 className="section-title">Invitation-based access</h2>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              A school administrator must invite your email for a specific student. Open the latest invitation email, log in with this parent account, and accept the invitation. The request will appear below while it waits for student or administrator approval.
            </p>
          </div>
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <h2 className="section-title">Request status</h2>
        <p className="mt-1 text-sm text-text-muted">Track link requests created from parent invitation emails.</p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {requests.length === 0 ? (
            <div className="sm:col-span-2 xl:col-span-3">
              <EmptyState
                icon={UserRound}
                title="No invitation requests yet"
                description="Accepted parent invitations will appear here with their approval status."
              />
            </div>
          ) : (
            requests.map((request) => (
              <div
                key={request.id}
                className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-4"
              >
                <div className="flex h-full flex-col gap-4">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-text">
                      {request.student_name || displayName(request.student)}
                    </p>
                    <p className="mt-1 break-words text-xs text-text-muted">
                      {request.admission_number_snapshot ||
                        request.student?.admission_number ||
                        "No admission number"}{" "}
                      / {cleanText(request.relationship_type)}
                    </p>
                  </div>
                  <div className="mt-auto">
                    <Badge
                      variant={
                        request.status === "approved"
                          ? "success"
                          : request.status === "rejected"
                            ? "error"
                            : "warning"
                      }
                    >
                      {request.status}
                    </Badge>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <h2 className="section-title">Linked students</h2>
        <p className="mt-1 text-sm text-text-muted">Children currently connected to this school membership.</p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {children.length === 0 ? (
            <div className="sm:col-span-2 xl:col-span-3">
              <EmptyState
                icon={Link2}
                title="No linked students"
                description="Students will appear after an invitation request is approved."
              />
            </div>
          ) : (
            children.map((entry) => {
              const student = entry.student || entry;
              const link = entry.link || entry.parent_link || {};
              return (
                <div
                  key={link.id || student.id}
                  className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-4"
                >
                  <div className="flex h-full flex-col gap-4">
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold text-text">{displayName(student)}</p>
                      <p className="mt-1 break-words text-xs text-text-muted">
                        {cleanText(student.admission_number)} / {cleanText(student.profile_status || student.status)}
                      </p>
                    </div>
                    <div className="mt-auto">
                      <Badge variant={link.is_primary_contact ? "success" : "default"}>
                        {cleanText(link.relationship_type || "linked")}
                      </Badge>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>
    </DashboardLayout>
  );
}

export default ParentStudentLinkingPage;
