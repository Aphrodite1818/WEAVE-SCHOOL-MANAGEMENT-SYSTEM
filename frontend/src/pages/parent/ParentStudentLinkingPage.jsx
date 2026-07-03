import { useEffect, useMemo, useState } from "react";
import { Link2, UserRound, X } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { getErrorMessage } from "../../services/api";
import { parentService } from "../../services/parentService";
import { displayName } from "../../utils/user";
import { cleanText } from "../../utils/academicDashboard";
import { useToast } from "../../hooks/useToast";

function asStatus(value) {
  return String(value || "").trim().toLowerCase();
}

function ParentStudentLinkingPage() {
  const [requests, setRequests] = useState([]);
  const [children, setChildren] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLinking, setIsLinking] = useState(false);
  const [admissionNumber, setAdmissionNumber] = useState("");
  const [relationshipType, setRelationshipType] = useState("guardian");
  const [loadError, setLoadError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

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
        await loadPageData();
      } catch (error) {
        if (mounted) setLoadError(getErrorMessage(error, "Failed to load student linking."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadPage();

    return () => {
      mounted = false;
    };
  }, []);

  const handleLinkSubmit = async (event) => {
    event.preventDefault();
    const normalizedAdmissionNumber = admissionNumber.trim().toUpperCase();
    if (!normalizedAdmissionNumber) {
      showWarning("Enter the student's admission number before requesting a link.");
      return;
    }

    setIsLinking(true);

    try {
      await parentService.createStudentLinkRequest({
        admission_number: normalizedAdmissionNumber,
        relationship_type: relationshipType,
      });
      await loadPageData();
      setAdmissionNumber("");
      showSuccess("Link request submitted. The student must approve it before you can view their academic record.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not submit link request."));
    } finally {
      setIsLinking(false);
    }
  };

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
      description="Request access to a child's academic record and track approval status."
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      <section className="grid gap-3 sm:grid-cols-3">
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
          description="awaiting student approval"
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
        <h2 className="section-title">Link a student</h2>
        <p className="mt-1 text-sm text-text-muted">
          Enter the student's admission number and your relationship. The student must approve the request.
        </p>

        <form onSubmit={handleLinkSubmit} className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,0.75fr)_auto] md:items-end">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-text-muted">
              Admission number
            </span>
            <input
              value={admissionNumber}
              onChange={(event) => setAdmissionNumber(event.target.value)}
              placeholder="NHS-2026-12345"
              className="min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm font-medium text-text outline-none transition placeholder:text-text-faint focus:border-primary focus:ring-4 focus:ring-primary/10"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-text-muted">
              Relationship
            </span>
            <select
              value={relationshipType}
              onChange={(event) => setRelationshipType(event.target.value)}
              className="min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm font-medium text-text outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
            >
              <option value="father">Father</option>
              <option value="mother">Mother</option>
              <option value="guardian">Guardian</option>
              <option value="sponsor">Sponsor</option>
              <option value="other">Other</option>
            </select>
          </label>

          <Button type="submit" disabled={isLinking || !admissionNumber.trim()}>
            <Link2 className="h-4 w-4" />
            {isLinking ? "Submitting..." : "Request link"}
          </Button>
        </form>
      </Card>

      <Card className="p-5 sm:p-6">
        <h2 className="section-title">Request status</h2>
        <p className="mt-1 text-sm text-text-muted">Track every parent-student link request you have submitted.</p>

        <div className="mt-4 space-y-3">
          {requests.length === 0 ? (
            <EmptyState
              icon={UserRound}
              title="No link requests yet"
              description="Submitted requests will appear here with their approval status."
            />
          ) : (
            requests.map((request) => (
              <div
                key={request.id}
                className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">
                      {displayName(request.student)}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {request.admission_number_snapshot ||
                        request.student?.admission_number ||
                        "No admission number"}{" "}
                      / {cleanText(request.relationship_type)}
                    </p>
                  </div>
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
            ))
          )}
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <h2 className="section-title">Linked students</h2>
        <p className="mt-1 text-sm text-text-muted">Children currently connected to your parent account.</p>

        <div className="mt-4 space-y-3">
          {children.length === 0 ? (
            <EmptyState
              icon={Link2}
              title="No linked students"
              description="Approved student links will appear here."
            />
          ) : (
            children.map(({ student, link }) => (
              <div
                key={link.id}
                className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">{displayName(student)}</p>
                    <p className="mt-1 text-xs text-text-muted">
                      {cleanText(student.admission_number)} / {cleanText(student.profile_status)}
                    </p>
                  </div>
                  <Badge variant={link.is_primary_contact ? "success" : "default"}>
                    {cleanText(link.relationship_type)}
                  </Badge>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </DashboardLayout>
  );
}

export default ParentStudentLinkingPage;
