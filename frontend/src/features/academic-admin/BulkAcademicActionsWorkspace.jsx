import {
  Archive,
  CheckCircle2,
  LockKeyhole,
  RotateCcw,
  Send,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { bulkAcademicService } from "../../services/bulkAcademicService";
import {
  SelectControl,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  item?.display_name ||
  [item?.academic_level_name, item?.department_name, item?.arm_label].filter(Boolean).join(" ") ||
  "Unnamed class";

const RESULT_ACTIONS = [
  {
    id: "submit",
    title: "Submit all draft results",
    description:
      "Move every complete draft result in the selected class to submitted. Incomplete rows are skipped.",
    icon: Send,
  },
  {
    id: "approve",
    title: "Approve all submitted results",
    description:
      "Approve submitted results that already have a calculated grade.",
    icon: CheckCircle2,
  },
  {
    id: "lock",
    title: "Finalize all approved results",
    description:
      "Lock approved results for report-card generation. Publication belongs to report cards.",
    icon: LockKeyhole,
  },
  {
    id: "reopen",
    title: "Reopen locked results",
    description:
      "Return locked results to draft for correction and mark affected report cards as outdated.",
    icon: RotateCcw,
    requiresReason: true,
  },
];

const REPORT_CARD_ACTIONS = [
  {
    id: "publish",
    title: "Publish all draft report cards",
    description:
      "Publish every valid, current draft report card in the selected class and period.",
    icon: Send,
  },
  {
    id: "archive",
    title: "Archive class report cards",
    description:
      "Archive current report cards while keeping their history available.",
    icon: Archive,
    requiresReason: true,
  },
  {
    id: "reopen",
    title: "Reopen archived report cards",
    description:
      "Return manually archived current versions to draft. Superseded historical versions remain read-only.",
    icon: RotateCcw,
    requiresReason: true,
  },
];

function BulkAcademicActionsWorkspace({
  domain,
  onContextChange,
  paidAccess = false,
}) {
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [classes, setClasses] = useState([]);
  const [filters, setFilters] = useState({
    class_id: "",
    academic_session_id: "",
    academic_term_id: "",
  });
  const [pendingAction, setPendingAction] = useState(null);
  const [reason, setReason] = useState("");
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { showSuccess, showError, showWarning } = useToast();

  const loadContext = useCallback(async () => {
    setLoading(true);
    try {
      const [sessionResponse, termResponse, classResponse] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        classService.getClasses({ limit: 100, activeOnly: false }),
      ]);
      const nextSessions = asItems(sessionResponse);
      const nextTerms = asItems(termResponse);
      const nextClasses = asItems(classResponse);
      const currentSession =
        nextSessions.find((item) => item.is_current) || null;
      const currentTerm = nextTerms.find((item) => item.is_current) || null;
      setSessions(nextSessions);
      setTerms(nextTerms);
      setClasses(nextClasses);
      setFilters((current) => ({
        class_id: current.class_id || nextClasses[0]?.id || "",
        academic_session_id:
          current.academic_session_id ||
          currentSession?.id ||
          nextSessions[0]?.id ||
          "",
        academic_term_id:
          current.academic_term_id ||
          currentTerm?.id ||
          nextTerms[0]?.id ||
          "",
      }));
      onContextChange?.({ currentSession, currentTerm });
    } catch (error) {
      showError(
        getErrorMessage(error, "Could not load bulk action context."),
      );
    } finally {
      setLoading(false);
    }
  }, [onContextChange, showError]);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  const actions =
    domain === "results" ? RESULT_ACTIONS : REPORT_CARD_ACTIONS;
  const sessionOptions = sessions.map((item) => ({
    value: item.id,
    label: item.name,
  }));
  const termOptions = terms
    .filter(
      (item) =>
        !filters.academic_session_id ||
        item.academic_session_id === filters.academic_session_id,
    )
    .map((item) => ({
      value: item.id,
      label: String(item.name || "").replaceAll("_", " "),
    }));
  const classOptions = classes.map((item) => ({
    value: item.id,
    label: classLabel(item),
  }));
  const selectedClass = classes.find(
    (item) => item.id === filters.class_id,
  );
  const selectedSession = sessions.find(
    (item) => item.id === filters.academic_session_id,
  );
  const selectedTerm = terms.find(
    (item) => item.id === filters.academic_term_id,
  );

  const contextReady = Boolean(
    filters.class_id &&
      filters.academic_session_id &&
      filters.academic_term_id,
  );

  const modalDescription = useMemo(() => {
    if (!pendingAction) return "";
    return `${pendingAction.description} Scope: ${classLabel(selectedClass)} · ${selectedSession?.name || "No session"} · ${String(selectedTerm?.name || "No term").replaceAll("_", " ")}.`;
  }, [pendingAction, selectedClass, selectedSession, selectedTerm]);

  const runAction = async () => {
    if (!paidAccess) {
      showWarning(
        "Bulk academic operations require an active paid subscription.",
      );
      return;
    }
    if (!pendingAction || !contextReady) return;
    if (pendingAction.requiresReason && reason.trim().length < 3) {
      showWarning("Enter a reason of at least 3 characters.");
      return;
    }

    setSaving(true);
    setSummary(null);
    try {
      const base = {
        ...filters,
        ...(pendingAction.requiresReason
          ? { reason: reason.trim() }
          : {}),
      };
      let response;
      if (domain === "results") {
        if (pendingAction.id === "reopen") {
          response = await bulkAcademicService.reopenClassResults({
            ...base,
            confirmation: "BULK_REOPEN_RESULTS",
          });
        } else {
          response = await bulkAcademicService.transitionClassResults({
            ...base,
            target_status: {
              submit: "submitted",
              approve: "approved",
              lock: "locked",
            }[pendingAction.id],
            confirmation: "BULK_TRANSITION_RESULTS",
          });
        }
      } else if (pendingAction.id === "publish") {
        response = await bulkAcademicService.publishClassReportCards({
          ...base,
          confirmation: "BULK_PUBLISH_REPORT_CARDS",
        });
      } else if (pendingAction.id === "archive") {
        response = await bulkAcademicService.archiveClassReportCards({
          ...base,
          confirmation: "BULK_ARCHIVE_REPORT_CARDS",
        });
      } else {
        response = await bulkAcademicService.reopenClassReportCards({
          ...base,
          confirmation: "BULK_REOPEN_REPORT_CARDS",
        });
      }

      setSummary(response);
      showSuccess(
        `${response?.processed || 0} record${
          response?.processed === 1 ? "" : "s"
        } updated.`,
      );
      setPendingAction(null);
      setReason("");
    } catch (error) {
      showError(
        getErrorMessage(error, "Could not complete the bulk action."),
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {!paidAccess ? (
        <div className="rounded-2xl border border-info/30 bg-info-soft px-4 py-3 text-sm font-medium text-info">
          Bulk result and report-card actions are available on paid plans. Individual academic operations remain available according to the current plan.
        </div>
      ) : null}

      <WorkspacePanel
        title={
          domain === "results"
            ? "Bulk result actions"
            : "Bulk report-card actions"
        }
        description="Choose one class and academic period, then apply one lifecycle action to all eligible records. Ineligible records are skipped rather than silently changed."
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <SelectControl
            label="Class"
            value={filters.class_id}
            onChange={(value) =>
              setFilters((current) => ({
                ...current,
                class_id: value,
              }))
            }
            options={classOptions}
            required
          />
          <SelectControl
            label="Academic session"
            value={filters.academic_session_id}
            onChange={(value) => {
              const nextTerm =
                terms.find(
                  (item) =>
                    item.academic_session_id === value && item.is_current,
                ) ||
                terms.find(
                  (item) => item.academic_session_id === value,
                );
              setFilters((current) => ({
                ...current,
                academic_session_id: value,
                academic_term_id: nextTerm?.id || "",
              }));
            }}
            options={sessionOptions}
            required
          />
          <SelectControl
            label="Academic term"
            value={filters.academic_term_id}
            onChange={(value) =>
              setFilters((current) => ({
                ...current,
                academic_term_id: value,
              }))
            }
            options={termOptions}
            required
          />
        </div>
      </WorkspacePanel>

      <div className="grid gap-3 lg:grid-cols-2">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <WorkspacePanel
              key={action.id}
              title={action.title}
              description={action.description}
            >
              <div className="flex items-center justify-between gap-4">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Icon className="h-5 w-5" />
                </span>
                <Button
                  type="button"
                  variant={
                    action.id === "archive" || action.id === "reopen"
                      ? "outline"
                      : "default"
                  }
                  disabled={loading || !contextReady || !paidAccess}
                  title={
                    paidAccess
                      ? "Review this class-wide action"
                      : "Requires an active paid subscription"
                  }
                  onClick={() => {
                    setPendingAction(action);
                    setReason("");
                  }}
                >
                  {paidAccess ? "Review action" : "Paid plan required"}
                </Button>
              </div>
            </WorkspacePanel>
          );
        })}
      </div>

      {summary ? (
        <WorkspacePanel
          title="Last bulk action result"
          description="The backend returns partial-success details so skipped records remain visible."
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryValue label="Matched" value={summary.matched || 0} />
            <SummaryValue label="Updated" value={summary.processed || 0} />
            <SummaryValue
              label="Skipped"
              value={summary.skipped?.length || 0}
            />
          </div>
          {summary.skipped?.length ? (
            <div className="mt-4 space-y-2 text-sm text-text-muted">
              {summary.skipped.slice(0, 10).map((item) => (
                <p
                  key={item.id}
                  className="rounded-xl bg-surface-muted/40 px-3 py-2"
                >
                  {item.id}: {item.reason}
                </p>
              ))}
            </div>
          ) : null}
        </WorkspacePanel>
      ) : null}

      <Modal
        open={Boolean(pendingAction)}
        title={pendingAction?.title || "Confirm bulk action"}
        description={modalDescription}
        onClose={() => {
          if (!saving) {
            setPendingAction(null);
            setReason("");
          }
        }}
        closeOnOverlay={!saving}
        footer={(
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={saving}
              onClick={() => setPendingAction(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={saving || !paidAccess}
              onClick={runAction}
            >
              {saving ? "Applying..." : "Apply to eligible records"}
            </Button>
          </div>
        )}
      >
        {pendingAction?.requiresReason ? (
          <label className="block text-sm font-semibold text-text-soft">
            <span className="mb-1.5 block">Reason</span>
            <textarea
              className="input-base min-h-24 resize-y"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={1000}
              placeholder="Explain why this class-wide lifecycle change is needed"
            />
          </label>
        ) : (
          <p className="text-sm text-text-muted">
            Only records in the correct current lifecycle stage will be changed.
          </p>
        )}
      </Modal>
    </div>
  );
}

function SummaryValue({ label, value }) {
  return (
    <div className="rounded-xl border border-border px-4 py-3">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold text-text">{value}</p>
    </div>
  );
}

export default BulkAcademicActionsWorkspace;
