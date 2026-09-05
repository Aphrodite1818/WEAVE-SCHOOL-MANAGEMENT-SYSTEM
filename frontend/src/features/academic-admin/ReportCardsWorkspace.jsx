import {
  CheckCircle2,
  Eye,
  MessageSquareWarning,
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
import { reportCommentService } from "../../services/reportCommentService";
import {
  Input,
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

const humanize = (value, fallback = "Not set") =>
  String(value || fallback)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());

const normalizeGrade = (value) => String(value || "").trim().toLowerCase();

const commentOptionLabel = (template) => {
  const text = String(template?.text || "").trim();
  if (!text) return "Saved comment";
  return text.length > 90 ? `${text.slice(0, 87)}...` : text;
};

const statusVariant = (value) => {
  const status = String(value || "").toLowerCase();
  if (["complete", "ready", "published", "submitted", "submitted_or_overridden", "available"].includes(status)) {
    return "success";
  }
  if (["missing", "needs_review", "override_required", "outdated", "incomplete"].includes(status)) {
    return "error";
  }
  if (["draft", "manual", "waiting_for_results"].includes(status)) return "warning";
  return "default";
};

function StatusBadge({ value }) {
  return <Badge variant={statusVariant(value)}>{humanize(value)}</Badge>;
}

function ReportCardsWorkspace({ activeTab, onContextChange }) {
  const { showSuccess, showError, showWarning } = useToast();
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [classes, setClasses] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [gradingScales, setGradingScales] = useState([]);
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
  const [principalMode, setPrincipalMode] = useState("default");
  const [principalTemplateId, setPrincipalTemplateId] = useState("");
  const [principalComment, setPrincipalComment] = useState("");
  const [generationSummary, setGenerationSummary] = useState(null);
  const [previewCard, setPreviewCard] = useState(null);
  const [overrideState, setOverrideState] = useState(null);
  const [principalEditor, setPrincipalEditor] = useState(null);
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        sessionResponse,
        termResponse,
        classResponse,
        templateResponse,
        gradeResponse,
      ] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        classService.getClasses({ limit: 100, activeOnly: false }),
        reportCommentService.listAdminTemplates({ include_archived: false }),
        academicService.listGradingScales({ active_only: true, limit: 100 }),
      ]);
      const nextSessions = asItems(sessionResponse);
      const nextTerms = asItems(termResponse);
      const nextClasses = asItems(classResponse);
      const nextTemplates = asItems(templateResponse).filter((item) => item.status === "active");
      const currentSession = nextSessions.find((item) => item.is_current) || nextSessions[0] || null;
      const currentTerm =
        nextTerms.find(
          (item) =>
            item.is_current &&
            (!currentSession || item.academic_session_id === currentSession.id),
        ) ||
        nextTerms.find(
          (item) => !currentSession || item.academic_session_id === currentSession.id,
        ) ||
        null;

      setSessions(nextSessions);
      setTerms(nextTerms);
      setClasses(nextClasses);
      setTemplates(nextTemplates);
      setGradingScales(asItems(gradeResponse));
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
  const scaleIdByGrade = useMemo(
    () => new Map(gradingScales.map((item) => [normalizeGrade(item.grade), item.id])),
    [gradingScales],
  );

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
  const readyRows = rows.filter((item) => item.report_readiness === "ready");
  const overrideRows = rows.filter((item) => item.report_readiness === "override_required");
  const waitingRows = rows.filter((item) => item.report_readiness === "waiting_for_results");
  const selectedStudent = rows.find((item) => item.student_id === selectedStudentId);

  const selectedClass = classes.find((item) => item.id === filters.class_id);
  const selectedSession = sessions.find((item) => item.id === filters.academic_session_id);
  const selectedTerm = terms.find((item) => item.id === filters.academic_term_id);

  const optionsForGradeId = useCallback(
    (gradeId) =>
      gradeId
        ? templates
            .filter((item) => (item.grading_scale_ids || []).includes(gradeId))
            .sort((left, right) => {
              const leftDefault = (left.default_grading_scale_ids || []).includes(gradeId) ? 1 : 0;
              const rightDefault = (right.default_grading_scale_ids || []).includes(gradeId) ? 1 : 0;
              return rightDefault - leftDefault;
            })
            .map((item) => ({
              value: item.id,
              label: commentOptionLabel(item),
              description: (item.default_grading_scale_ids || []).includes(gradeId)
                ? "Default for this grade"
                : "Saved principal comment",
            }))
        : [],
    [templates],
  );

  const selectedStudentGradeId = selectedStudent?.overall_grade
    ? scaleIdByGrade.get(normalizeGrade(selectedStudent.overall_grade))
    : null;
  const generationTemplateOptions = useMemo(
    () => optionsForGradeId(selectedStudentGradeId),
    [optionsForGradeId, selectedStudentGradeId],
  );

  const principalEditorGradeId = useMemo(() => {
    if (!principalEditor?.card) return null;
    const score = Number(principalEditor.card.average_score);
    if (!Number.isFinite(score)) return null;
    const scale = gradingScales.find((item) => {
      const minimum = Number(item.min_score);
      const maximum = Number(item.max_score);
      return Number.isFinite(minimum) && Number.isFinite(maximum) && score >= minimum && score <= maximum;
    });
    return scale?.id || null;
  }, [gradingScales, principalEditor]);
  const principalEditorTemplateOptions = useMemo(
    () => optionsForGradeId(principalEditorGradeId),
    [optionsForGradeId, principalEditorGradeId],
  );

  const contextControls = (
    <WorkspacePanel
      title="Report-card context"
      description="Choose the class and academic period once. Results, teacher comments, principal comments, generation, and versioning all use this context."
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
          onChange={(value) => setFilters((current) => ({ ...current, academic_term_id: value }))}
          options={termOptions}
          required
        />
      </div>
    </WorkspacePanel>
  );

  const contextSummary = (
    <div className="flex flex-col gap-2 rounded-xl border border-border/70 bg-surface px-4 py-3 text-sm text-text-muted sm:flex-row sm:items-center sm:justify-between">
      <span>
        <span className="font-semibold text-text">Selected report context:</span>{" "}
        {classLabel(selectedClass)} · {selectedSession?.name || "No session"} · {termLabel(selectedTerm)}
      </span>
      <Button type="button" size="small" variant="outline" onClick={loadPageData}>
        <RefreshCw className="h-4 w-4" /> Refresh
      </Button>
    </div>
  );

  const buildGenerationPayload = () => {
    const payload = {
      academic_session_id: filters.academic_session_id,
      academic_term_id: filters.academic_term_id,
      ...(generationTarget === "class"
        ? { class_id: filters.class_id }
        : { student_id: selectedStudentId }),
    };
    if (generationTarget === "class") {
      payload.apply_default_principal_template = true;
      return payload;
    }
    if (principalMode === "default") payload.apply_default_principal_template = true;
    if (principalMode === "template" && principalTemplateId) {
      payload.principal_template_id = principalTemplateId;
    }
    if (principalMode === "manual" && principalComment.trim()) {
      payload.principal_comment = principalComment.trim();
    }
    return payload;
  };

  const generate = async () => {
    if (generationTarget === "student" && !selectedStudentId) {
      showWarning("Select a student first.");
      return;
    }
    if (generationTarget === "student" && selectedStudent?.report_readiness !== "ready") {
      showWarning("Resolve result or teacher-comment blockers before generating this report.");
      return;
    }
    if (generationTarget === "class" && readyRows.length === 0) {
      showWarning("No student in this class is currently ready for generation.");
      return;
    }
    if (generationTarget === "student" && principalMode === "template" && !principalTemplateId) {
      showWarning("Choose a principal comment assigned to this student's grade.");
      return;
    }
    if (generationTarget === "student" && principalMode === "manual" && !principalComment.trim()) {
      showWarning("Enter the principal comment to use.");
      return;
    }

    setSaving("generate");
    setGenerationSummary(null);
    try {
      const response = await reportCardService.generateReportCard(buildGenerationPayload());
      const generated = Array.isArray(response?.generated) ? response.generated : [response];
      const skipped = Array.isArray(response?.skipped) ? response.skipped : [];
      setGenerationSummary({ generated: generated.filter(Boolean), skipped });
      showSuccess(`${generated.filter(Boolean).length} report card${generated.filter(Boolean).length === 1 ? "" : "s"} generated.`);
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not generate report card."));
    } finally {
      setSaving("");
    }
  };

  const submitOverride = async (event) => {
    event.preventDefault();
    if (!overrideState) return;
    if (!overrideState.comment_text.trim() || overrideState.reason.trim().length < 3) {
      showWarning("Enter the override comment and a reason of at least three characters.");
      return;
    }
    setSaving("override");
    try {
      await reportCommentService.overrideTeacherComment({
        student_id: overrideState.student.student_id,
        academic_session_id: filters.academic_session_id,
        academic_term_id: filters.academic_term_id,
        comment_text: overrideState.comment_text.trim(),
        reason: overrideState.reason.trim(),
      });
      showSuccess("Teacher comment override recorded with its audit reason.");
      setOverrideState(null);
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not record the teacher comment override."));
    } finally {
      setSaving("");
    }
  };

  const openPreview = async (card) => {
    setSaving(`preview:${card.id}`);
    try {
      const detail = await reportCardService.getAdminReportCard(card.id);
      setPreviewCard(detail);
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not load report-card preview."));
    } finally {
      setSaving("");
    }
  };

  const publish = async (card) => {
    setSaving(card.id);
    try {
      await reportCardService.publishReportCard(card.id);
      showSuccess("Report card published as the current official version.");
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
      const replacement = await reportCardService.regenerateReportCard(card.id);
      showSuccess(
        card.status === "published"
          ? `Replacement draft v${replacement?.version || Number(card.version || 1) + 1} created. The published snapshot remains immutable until replacement publication.`
          : `Report draft regenerated as v${replacement?.version || Number(card.version || 1) + 1}.`,
      );
      setPreviewCard(null);
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not create the replacement report draft."));
    } finally {
      setSaving("");
    }
  };

  const savePrincipalComment = async (event) => {
    event.preventDefault();
    if (!principalEditor) return;
    const allowedTemplateIds = new Set(principalEditorTemplateOptions.map((item) => item.value));
    const selectedTemplate = templates.find(
      (item) => item.id === principalEditor.template_id && allowedTemplateIds.has(item.id),
    );
    if (principalEditor.template_id && !selectedTemplate) {
      showWarning("Choose a principal comment assigned to this report's calculated grade.");
      return;
    }
    const text = selectedTemplate?.text || principalEditor.comment.trim();
    if (!text) {
      showWarning("Choose a grade-matched saved comment or enter a principal comment.");
      return;
    }
    setSaving("principal");
    try {
      const updated = await reportCardService.updatePrincipalComment(principalEditor.card.id, {
        principal_comment: text,
        principal_template_id: selectedTemplate?.id || null,
      });
      showSuccess("Principal comment updated on this draft.");
      setPreviewCard(updated);
      setPrincipalEditor(null);
      await loadPageData();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not update the principal comment."));
    } finally {
      setSaving("");
    }
  };

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
      {activeTab === "overview" ? contextControls : contextSummary}

      {activeTab === "overview" ? (
        <>
          <WorkspacePanel
            title="Report readiness overview"
            description="A report is ready only when the authoritative curriculum results are locked and the effective class-teacher comment is submitted or explicitly overridden."
          >
            <div className="grid grid-cols-2 overflow-hidden rounded-xl border border-border/70 lg:grid-cols-4">
              {[
                ["Students", rows.length],
                ["Ready", readyRows.length],
                ["Override required", overrideRows.length],
                ["Waiting for results", waitingRows.length],
              ].map(([label, value], index) => (
                <div key={label} className={`px-4 py-3 ${index ? "border-l border-border/70" : ""}`}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
                  <p className="mt-1 text-xl font-semibold text-text">{value}</p>
                </div>
              ))}
            </div>
          </WorkspacePanel>
          <ReadinessTable
            rows={filteredRows}
            studentQuery={studentQuery}
            onStudentQuery={setStudentQuery}
            onOverride={(student) => setOverrideState({ student, comment_text: "", reason: "" })}
          />
        </>
      ) : null}

      {activeTab === "ready" ? (
        <ReadinessTable
          rows={filteredRows}
          studentQuery={studentQuery}
          onStudentQuery={setStudentQuery}
          onOverride={(student) => setOverrideState({ student, comment_text: "", reason: "" })}
        />
      ) : null}

      {activeTab === "generate" ? (
        <WorkspacePanel
          title="Generate report cards"
          description="Generation uses backend readiness, snapshot data, and grade-aware principal comments. Students with unresolved teacher comments are skipped rather than silently treated as ready."
        >
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
            <div className="space-y-4">
              <SelectControl
                label="Generation target"
                value={generationTarget}
                onChange={(value) => {
                  setGenerationTarget(value);
                  setSelectedStudentId("");
                  setGenerationSummary(null);
                  setPrincipalTemplateId("");
                  setPrincipalComment("");
                  if (value === "class") setPrincipalMode("default");
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
                  onChange={(value) => {
                    setSelectedStudentId(value);
                    setPrincipalTemplateId("");
                    setPrincipalComment("");
                  }}
                  options={rows.map((item) => ({
                    value: item.student_id,
                    label: studentLabel(item),
                    description: humanize(item.report_readiness),
                  }))}
                  required
                />
              ) : (
                <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
                  <span className="font-semibold text-text">{readyRows.length}</span> of {rows.length} students are ready. Each generated student uses your default principal comment for their own calculated grade.
                </div>
              )}
              <Button type="button" onClick={generate} disabled={saving === "generate"}>
                {saving === "generate" ? "Generating..." : "Generate report card"}
              </Button>
              {generationSummary ? (
                <div className="rounded-xl border border-border/70 px-4 py-3 text-sm text-text-muted">
                  Generated: <span className="font-semibold text-text">{generationSummary.generated.length}</span> · Skipped:{" "}
                  <span className="font-semibold text-text">{generationSummary.skipped.length}</span>
                  {generationSummary.skipped.length ? (
                    <div className="mt-2 space-y-1">
                      {generationSummary.skipped.slice(0, 8).map((item) => (
                        <p key={`${item.student_id}-${item.reason}`}>{item.reason}</p>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="space-y-3 rounded-xl border border-border/70 bg-surface p-4">
              <p className="font-semibold text-text">Principal comment policy</p>
              {generationTarget === "class" ? (
                <>
                  <StatusBadge value="available" />
                  <p className="text-sm leading-6 text-text-muted">
                    Bulk generation always resolves your personal default principal comment separately for each student's calculated grade. One arbitrary comment is never applied to the whole class.
                  </p>
                </>
              ) : (
                <>
                  <SelectControl
                    label="Comment source"
                    value={principalMode}
                    onChange={(value) => {
                      setPrincipalMode(value);
                      setPrincipalTemplateId("");
                      setPrincipalComment("");
                    }}
                    options={[
                      { value: "default", label: "Use my grade default" },
                      { value: "template", label: "Choose another comment for this grade" },
                      { value: "manual", label: "Write a manual comment" },
                    ]}
                  />
                  {principalMode === "template" ? (
                    <SelectControl
                      label={`Grade ${selectedStudent?.overall_grade || ""} principal comment`}
                      value={principalTemplateId}
                      onChange={setPrincipalTemplateId}
                      options={generationTemplateOptions}
                      required
                      disabled={!selectedStudentGradeId}
                    />
                  ) : null}
                  {principalMode === "manual" ? (
                    <label className="grid gap-1.5 text-sm font-medium text-text-soft">
                      Principal comment
                      <textarea
                        value={principalComment}
                        onChange={(event) => setPrincipalComment(event.target.value)}
                        rows={5}
                        maxLength={2000}
                        className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                      />
                    </label>
                  ) : null}
                  {principalMode === "default" ? (
                    <p className="text-sm leading-6 text-text-muted">
                      This student uses your active default principal comment mapped to Grade {selectedStudent?.overall_grade || "—"}.
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </div>
        </WorkspacePanel>
      ) : null}

      {listTabs.includes(activeTab) ? (
        <WorkspacePanel
          title={`${humanize(activeTab)} report cards`}
          description={`${filteredCards.length} matching report card${filteredCards.length === 1 ? "" : "s"}. Published versions remain immutable; an outdated published card produces a replacement draft.`}
          actions={
            <Input
              label="Search"
              value={studentQuery}
              placeholder="Student or admission number"
              onChange={(event) => setStudentQuery(event.target.value)}
            />
          }
        >
          {filteredCards.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
              No report cards match this lifecycle stage.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredCards.map((card) => (
                <div key={card.id} className="rounded-xl border border-border/70 bg-surface p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-text">{card.student_name || card.admission_number || "Student"}</p>
                        <StatusBadge value={card.is_outdated ? "outdated" : card.status} />
                        <Badge variant="default">Version {card.version || 1}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-text-muted">
                        Average {card.average_score ?? "–"} · Position {card.position ? `${card.position}/${card.position_out_of || "–"}` : "–"}
                        {card.department_name ? ` · ${card.department_name}` : ""}
                      </p>
                      {card.replaces_report_card_id ? (
                        <p className="mt-1 text-xs text-text-muted">Replacement version for an earlier official snapshot.</p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" size="small" variant="outline" disabled={saving === `preview:${card.id}`} onClick={() => openPreview(card)}>
                        <Eye className="h-4 w-4" /> Preview
                      </Button>
                      {card.is_outdated && card.status !== "archived" ? (
                        <Button type="button" size="small" variant="outline" disabled={saving === card.id} onClick={() => regenerate(card)}>
                          {card.status === "published" ? `Create replacement v${Number(card.version || 1) + 1}` : "Regenerate draft"}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </WorkspacePanel>
      ) : null}

      <Modal
        open={Boolean(overrideState)}
        title="Override class-teacher comment"
        description="Use this only when the class-teacher comment is missing or needs review. The reason is stored as audit evidence."
        onClose={() => setOverrideState(null)}
      >
        {overrideState ? (
          <form className="space-y-4" onSubmit={submitOverride}>
            <div className="rounded-xl border border-warning/30 bg-warning-soft/40 px-4 py-3 text-sm text-text-soft">
              <p className="font-semibold text-text">{studentLabel(overrideState.student)}</p>
              <p className="mt-1">Current teacher-comment state: {humanize(overrideState.student.teacher_comment_status)}</p>
            </div>
            <label className="grid gap-1.5 text-sm font-medium text-text-soft">
              Override comment
              <textarea
                value={overrideState.comment_text}
                onChange={(event) => setOverrideState((current) => ({ ...current, comment_text: event.target.value }))}
                rows={5}
                maxLength={2000}
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                required
              />
            </label>
            <label className="grid gap-1.5 text-sm font-medium text-text-soft">
              Audit reason
              <textarea
                value={overrideState.reason}
                onChange={(event) => setOverrideState((current) => ({ ...current, reason: event.target.value }))}
                rows={3}
                maxLength={1000}
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                required
              />
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOverrideState(null)}>Cancel</Button>
              <Button type="submit" disabled={saving === "override"}>{saving === "override" ? "Saving..." : "Record override"}</Button>
            </div>
          </form>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(principalEditor)}
        title="Edit principal comment"
        description="Principal comments may be edited only on draft report cards. Saved comments shown here are restricted to this report's calculated grade."
        onClose={() => setPrincipalEditor(null)}
      >
        {principalEditor ? (
          <form className="space-y-4" onSubmit={savePrincipalComment}>
            <SelectControl
              label="Use a saved comment for this grade"
              value={principalEditor.template_id}
              onChange={(value) => setPrincipalEditor((current) => ({ ...current, template_id: value, comment: "" }))}
              options={principalEditorTemplateOptions}
              clearable
            />
            <label className="grid gap-1.5 text-sm font-medium text-text-soft">
              Or write a manual principal comment
              <textarea
                value={principalEditor.comment}
                onChange={(event) => setPrincipalEditor((current) => ({ ...current, template_id: "", comment: event.target.value }))}
                rows={5}
                maxLength={2000}
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
              />
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setPrincipalEditor(null)}>Cancel</Button>
              <Button type="submit" disabled={saving === "principal"}>{saving === "principal" ? "Saving..." : "Save principal comment"}</Button>
            </div>
          </form>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(previewCard)}
        title="Report card preview"
        description="This preview reads the report snapshot, not mutable current class configuration."
        onClose={() => setPreviewCard(null)}
        footer={
          previewCard ? (
            <div className="flex flex-wrap justify-end gap-2">
              {previewCard.status === "draft" ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setPrincipalEditor({
                    card: previewCard,
                    template_id: previewCard.principal_comment_source_template_id || "",
                    comment: previewCard.principal_comment || "",
                  })}
                >
                  Edit principal comment
                </Button>
              ) : null}
              {previewCard.is_outdated && previewCard.status !== "archived" ? (
                <Button type="button" variant="outline" disabled={saving === previewCard.id} onClick={() => regenerate(previewCard)}>
                  {previewCard.status === "published" ? `Create replacement v${Number(previewCard.version || 1) + 1}` : "Regenerate draft"}
                </Button>
              ) : null}
              {previewCard.status === "draft" ? (
                <Button
                  type="button"
                  variant="success"
                  disabled={saving === previewCard.id || previewCard.is_outdated}
                  onClick={() => publish(previewCard)}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {saving === previewCard.id ? "Publishing..." : "Publish official version"}
                </Button>
              ) : null}
            </div>
          ) : null
        }
      >
        {previewCard ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <PreviewField label="Student" value={previewCard.student_name || previewCard.admission_number} />
              <PreviewField label="Class snapshot" value={[previewCard.class_name, previewCard.class_arm].filter(Boolean).join(" ")} />
              <PreviewField label="Department snapshot" value={previewCard.department_name || "No term specialization"} />
              <PreviewField label="Class teacher snapshot" value={previewCard.class_teacher_name || "Not assigned"} />
              <PreviewField label="Version" value={`v${previewCard.version || 1}`} />
              <PreviewField label="Status" value={humanize(previewCard.is_outdated ? "outdated" : previewCard.status)} />
              <PreviewField label="Average" value={previewCard.average_score} />
              <PreviewField label="Position" value={previewCard.position ? `${previewCard.position}/${previewCard.position_out_of || "–"}` : "–"} />
              <PreviewField label="Teacher comment source" value={humanize(previewCard.teacher_comment_source, "Missing")} />
            </div>
            <ReportCardLinesTable lines={previewCard.lines || []} />
            <div className="grid gap-3 sm:grid-cols-2">
              <PreviewField label="Class teacher comment" value={previewCard.class_teacher_comment || "No comment"} multiline />
              <PreviewField label="Principal comment" value={previewCard.principal_comment || "No comment"} multiline />
            </div>
            {previewCard.replaces_report_card_id ? (
              <div className="rounded-xl border border-primary/20 bg-primary-soft/30 px-4 py-3 text-sm text-text-soft">
                This draft/version replaces an earlier report snapshot. The earlier published record is retained for history.
              </div>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

function ReadinessTable({ rows, studentQuery, onStudentQuery, onOverride }) {
  return (
    <WorkspacePanel
      title="Student readiness"
      description="Results, effective class-teacher comment, overall grade, principal-comment policy, and report state are shown separately so blockers are explicit."
      actions={
        <Input
          label="Search"
          value={studentQuery}
          placeholder="Student or admission number"
          onChange={(event) => onStudentQuery(event.target.value)}
        />
      }
    >
      {rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
          No students in this report context.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border/70">
          <table className="min-w-[980px] w-full text-left text-sm">
            <thead className="bg-surface-muted/60 text-xs uppercase tracking-wide text-text-muted">
              <tr>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3">Results</th>
                <th className="px-4 py-3">Teacher comment</th>
                <th className="px-4 py-3">Overall grade</th>
                <th className="px-4 py-3">Principal comment</th>
                <th className="px-4 py-3">Report readiness</th>
                <th className="px-4 py-3">Report</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/70">
              {rows.map((item) => {
                const canOverride = ["missing", "needs_review"].includes(item.teacher_comment_status);
                return (
                  <tr key={item.student_id}>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-text">{item.student_name || "Student"}</p>
                      <p className="text-xs text-text-muted">{item.admission_number}</p>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge value={item.results_readiness} />
                      <p className="mt-1 text-xs text-text-muted">{item.submitted_count}/{item.expected_count} locked</p>
                      {item.missing_subject_names?.length ? (
                        <p className="mt-1 max-w-52 text-xs text-error">Missing: {item.missing_subject_names.join(", ")}</p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3"><StatusBadge value={item.teacher_comment_status} /></td>
                    <td className="px-4 py-3 font-semibold text-text">{item.overall_grade || "–"}</td>
                    <td className="px-4 py-3"><StatusBadge value={item.principal_comment_status} /></td>
                    <td className="px-4 py-3"><StatusBadge value={item.report_readiness} /></td>
                    <td className="px-4 py-3">
                      {item.report_card_id ? (
                        <div className="flex flex-wrap gap-1.5">
                          <StatusBadge value={item.is_outdated ? "outdated" : item.report_card_status} />
                          <Badge variant="default">v{item.report_card_version || 1}</Badge>
                        </div>
                      ) : (
                        <span className="text-text-muted">Not generated</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {canOverride ? (
                        <Button type="button" size="small" variant="outline" onClick={() => onOverride(item)}>
                          <MessageSquareWarning className="h-4 w-4" /> Override
                        </Button>
                      ) : item.report_readiness === "waiting_for_results" ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-warning"><TriangleAlert className="h-4 w-4" /> Resolve results</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-success"><CheckCircle2 className="h-4 w-4" /> Ready</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </WorkspacePanel>
  );
}

function PreviewField({ label, value, multiline = false }) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface-muted/20 px-3 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p className={`mt-1 text-sm font-medium text-text ${multiline ? "whitespace-pre-wrap leading-6" : ""}`}>{value ?? "–"}</p>
    </div>
  );
}

export default ReportCardsWorkspace;
