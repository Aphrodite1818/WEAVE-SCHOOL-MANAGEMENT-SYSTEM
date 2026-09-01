import {
  CheckCircle2,
  Eye,
  FileText,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import ReportCardLinesTable from "../../components/shared/ReportCardLinesTable";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { reportCardService } from "../../services/reportCardService";
import {
  Input,
  RecordList,
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
  [item?.academic_level_name, item?.arm_label || item?.arm]
    .filter(Boolean)
    .join(" ") ||
  "Unnamed class";

const studentLabel = (item) =>
  `${item?.student_name || item?.admission_number || "Student"}${
    item?.admission_number ? ` · ${item.admission_number}` : ""
  }`;

const termLabel = (item) =>
  String(item?.display_name || item?.name || "No term").replaceAll("_", " ");

const listTabs = ["draft", "published", "outdated", "archived"];

const reportBadgeVariant = (card) => {
  if (card?.is_outdated) return "error";
  return card?.status === "published" ? "success" : "warning";
};

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
  const [studentQuery, setStudentQuery] = useState("");
  const [generationSummary, setGenerationSummary] = useState(null);
  const [previewCard, setPreviewCard] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
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
          current.academic_term_id || currentTerm?.id || nextTerms[0]?.id || "",
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
    setStudentQuery("");
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
        .map((item) => ({ value: item.id, label: termLabel(item) })),
    [filters.academic_session_id, terms],
  );
  const classOptions = useMemo(
    () => classes.map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );

  const selectedClass = classes.find((item) => item.id === filters.class_id);
  const selectedSession = sessions.find((item) => item.id === filters.academic_session_id);
  const selectedTerm = terms.find((item) => item.id === filters.academic_term_id);
  const rows = overview?.items || [];
  const normalizedStudentQuery = studentQuery.trim().toLowerCase();
  const filteredRows = normalizedStudentQuery
    ? rows.filter((item) => studentLabel(item).toLowerCase().includes(normalizedStudentQuery))
    : rows;
  const filteredCards = normalizedStudentQuery
    ? cards.filter((item) =>
        `${item.student_name || ""} ${item.admission_number || ""}`
          .toLowerCase()
          .includes(normalizedStudentQuery),
      )
    : cards;
  const readyRows = rows.filter(
    (item) => item.expected_count > 0 && item.submitted_count >= item.expected_count,
  );
  const selectedStudent = rows.find((item) => item.student_id === selectedStudentId);
  const selectedStudentReady = Boolean(
    selectedStudent &&
      selectedStudent.expected_count > 0 &&
      selectedStudent.submitted_count >= selectedStudent.expected_count,
  );

  const contextSummary = (
    <div className="flex flex-col gap-2 rounded-xl border border-border/70 bg-surface px-4 py-3 text-sm text-text-muted sm:flex-row sm:items-center sm:justify-between">
      <span>
        <span className="font-semibold text-text">Selected report context:</span>{" "}
        {classLabel(selectedClass)} · {selectedSession?.name || "No session"} · {termLabel(selectedTerm)}
      </span>
      <Button
        type="button"
        size="small"
        variant="outline"
        className="manual-refresh-action"
        onClick={loadPageData}
      >
        <RefreshCw className="h-4 w-4" /> Refresh
      </Button>
    </div>
  );

  const contextPanel = (
    <WorkspacePanel
      title="Report-card context"
      description="Choose the class and academic period once. Readiness, generation, and report-card lifecycle pages reuse this context."
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <SelectControl
          label="Class"
          value={filters.class_id}
          onChange={(value) => setFilters((current) => ({ ...current, class_id: value }))}
          options={classOptions}
          required
        />
        <SelectControl
          label="Academic session"
          value={filters.academic_session_id}
          onChange={(value) => {
            const nextTerm =
              terms.find((item) => item.academic_session_id === value && item.is_current) ||
              terms.find((item) => item.academic_session_id === value);
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
            setFilters((current) => ({ ...current, academic_term_id: value }))
          }
          options={termOptions}
          required
        />
      </div>
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
        `${generated.length} report card${generated.length === 1 ? "" : "s"} generated.`,
      );
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not generate report card."));
    } finally {
      setSaving("");
    }
  };

  const openPreview = async (card) => {
    setPreviewLoading(true);
    try {
      const detail = await reportCardService.getAdminReportCard(card.id);
      setPreviewCard(detail);
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not load report-card preview."));
    } finally {
      setPreviewLoading(false);
    }
  };

  const publish = async (card) => {
    setSaving(card.id);
    try {
      await reportCardService.publishReportCard(card.id);
      showSuccess("Report card published.");
      setPreviewCard(null);
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

  const cardActions = (card) => (
    <ReportCardActions
      card={card}
      busy={saving === card.id}
      previewLoading={previewLoading}
      onPreview={openPreview}
      onRegenerate={regenerate}
    />
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
      {activeTab === "overview" ? contextPanel : contextSummary}

      {activeTab === "overview" ? (
        <WorkspacePanel
          title="Report-card overview"
          description="A compact readiness summary for the selected class and academic period."
        >
          <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-border/70 lg:grid-cols-4">
            {[
              ["Students", rows.length],
              ["Ready", readyRows.length],
              ["Incomplete", rows.length - readyRows.length],
              ["Generated", rows.filter((item) => item.report_card_id).length],
            ].map(([label, value], index) => (
              <div
                key={label}
                className={`px-4 py-3 ${index ? "border-l border-border/70" : ""}`}
              >
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  {label}
                </p>
                <p className="mt-1 text-xl font-semibold text-text">{value}</p>
              </div>
            ))}
          </div>
        </WorkspacePanel>
      ) : null}

      {activeTab === "ready" ? (
        <RecordList
          title="Student readiness"
          description="Every expected subject result must be locked before a report card can be generated."
          items={filteredRows.map((item) => ({ ...item, id: item.student_id }))}
          emptyIcon={FileText}
          emptyTitle="No students in this report context"
          emptyDescription="Choose another class or academic period from Overview."
          renderTitle={studentLabel}
          renderMeta={(item) => `${item.submitted_count} of ${item.expected_count} results locked`}
          renderDescription={(item) =>
            item.missing_subject_names?.length
              ? `Missing: ${item.missing_subject_names.join(", ")}`
              : "All expected subject results are locked."
          }
          renderStatus={(item) =>
            item.expected_count > 0 && item.submitted_count >= item.expected_count
              ? "ready"
              : "incomplete"
          }
          renderInspector={(item) => <ReadinessInspector item={item} />}
          actions={
            <Input
              label="Search"
              value={studentQuery}
              placeholder="Student or admission number"
              onChange={(event) => setStudentQuery(event.target.value)}
            />
          }
        />
      ) : null}

      {activeTab === "generate" ? (
        <WorkspacePanel
          title="Generate report cards"
          description="Generation uses the selected class and academic period and never bypasses readiness checks."
        >
          <div className="max-w-2xl space-y-4">
            <SelectControl
              label="Generation target"
              value={generationTarget}
              onChange={(value) => {
                setGenerationTarget(value);
                setSelectedStudentId("");
                setGenerationSummary(null);
              }}
              options={[
                { value: "class", label: "Entire class" },
                { value: "student", label: "One student" },
              ]}
            />

            {generationTarget === "student" ? (
              <div className="space-y-3">
                <Input
                  label="Search students"
                  value={studentQuery}
                  placeholder="Student name or admission number"
                  onChange={(event) => setStudentQuery(event.target.value)}
                />
                <SelectControl
                  label="Student"
                  value={selectedStudentId}
                  onChange={setSelectedStudentId}
                  searchPlaceholder="Search name or admission number"
                  options={filteredRows.map((item) => ({
                    value: item.student_id,
                    label: studentLabel(item),
                    description:
                      item.expected_count > 0 && item.submitted_count >= item.expected_count
                        ? "Ready for generation"
                        : "Incomplete results",
                    keywords: item.admission_number,
                  }))}
                  required
                />
              </div>
            ) : (
              <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
                <span className="font-semibold text-text">{readyRows.length}</span> of {rows.length} students are ready. Incomplete students are not silently treated as complete.
              </div>
            )}

            <Button type="button" onClick={generate} disabled={saving === "generate"}>
              {saving === "generate" ? "Generating..." : "Generate report card"}
            </Button>

            {generationSummary ? (
              <div className="rounded-xl border border-border/70 px-4 py-3 text-sm text-text-muted">
                Generated: <span className="font-semibold text-text">{generationSummary.generated.length}</span> · Skipped:{" "}
                <span className="font-semibold text-text">{generationSummary.skipped.length}</span>
              </div>
            ) : null}
          </div>
        </WorkspacePanel>
      ) : null}

      {listTabs.includes(activeTab) ? (
        <RecordList
          title={`${String(activeTab).replaceAll("-", " ")} report cards`}
          description={`${filteredCards.length} matching report card${filteredCards.length === 1 ? "" : "s"}.`}
          items={filteredCards}
          emptyIcon={FileText}
          emptyTitle="No matching report cards"
          emptyDescription="No report cards in this lifecycle stage match the selected context and search."
          renderTitle={(card) => card.student_name || card.admission_number || "Student"}
          renderMeta={(card) => `Version ${card.version || 1}`}
          renderDescription={(card) =>
            `Average ${card.average_score ?? "–"} · Position ${
              card.position ? `${card.position}/${card.position_out_of || "–"}` : "–"
            }${card.is_outdated ? " · Results changed after generation" : ""}`
          }
          renderStatus={(card) => (card.is_outdated ? "outdated" : card.status)}
          renderActions={cardActions}
          renderInspector={(card) => (
            <ReportCardInspector card={card} actions={cardActions(card)} />
          )}
          actions={
            <Input
              label="Search"
              value={studentQuery}
              placeholder="Student or admission number"
              onChange={(event) => setStudentQuery(event.target.value)}
            />
          }
        />
      ) : null}

      <Modal
        open={Boolean(previewCard)}
        title="Report card preview"
        description="Review every subject line, total, average, position, and comment before publishing."
        onClose={() => setPreviewCard(null)}
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setPreviewCard(null)}>
              Close
            </Button>
            {previewCard?.status === "draft" ? (
              <Button
                type="button"
                variant="success"
                disabled={saving === previewCard.id || previewCard.is_outdated}
                onClick={() => publish(previewCard)}
              >
                <CheckCircle2 className="h-4 w-4" />
                {saving === previewCard.id ? "Publishing..." : "Publish confirmed card"}
              </Button>
            ) : null}
          </div>
        }
      >
        {previewCard ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <PreviewField
                label="Student"
                value={previewCard.student_name || previewCard.admission_number}
              />
              <PreviewField
                label="Class"
                value={[previewCard.class_name, previewCard.class_arm]
                  .filter(Boolean)
                  .join(" ")}
              />
              <PreviewField label="Session" value={previewCard.academic_session_name} />
              <PreviewField
                label="Term"
                value={String(previewCard.academic_term_name || "").replaceAll("_", " ")}
              />
              <PreviewField label="Average" value={previewCard.average_score} />
              <PreviewField
                label="Position"
                value={
                  previewCard.position
                    ? `${previewCard.position}/${previewCard.position_out_of || "–"}`
                    : "–"
                }
              />
            </div>
            <ReportCardLinesTable lines={previewCard.lines || []} />
            <div className="grid gap-3 sm:grid-cols-2">
              <PreviewField
                label="Class teacher comment"
                value={previewCard.class_teacher_comment || "No comment"}
              />
              <PreviewField
                label="Principal comment"
                value={previewCard.principal_comment || "No comment"}
              />
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

function ReportCardActions({
  card,
  busy,
  previewLoading,
  onPreview,
  onRegenerate,
}) {
  return (
    <>
      <Button
        type="button"
        size="small"
        variant="outline"
        disabled={previewLoading}
        onClick={() => onPreview(card)}
      >
        <Eye className="h-4 w-4" /> Preview
      </Button>
      {card.is_outdated && card.status !== "published" ? (
        <Button
          type="button"
          size="small"
          variant="outline"
          disabled={busy}
          onClick={() => onRegenerate(card)}
        >
          Regenerate
        </Button>
      ) : null}
      {card.status === "draft" ? (
        <Button
          type="button"
          size="small"
          variant="success"
          disabled={busy || card.is_outdated}
          onClick={() => onPreview(card)}
        >
          Review to publish
        </Button>
      ) : null}
    </>
  );
}

function ReadinessInspector({ item }) {
  const ready = item.expected_count > 0 && item.submitted_count >= item.expected_count;
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-surface">
      <div className="border-b border-border/70 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-semibold text-text">{studentLabel(item)}</p>
            <p className="mt-1 text-xs text-text-muted">Report-card generation readiness</p>
          </div>
          <Badge variant={ready ? "success" : "warning"}>
            {ready ? "ready" : "incomplete"}
          </Badge>
        </div>
      </div>
      <div className="divide-y divide-border/70">
        <section className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            Result coverage
          </p>
          <p className="mt-2 text-sm text-text-muted">
            <span className="font-semibold text-text">{item.submitted_count}</span> of{" "}
            <span className="font-semibold text-text">{item.expected_count}</span> expected subject results are locked.
          </p>
        </section>
        <section className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            Missing subjects
          </p>
          {item.missing_subject_names?.length ? (
            <ul className="mt-2 space-y-1 text-sm text-error">
              {item.missing_subject_names.map((name) => (
                <li key={name}>• {name}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-success">No missing subject results.</p>
          )}
        </section>
        {item.report_card_id ? (
          <section className="px-4 py-4 text-sm text-text-muted">
            A report card has already been generated for this context.
          </section>
        ) : null}
      </div>
    </div>
  );
}

function ReportCardInspector({ card, actions }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-surface">
      <div className="border-b border-border/70 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-semibold text-text">
              {card.student_name || card.admission_number || "Student"}
            </p>
            <p className="mt-1 text-xs text-text-muted">Version {card.version || 1}</p>
          </div>
          <Badge variant={reportBadgeVariant(card)}>
            {card.is_outdated ? "outdated" : card.status}
          </Badge>
        </div>
      </div>
      <div className="divide-y divide-border/70">
        <section className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            Academic outcome
          </p>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-text-muted">Average</dt>
              <dd className="font-semibold text-text">{card.average_score ?? "–"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-text-muted">Position</dt>
              <dd className="font-semibold text-text">
                {card.position ? `${card.position}/${card.position_out_of || "–"}` : "–"}
              </dd>
            </div>
          </dl>
        </section>

        {card.is_outdated ? (
          <section className="px-4 py-4">
            <div className="flex gap-2 rounded-lg bg-error-soft px-3 py-2 text-xs text-error">
              <TriangleAlert className="h-4 w-4 shrink-0" />
              Results changed after this version was generated. Regenerate the draft before publishing.
            </div>
          </section>
        ) : null}

        <section className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            Actions
          </p>
          <div className="mt-3 flex flex-wrap gap-2">{actions}</div>
        </section>
      </div>
    </div>
  );
}

function PreviewField({ label, value }) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface-muted/20 px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-text">{value ?? "–"}</p>
    </div>
  );
}

export default ReportCardsWorkspace;
