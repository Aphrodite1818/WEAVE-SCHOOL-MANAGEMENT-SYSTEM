import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, FilePenLine, RefreshCw } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { parseApiError } from "../../services/api";
import { reportCommentService } from "../../services/reportCommentService";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const normalizeGrade = (value) => String(value || "").trim().toLowerCase();

const commentOptionLabel = (template) => {
  const text = String(template?.text || "").trim();
  if (!text) return "Saved comment";
  return text.length > 90 ? `${text.slice(0, 87)}...` : text;
};

const statusVariant = (status) => {
  const value = String(status || "").toLowerCase();
  if (value === "submitted") return "success";
  if (value === "needs_review") return "error";
  if (value === "draft") return "warning";
  return "default";
};

function SelectField({ label, value, options, onChange, placeholder, disabled }) {
  return (
    <SearchableSelect
      label={label}
      value={value || ""}
      options={options}
      placeholder={placeholder || "Select"}
      clearable={false}
      disabled={disabled}
      onChange={onChange}
    />
  );
}

function TeacherStudentCommentsPage() {
  const { showSuccess, showError } = useToast();
  const [summary, setSummary] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [gradingScales, setGradingScales] = useState([]);
  const [rows, setRows] = useState([]);
  const [classId, setClassId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [termId, setTermId] = useState("");
  const [loading, setLoading] = useState(true);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [editor, setEditor] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      reportCommentService.getTeacherCommentSummary(),
      academicService.listTeacherSessions({ limit: 100 }),
      reportCommentService.listTeacherTemplates(),
      reportCommentService.listTeacherGradingScales(),
    ])
      .then(([summaryResponse, sessionResponse, templateResponse, gradeResponse]) => {
        if (!active) return;
        setSummary(summaryResponse);
        setSessions(asItems(sessionResponse));
        setTemplates(asItems(templateResponse).filter((item) => item.status === "active"));
        setGradingScales(asItems(gradeResponse));
        setClassId(summaryResponse?.classes?.[0]?.class_id || "");
        setSessionId(
          summaryResponse?.academic_session_id ||
            asItems(sessionResponse).find((item) => item.is_current)?.id ||
            asItems(sessionResponse)[0]?.id ||
            "",
        );
        setTermId(summaryResponse?.academic_term_id || "");
      })
      .catch((requestError) => {
        if (active) setError(parseApiError(requestError, "Failed to load comment workspace.").message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!sessionId) {
      setTerms([]);
      setTermId("");
      return;
    }
    let active = true;
    academicService
      .listTeacherTerms({ academic_session_id: sessionId, limit: 100 })
      .then((response) => {
        if (!active) return;
        const items = asItems(response);
        setTerms(items);
        setTermId((current) =>
          items.some((item) => item.id === current)
            ? current
            : items.find((item) => item.is_current)?.id || items[0]?.id || "",
        );
      })
      .catch((requestError) => {
        if (active) showError(parseApiError(requestError, "Failed to load academic terms.").message);
      });
    return () => {
      active = false;
    };
  }, [sessionId, showError]);

  const loadRoster = async () => {
    if (!classId || !sessionId || !termId) {
      setRows([]);
      return;
    }
    setRosterLoading(true);
    setError("");
    try {
      const response = await reportCommentService.listTeacherStudentComments({
        class_id: classId,
        academic_session_id: sessionId,
        academic_term_id: termId,
      });
      setRows(asItems(response));
    } catch (requestError) {
      setError(parseApiError(requestError, "Failed to load student comment readiness.").message);
      setRows([]);
    } finally {
      setRosterLoading(false);
    }
  };

  useEffect(() => {
    loadRoster();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId, sessionId, termId]);

  const classOptions = useMemo(
    () =>
      (summary?.classes || []).map((item) => ({
        value: item.class_id,
        label: item.class_name,
      })),
    [summary],
  );
  const sessionOptions = useMemo(
    () => sessions.map((item) => ({ value: item.id, label: item.name || item.id })),
    [sessions],
  );
  const termOptions = useMemo(
    () => terms.map((item) => ({ value: item.id, label: titleCase(item.name) })),
    [terms],
  );
  const scaleIdByGrade = useMemo(
    () =>
      new Map(
        gradingScales.map((item) => [normalizeGrade(item.grade), item.id]),
      ),
    [gradingScales],
  );
  const editorTemplateOptions = useMemo(() => {
    if (!editor?.row?.overall_grade) return [];
    const gradeId = scaleIdByGrade.get(normalizeGrade(editor.row.overall_grade));
    if (!gradeId) return [];
    return templates
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
          ? `Default for Grade ${editor.row.overall_grade}`
          : `Grade ${editor.row.overall_grade}`,
      }));
  }, [editor, scaleIdByGrade, templates]);

  const openEditor = (row) => {
    const suggested = row.suggested_template;
    setEditor({
      row,
      sourceTemplateId: row.comment?.source_template_id || suggested?.id || "",
      text: row.comment?.comment_text || suggested?.text || "",
    });
  };

  const selectTemplate = (templateId) => {
    const template = templates.find((item) => item.id === templateId);
    setEditor((current) => ({
      ...current,
      sourceTemplateId: templateId,
      text: template?.text || current.text,
    }));
  };

  const save = async (submit) => {
    if (!editor || !editor.text.trim()) return;
    setBusy(true);
    const payload = {
      academic_session_id: sessionId,
      academic_term_id: termId,
      comment_text: editor.text.trim(),
      source_template_id: editor.sourceTemplateId || null,
    };
    try {
      if (submit) {
        await reportCommentService.submitTeacherComment(editor.row.student_id, payload);
        showSuccess("Teacher comment submitted.");
      } else {
        await reportCommentService.saveTeacherCommentDraft(editor.row.student_id, payload);
        showSuccess("Comment saved as draft.");
      }
      setEditor(null);
      await loadRoster();
    } catch (requestError) {
      showError(
        parseApiError(
          requestError,
          submit ? "Failed to submit teacher comment." : "Failed to save draft.",
        ).message,
      );
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout role="teacher" title="Student Comments">
        <LoadingState label="Loading comment workspace..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout role="teacher" title="Student Comments">
      <div className="space-y-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-text sm:text-[1.65rem]">
            Student Comments
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Review finalized performance and submit the class-teacher comment used by report cards.
          </p>
        </div>

        {error ? (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
            {error}
          </div>
        ) : null}

        {!summary?.class_teacher_class_count ? (
          <Card className="p-6">
            <EmptyState
              title="Class teacher assignment required"
              description="Student comments are available only when you are explicitly assigned as a class teacher. Subject teaching assignments do not grant this capability."
            />
          </Card>
        ) : (
          <>
            <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              {[
                ["Require comments", summary.students_requiring_comments],
                ["Draft", summary.draft_comments],
                ["Submitted", summary.submitted_comments],
                ["Needs review", summary.needs_review_comments],
                ["Completion", `${summary.comment_completion_percent}%`],
              ].map(([label, value]) => (
                <Card key={label} className="p-4">
                  <p className="text-xs font-semibold uppercase text-text-muted">{label}</p>
                  <p className="mt-2 text-2xl font-semibold text-text">{value}</p>
                </Card>
              ))}
            </section>

            <Card className="p-4 sm:p-5">
              <div className="grid gap-4 lg:grid-cols-3">
                <SelectField label="Class" value={classId} options={classOptions} onChange={setClassId} />
                <SelectField label="Academic session" value={sessionId} options={sessionOptions} onChange={setSessionId} />
                <SelectField label="Academic term" value={termId} options={termOptions} onChange={setTermId} disabled={!sessionId} />
              </div>
            </Card>

            <Card className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-border px-4 py-3 sm:px-5">
                <div>
                  <p className="font-semibold text-text">Comment readiness</p>
                  <p className="text-xs text-text-muted">Scores are read-only here. Comment work starts when the student's expected results are finalized and locked.</p>
                </div>
                <Button type="button" size="small" variant="outline" onClick={loadRoster} disabled={rosterLoading}>
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </Button>
              </div>
              {rosterLoading ? (
                <div className="p-6"><LoadingState label="Resolving academic readiness..." /></div>
              ) : rows.length === 0 ? (
                <div className="p-6"><EmptyState title="No students in scope" description="No students matched this class, session, and term." /></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[860px] text-sm">
                    <thead className="bg-surface-muted/40 text-left text-xs uppercase tracking-wide text-text-muted">
                      <tr>
                        <th className="px-4 py-3">Student</th>
                        <th className="px-4 py-3">Academic readiness</th>
                        <th className="px-4 py-3">Average</th>
                        <th className="px-4 py-3">Grade</th>
                        <th className="px-4 py-3">Comment</th>
                        <th className="px-4 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {rows.map((row) => {
                        const canOpen = row.academic_ready || Boolean(row.comment);
                        return (
                          <tr key={row.student_id}>
                            <td className="px-4 py-3">
                              <p className="font-semibold text-text">{row.student_name || row.admission_number}</p>
                              <p className="text-xs text-text-muted">{row.admission_number}</p>
                            </td>
                            <td className="px-4 py-3">
                              <Badge variant={row.academic_ready ? "success" : "warning"}>{titleCase(row.readiness_label)}</Badge>
                            </td>
                            <td className="px-4 py-3 text-text-soft">{row.average ?? "—"}</td>
                            <td className="px-4 py-3 text-text-soft">{row.overall_grade || "—"}</td>
                            <td className="px-4 py-3">
                              <Badge variant={statusVariant(row.comment_status)}>{titleCase(row.comment_status)}</Badge>
                              {row.comment_status === "needs_review" ? (
                                <p className="mt-1 max-w-xs text-xs text-error">Performance or placement context changed after submission. Review and resubmit.</p>
                              ) : null}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <Button
                                type="button"
                                size="small"
                                variant="outline"
                                disabled={!canOpen}
                                onClick={() => openEditor(row)}
                              >
                                <FilePenLine className="h-4 w-4" />
                                {row.comment
                                  ? "Review comment"
                                  : row.academic_ready
                                    ? "Write comment"
                                    : "Waiting for results"}
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </>
        )}
      </div>

      <Modal
        open={Boolean(editor)}
        title={editor ? `Teacher comment · ${editor.row.student_name || editor.row.admission_number}` : "Teacher comment"}
        description="Only saved comments assigned to this student's calculated grade are shown. Review the final wording before submission."
        onClose={() => !busy && setEditor(null)}
        closeOnOverlay={!busy}
      >
        {editor ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 rounded-xl bg-surface-muted/35 p-3 text-sm">
              <div><span className="text-text-muted">Average</span><p className="font-semibold text-text">{editor.row.average ?? "—"}</p></div>
              <div><span className="text-text-muted">Overall grade</span><p className="font-semibold text-text">{editor.row.overall_grade || "—"}</p></div>
            </div>
            <SelectField
              label={`My Grade ${editor.row.overall_grade || ""} comments`}
              value={editor.sourceTemplateId}
              options={editorTemplateOptions}
              onChange={selectTemplate}
              placeholder="Write manually"
            />
            {editor.row.suggested_template ? (
              <div className="rounded-xl border border-primary/15 bg-primary/5 px-3 py-2 text-xs text-text-muted">
                <span className="font-semibold text-text">Default suggestion:</span>{" "}
                {editor.row.suggested_template.text}
              </div>
            ) : null}
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">Class-teacher comment</span>
              <textarea
                className="input-base min-h-36"
                maxLength={2000}
                value={editor.text}
                onChange={(event) => setEditor((current) => ({ ...current, text: event.target.value }))}
              />
            </label>
            {!editor.row.academic_ready ? (
              <div className="rounded-xl border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-amber-800">
                This older draft can be reviewed, but final submission remains unavailable until all expected results are finalized and locked.
              </div>
            ) : null}
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" disabled={busy || !editor.text.trim()} onClick={() => save(false)}>
                {busy ? "Saving..." : "Save Draft"}
              </Button>
              <Button type="button" disabled={busy || !editor.text.trim() || !editor.row.academic_ready} onClick={() => save(true)}>
                <CheckCircle2 className="h-4 w-4" />
                {busy ? "Submitting..." : "Submit"}
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </DashboardLayout>
  );
}

export default TeacherStudentCommentsPage;
