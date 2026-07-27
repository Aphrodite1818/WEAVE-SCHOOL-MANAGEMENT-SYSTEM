import { CheckCircle2, FileText, RefreshCw, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { reportCardService } from "../../services/reportCardService";
import { SelectControl, WorkspacePanel } from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || "Unnamed class";

const studentLabel = (item) =>
  `${item?.student_name || item?.admission_number || "Student"}${
    item?.admission_number ? ` · ${item.admission_number}` : ""
  }`;

const listTabs = ["draft", "published", "outdated", "archived"];

function ReportCardsWorkspace({ activeTab, onContextChange }) {
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [classes, setClasses] = useState([]);
  const [overview, setOverview] = useState(null);
  const [cards, setCards] = useState([]);
  const [filters, setFilters] = useState({
    class_id: "",
    academic_session_id: "",
    academic_term_id: "",
  });
  const [generationTarget, setGenerationTarget] = useState("class");
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [generationSummary, setGenerationSummary] = useState(null);
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessionResponse, termResponse, classResponse] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        classService.getClasses({ limit: 100, activeOnly: false }),
      ]);
      const nextSessions = asItems(sessionResponse);
      const nextTerms = asItems(termResponse);
      const nextClasses = asItems(classResponse);
      const currentSession = nextSessions.find((item) => item.is_current) || null;
      const currentTerm = nextTerms.find((item) => item.is_current) || null;

      setSessions(nextSessions);
      setTerms(nextTerms);
      setClasses(nextClasses);
      setFilters((current) => ({
        class_id: current.class_id || nextClasses[0]?.id || "",
        academic_session_id:
          current.academic_session_id || currentSession?.id || nextSessions[0]?.id || "",
        academic_term_id:
          current.academic_term_id || currentTerm?.id || "",
      }));
      onContextChange?.({ currentSession, currentTerm });
    } catch (requestError) {
      const message = getErrorMessage(requestError, "Could not load report-card setup.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [onContextChange, showError]);

  const loadPageData = useCallback(async () => {
    if (!filters.class_id || !filters.academic_session_id || !filters.academic_term_id) {
      setOverview(null);
      setCards([]);
      return;
    }
    try {
      if (["overview", "ready", "generate"].includes(activeTab)) {
        const response = await reportCardService.getClassOverview(filters);
        setOverview(response);
        setCards([]);
        return;
      }
      const params = { ...filters, limit: 100 };
      if (activeTab === "draft") params.status = "draft";
      if (activeTab === "published") params.status = "published";
      if (activeTab === "archived") params.status = "archived";
      if (activeTab === "outdated") params.is_outdated = true;
      const response = await reportCardService.listAdminReportCards(params);
      setCards(asItems(response));
      setOverview(null);
    } catch (requestError) {
      setOverview(null);
      setCards([]);
      showError(getErrorMessage(requestError, "Could not load this report-card page."));
    }
  }, [activeTab, filters, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadPageData();
  }, [loadPageData]);

  useEffect(() => {
    setGenerationSummary(null);
    if (activeTab !== "generate") setSelectedStudentId("");
  }, [activeTab]);

  const sessionOptions = useMemo(
    () => sessions.map((item) => ({ value: item.id, label: item.name })),
    [sessions],
  );
  const termOptions = useMemo(
    () =>
      terms
        .filter(
          (item) =>
            !filters.academic_session_id ||
            item.academic_session_id === filters.academic_session_id,
        )
        .map((item) => ({
          value: item.id,
          label: String(item.name || "").replaceAll("_", " "),
        })),
    [filters.academic_session_id, terms],
  );
  const classOptions = useMemo(
    () => classes.map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );

  const selectedClass = classes.find((item) => item.id === filters.class_id);
  const selectedSession = sessions.find(
    (item) => item.id === filters.academic_session_id,
  );
  const selectedTerm = terms.find((item) => item.id === filters.academic_term_id);
  const rows = overview?.items || [];
  const readyRows = rows.filter(
    (item) => item.expected_count > 0 && item.submitted_count >= item.expected_count,
  );
  const selectedStudent = rows.find((item) => item.student_id === selectedStudentId);
  const selectedStudentReady = Boolean(
    selectedStudent &&
      selectedStudent.expected_count > 0 &&
      selectedStudent.submitted_count >= selectedStudent.expected_count,
  );

  const resetGenerationState = () => {
    setSelectedStudentId("");
    setGenerationSummary(null);
  };

  const contextSummary = (
    <div className="flex flex-col gap-2 rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted sm:flex-row sm:items-center sm:justify-between">
      <span>
        <span className="font-semibold text-text">Selected report context:</span>{" "}
        {classLabel(selectedClass)} · {selectedSession?.name || "No session"} ·{" "}
        {String(selectedTerm?.name || "No term").replaceAll("_", " ")}
      </span>
      <Button type="button" size="small" variant="outline" onClick={loadPageData}>
        <RefreshCw className="h-4 w-4" /> Refresh
      </Button>
    </div>
  );

  const contextPanel = (
    <WorkspacePanel
      title="Report-card context"
      description="Choose the class and academic period once. Every report-card page uses this context until you change it here."
      actions={
        <Button type="button" size="small" variant="outline" onClick={loadPageData}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <SelectControl
          label="Class"
          value={filters.class_id}
          onChange={(value) => {
            setFilters((current) => ({ ...current, class_id: value }));
            resetGenerationState();
          }}
          options={classOptions}
          required
        />
        <SelectControl
          label="Academic session"
          value={filters.academic_session_id}
          onChange={(value) => {
            const nextTerm = terms.find(
              (item) => item.academic_session_id === value && item.is_current,
            );
            setFilters((current) => ({
              ...current,
              academic_session_id: value,
              academic_term_id:
                nextTerm?.id ||
                terms.find((item) => item.academic_session_id === value)?.id ||
                "",
            }));
            resetGenerationState();
          }}
          options={sessionOptions}
          required
        />
        <SelectControl
          label="Academic term"
          value={filters.academic_term_id}
          onChange={(value) => {
            setFilters((current) => ({ ...current, academic_term_id: value }));
            resetGenerationState();
          }}
          options={termOptions}
          required
        />
      </div>
    </WorkspacePanel>
  );

  const overviewPanel = (
    <WorkspacePanel
      title="Report-card overview"
      description="A report card can be generated only when every expected subject result is locked."
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Students", rows.length],
          ["Ready", readyRows.length],
          ["Incomplete", rows.length - readyRows.length],
          ["Generated", rows.filter((item) => item.report_card_id).length],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
            <p className="mt-2 text-xl font-semibold text-text">{value}</p>
          </div>
        ))}
      </div>
    </WorkspacePanel>
  );

  const readinessPanel = (
    <WorkspacePanel
      title="Student readiness"
      description="Review which students have every expected result locked before generation."
    >
      {rows.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
          No enrolled students were found for the selected class and session.
        </p>
      ) : (
        <div className="space-y-3">
          {rows.map((item) => {
            const ready = item.expected_count > 0 && item.submitted_count >= item.expected_count;
            return (
              <div key={item.student_id} className="rounded-2xl border border-border/70 bg-surface px-4 py-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-semibold text-text">{studentLabel(item)}</p>
                    <p className="mt-1 text-sm text-text-muted">
                      {item.submitted_count} of {item.expected_count} subject results locked
                    </p>
                    {item.missing_subject_names?.length ? (
                      <p className="mt-2 text-xs leading-5 text-error">
                        Missing: {item.missing_subject_names.join(", ")}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={ready ? "success" : "warning"}>
                      {ready ? "ready" : "incomplete"}
                    </Badge>
                    {item.report_card_status ? <Badge>{item.report_card_status}</Badge> : null}
                    {item.is_outdated ? <Badge variant="error">outdated</Badge> : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </WorkspacePanel>
  );

  const generate = async () => {
    if (generationTarget === "student" && !selectedStudentId) {
      showWarning("Select a student first.");
      return;
    }
    if (generationTarget === "student" && !selectedStudentReady) {
      showWarning("The selected student still has missing or unlocked subject results.");
      return;
    }
    if (generationTarget === "class" && readyRows.length === 0) {
      showWarning("No student in this context is ready for report-card generation.");
      return;
    }
    setSaving("generate");
    setGenerationSummary(null);
    try {
      const response = await reportCardService.generateReportCard({
        academic_session_id: filters.academic_session_id,
        academic_term_id: filters.academic_term_id,
        ...(generationTarget === "class"
          ? { class_id: filters.class_id, generate_for_class: true }
          : { student_id: selectedStudentId }),
      });
      const generated = Array.isArray(response?.generated) ? response.generated : [response];
      const skipped = Array.isArray(response?.skipped) ? response.skipped : [];
      setGenerationSummary({ generated, skipped });
      showSuccess(
        generationTarget === "class"
          ? `${generated.length} report card${generated.length === 1 ? "" : "s"} generated.`
          : "Student report card generated.",
      );
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not generate report card."));
    } finally {
      setSaving("");
    }
  };

  const generatePanel = (
    <WorkspacePanel
      title="Generate report cards"
      description="Generation uses the class and period selected on Overview. Choose only the generation target here."
    >
      <div className="space-y-4">
        <SelectControl
          label="Generation target"
          value={generationTarget}
          onChange={(value) => {
            setGenerationTarget(value);
            resetGenerationState();
          }}
          options={[
            { value: "class", label: "Entire class" },
            { value: "student", label: "One student" },
          ]}
        />
        {generationTarget === "student" ? (
          <SelectControl
            label="Student"
            value={selectedStudentId}
            onChange={setSelectedStudentId}
            options={rows.map((item) => ({
              value: item.student_id,
              label: `${studentLabel(item)}${
                item.expected_count > 0 && item.submitted_count >= item.expected_count
                  ? " · Ready"
                  : " · Incomplete"
              }`,
            }))}
            required
          />
        ) : (
          <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
            {readyRows.length} of {rows.length} students are currently ready. Incomplete students will be returned in the skipped summary.
          </div>
        )}
        <Button type="button" onClick={generate} disabled={saving === "generate"}>
          {saving === "generate" ? "Generating..." : "Generate report card"}
        </Button>
        {generationSummary ? (
          <div className="space-y-3 rounded-2xl border border-border/70 p-4">
            <p className="font-semibold text-text">
              Generated: {generationSummary.generated.length} · Skipped: {generationSummary.skipped.length}
            </p>
            {generationSummary.skipped.map((item) => (
              <div key={`${item.student_id}-${item.reason}`} className="rounded-xl bg-warning-soft px-3 py-2 text-sm text-amber-900">
                {item.reason}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </WorkspacePanel>
  );

  const publish = async (card) => {
    setSaving(card.id);
    try {
      await reportCardService.publishReportCard(card.id);
      showSuccess("Report card published.");
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not publish report card."));
    } finally {
      setSaving("");
    }
  };

  const regenerate = async (card) => {
    setSaving(card.id);
    try {
      await reportCardService.regenerateReportCard(card.id);
      showSuccess("Report card regenerated.");
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not regenerate report card."));
    } finally {
      setSaving("");
    }
  };

  const cardsPanel = (
    <WorkspacePanel
      title={`${String(activeTab || "").replaceAll("-", " ")} report cards`}
      description={`${cards.length} report card${cards.length === 1 ? "" : "s"} in the selected Overview context.`}
    >
      {cards.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <FileText className="mx-auto h-7 w-7 text-text-muted" />
          <p className="mt-3 text-sm font-semibold text-text">No matching report cards</p>
          <p className="mt-1 text-sm text-text-muted">Generate eligible report cards for the selected class and period.</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {cards.map((card) => (
            <div key={card.id} className="flex min-h-[14rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-text">{card.student_name || card.admission_number || "Student"}</p>
                  <p className="mt-1 text-xs text-text-muted">Version {card.version || 1}</p>
                </div>
                <Badge variant={card.status === "published" ? "success" : "warning"}>{card.status}</Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <div className="rounded-xl bg-surface-muted/40 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-text-muted">Average</p>
                  <p className="mt-1 font-semibold text-text">{card.average_score ?? "–"}</p>
                </div>
                <div className="rounded-xl bg-surface-muted/40 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-text-muted">Position</p>
                  <p className="mt-1 font-semibold text-text">{card.position ? `${card.position}/${card.position_out_of || "–"}` : "–"}</p>
                </div>
              </div>
              {card.is_outdated ? (
                <div className="mt-3 flex gap-2 rounded-xl bg-error-soft px-3 py-2 text-xs text-error">
                  <TriangleAlert className="h-4 w-4 shrink-0" />
                  Results changed after this version was generated.
                </div>
              ) : null}
              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                {card.is_outdated && card.status !== "published" ? (
                  <Button type="button" size="small" variant="outline" disabled={saving === card.id} onClick={() => regenerate(card)}>
                    Regenerate
                  </Button>
                ) : null}
                {card.status === "draft" ? (
                  <Button type="button" size="small" variant="success" disabled={saving === card.id || card.is_outdated} onClick={() => publish(card)}>
                    <CheckCircle2 className="h-4 w-4" />
                    {saving === card.id ? "Publishing..." : "Publish"}
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </WorkspacePanel>
  );

  if (error && !loading) {
    return (
      <WorkspacePanel title="Report cards unavailable">
        <p className="text-sm text-error">{error}</p>
        <Button type="button" className="mt-4" onClick={loadBase}>Retry</Button>
      </WorkspacePanel>
    );
  }

  return (
    <div className="space-y-4">
      {activeTab === "overview" ? contextPanel : contextSummary}
      {activeTab === "overview" ? overviewPanel : null}
      {activeTab === "ready" ? readinessPanel : null}
      {activeTab === "generate" ? generatePanel : null}
      {listTabs.includes(activeTab) ? cardsPanel : null}
    </div>
  );
}

export default ReportCardsWorkspace;
