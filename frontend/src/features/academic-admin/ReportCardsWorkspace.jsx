import { CheckCircle2, FileText, RefreshCw, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { reportCardService } from "../../services/reportCardService";
import {
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || "Unnamed class";

const studentLabel = (item) =>
  `${item?.student_name || item?.admission_number || "Student"}${item?.admission_number ? ` · ${item.admission_number}` : ""}`;

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
        classService.getClasses({ limit: 100, activeOnly: true }),
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
          current.academic_term_id || currentTerm?.id || nextTerms[0]?.id || "",
      }));
      onContextChange?.({ currentSession, currentTerm });
    } catch (err) {
      const message = getErrorMessage(err, "Could not load report-card workspace.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [onContextChange, showError]);

  const loadReportData = useCallback(async () => {
    if (
      !filters.class_id ||
      !filters.academic_session_id ||
      !filters.academic_term_id
    ) {
      setOverview(null);
      setCards([]);
      return;
    }
    try {
      const [overviewResponse, cardResponse] = await Promise.all([
        reportCardService.getClassOverview(filters),
        reportCardService.listAdminReportCards({ limit: 100 }),
      ]);
      setOverview(overviewResponse);
      setCards(
        asItems(cardResponse).filter(
          (item) =>
            item.class_id === filters.class_id &&
            item.academic_session_id === filters.academic_session_id &&
            item.academic_term_id === filters.academic_term_id,
        ),
      );
    } catch (err) {
      setOverview(null);
      setCards([]);
      showError(getErrorMessage(err, "Could not load report-card data."));
    }
  }, [filters, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadReportData();
  }, [loadReportData]);

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
  const studentOptions = useMemo(
    () =>
      (overview?.items || []).map((item) => ({
        value: item.student_id,
        label: studentLabel(item),
      })),
    [overview?.items],
  );

  const overviewStats = useMemo(() => {
    const items = overview?.items || [];
    return {
      total: items.length,
      ready: items.filter(
        (item) =>
          item.expected_count > 0 && item.submitted_count >= item.expected_count,
      ).length,
      incomplete: items.filter((item) => item.submitted_count < item.expected_count)
        .length,
      generated: items.filter((item) => item.report_card_id).length,
    };
  }, [overview?.items]);

  const generate = async () => {
    if (!filters.academic_session_id || !filters.academic_term_id) {
      showWarning("Select a session and term first.");
      return;
    }
    if (generationTarget === "student" && !selectedStudentId) {
      showWarning("Select a student first.");
      return;
    }
    setSaving("generate");
    try {
      await reportCardService.generateReportCard({
        academic_session_id: filters.academic_session_id,
        academic_term_id: filters.academic_term_id,
        ...(generationTarget === "class"
          ? { class_id: filters.class_id, generate_for_class: true }
          : { student_id: selectedStudentId }),
      });
      showSuccess(
        generationTarget === "class"
          ? "Class report-card generation completed."
          : "Student report card generated.",
      );
      await loadReportData();
    } catch (err) {
      showError(getErrorMessage(err, "Could not generate report card."));
    } finally {
      setSaving("");
    }
  };

  const regenerate = async (card) => {
    setSaving(card.id);
    try {
      await reportCardService.regenerateReportCard(card.id);
      showSuccess("Report card regenerated.");
      await loadReportData();
    } catch (err) {
      showError(getErrorMessage(err, "Could not regenerate report card."));
    } finally {
      setSaving("");
    }
  };

  const publish = async (card) => {
    setSaving(card.id);
    try {
      await reportCardService.publishReportCard(card.id);
      showSuccess("Report card published.");
      await loadReportData();
    } catch (err) {
      showError(getErrorMessage(err, "Could not publish report card."));
    } finally {
      setSaving("");
    }
  };

  const filterPanel = (
    <WorkspacePanel
      title="Report-card context"
      description="Choose the class, academic session, and term."
      actions={
        <Button type="button" size="small" variant="outline" onClick={loadReportData}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <SelectControl
          label="Class"
          value={filters.class_id}
          onChange={(value) =>
            setFilters((current) => ({ ...current, class_id: value }))
          }
          options={classOptions}
          required
        />
        <SelectControl
          label="Academic session"
          value={filters.academic_session_id}
          onChange={(value) => {
            const currentTerm = terms.find(
              (item) => item.academic_session_id === value && item.is_current,
            );
            setFilters((current) => ({
              ...current,
              academic_session_id: value,
              academic_term_id: currentTerm?.id || "",
            }));
          }}
          options={sessionOptions}
          required
        />
        <SelectControl
          label="Academic term"
          value={filters.academic_term_id}
          onChange={(value) =>
            setFilters((current) => ({ ...current, academic_term_id: value }))
          }
          options={termOptions}
          required
        />
      </div>
    </WorkspacePanel>
  );

  const overviewPanel = (
    <WorkspacePanel
      title="Class readiness"
      description="Each student must have all expected subject results submitted before report generation."
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Students", overviewStats.total],
          ["Ready", overviewStats.ready],
          ["Incomplete", overviewStats.incomplete],
          ["Generated", overviewStats.generated],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3"
          >
            <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
              {label}
            </p>
            <p className="mt-2 text-xl font-semibold text-text">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-3">
        {(overview?.items || []).length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border p-5 text-sm text-text-muted">
            No students are available in this class context.
          </p>
        ) : (
          overview.items.map((item) => {
            const ready =
              item.expected_count > 0 && item.submitted_count >= item.expected_count;
            return (
              <div
                key={item.student_id}
                className="rounded-2xl border border-border/70 bg-surface px-4 py-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-semibold text-text">{studentLabel(item)}</p>
                    <p className="mt-1 text-sm text-text-muted">
                      {item.submitted_count} of {item.expected_count} subjects submitted
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
                    {item.report_card_status ? (
                      <Badge variant={item.report_card_status === "published" ? "success" : "default"}>
                        {item.report_card_status}
                      </Badge>
                    ) : null}
                    {item.is_outdated ? <Badge variant="error">outdated</Badge> : null}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </WorkspacePanel>
  );

  const generatePanel = (
    <WorkspacePanel
      title="Generate report cards"
      description="Generate for the whole class or one selected student."
    >
      <div className="space-y-3">
        <SelectControl
          label="Generation target"
          value={generationTarget}
          onChange={(value) => {
            setGenerationTarget(value);
            setSelectedStudentId("");
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
            options={studentOptions}
            required
          />
        ) : null}
        <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm leading-6 text-amber-800">
          Incomplete students may be skipped by the backend. Review Class Overview before generating.
        </div>
        <Button type="button" onClick={generate} disabled={saving === "generate"}>
          {saving === "generate" ? "Generating..." : "Generate report card"}
        </Button>
      </div>
    </WorkspacePanel>
  );

  const cardsPanel = (
    <WorkspacePanel
      title="Generated report cards"
      description={`${cards.length} report card${cards.length === 1 ? "" : "s"} in the selected context.`}
    >
      {cards.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <FileText className="mx-auto h-7 w-7 text-text-muted" />
          <p className="mt-3 text-sm font-semibold text-text">No report cards generated</p>
          <p className="mt-1 text-sm text-text-muted">
            Generate report cards after all required results are submitted.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {cards.map((card) => (
            <div
              key={card.id}
              className="flex min-h-[14rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-text">
                    {card.student_name || card.admission_number || "Student"}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Version {card.version || 1}
                  </p>
                </div>
                <Badge variant={card.status === "published" ? "success" : "warning"}>
                  {card.status}
                </Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <div className="rounded-xl bg-surface-muted/40 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-text-muted">Average</p>
                  <p className="mt-1 font-semibold text-text">{card.average_score ?? "–"}</p>
                </div>
                <div className="rounded-xl bg-surface-muted/40 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-text-muted">Position</p>
                  <p className="mt-1 font-semibold text-text">
                    {card.position ? `${card.position}/${card.position_out_of || "–"}` : "–"}
                  </p>
                </div>
              </div>
              {card.is_outdated ? (
                <div className="mt-3 flex gap-2 rounded-xl bg-error-soft px-3 py-2 text-xs text-error">
                  <TriangleAlert className="h-4 w-4 shrink-0" />
                  Results changed after this version was generated.
                </div>
              ) : null}
              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                {card.is_outdated ? (
                  <Button
                    type="button"
                    size="small"
                    variant="outline"
                    disabled={saving === card.id}
                    onClick={() => regenerate(card)}
                  >
                    Regenerate
                  </Button>
                ) : null}
                {card.status !== "published" ? (
                  <Button
                    type="button"
                    size="small"
                    variant="success"
                    disabled={saving === card.id || card.is_outdated}
                    onClick={() => publish(card)}
                  >
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
        <Button type="button" className="mt-4" onClick={loadBase}>
          Retry
        </Button>
      </WorkspacePanel>
    );
  }

  return (
    <div className="space-y-4">
      {filterPanel}
      {activeTab === "generate" ? (
        <WorkspaceGrid editor={generatePanel} content={overviewPanel} />
      ) : activeTab === "publish" ? (
        cardsPanel
      ) : (
        overviewPanel
      )}
    </div>
  );
}

export default ReportCardsWorkspace;
