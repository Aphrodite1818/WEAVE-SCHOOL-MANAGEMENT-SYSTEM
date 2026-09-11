import { Archive, CheckCircle2, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { parseApiError } from "../../services/api";
import { reportCommentService } from "../../services/reportCommentService";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const gradeLabel = (scale) =>
  scale ? `${scale.grade}${scale.remark ? ` · ${scale.remark}` : ""}` : "Unknown grade";

const templateGradeId = (template) => template?.grading_scale_ids?.[0] || "";
const templateIsDefault = (template) => {
  const gradeId = templateGradeId(template);
  return Boolean(gradeId && template?.default_grading_scale_ids?.includes(gradeId));
};

function TeacherCommentTemplatesPage() {
  const { showSuccess, showError } = useToast();
  const [summary, setSummary] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [gradingScales, setGradingScales] = useState([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editor, setEditor] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [summaryResponse, templateResponse, gradeResponse] = await Promise.all([
        reportCommentService.getTeacherCommentSummary(),
        reportCommentService.listTeacherTemplates({ include_archived: includeArchived }),
        reportCommentService.listTeacherGradingScales(),
      ]);
      setSummary(summaryResponse);
      setTemplates(asItems(templateResponse));
      setGradingScales(asItems(gradeResponse));
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to load comment templates.").message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeArchived]);

  const canCreate = Number(summary?.class_teacher_class_count || 0) > 0;
  const scaleById = useMemo(
    () => new Map(gradingScales.map((item) => [item.id, item])),
    [gradingScales],
  );

  const openCreate = () =>
    setEditor({
      id: null,
      text: "",
      gradingScaleId: gradingScales[0]?.id || "",
      isDefault: false,
    });

  const openEdit = (template) =>
    setEditor({
      id: template.id,
      text: template.text,
      gradingScaleId: templateGradeId(template),
      isDefault: templateIsDefault(template),
    });

  const save = async (event) => {
    event.preventDefault();
    if (!editor?.text.trim() || !editor?.gradingScaleId) return;
    setBusy(true);
    try {
      if (editor.id) {
        await reportCommentService.updateTeacherTemplate(editor.id, {
          text: editor.text.trim(),
          is_default: editor.isDefault,
        });
        showSuccess("Comment updated. Existing submitted student comments were not changed.");
      } else {
        await reportCommentService.createTeacherTemplate({
          text: editor.text.trim(),
          grading_scale_id: editor.gradingScaleId,
          is_default: editor.isDefault,
        });
        showSuccess("Personal class-teacher comment saved for this grade.");
      }
      setEditor(null);
      await load();
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to save comment.").message);
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (template, status) => {
    setBusy(true);
    try {
      await reportCommentService.updateTeacherTemplate(template.id, { status });
      showSuccess(status === "archived" ? "Comment archived." : "Comment status updated.");
      await load();
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to update comment status.").message);
    } finally {
      setBusy(false);
    }
  };

  const makeDefault = async (template) => {
    setBusy(true);
    try {
      await reportCommentService.updateTeacherTemplate(template.id, { is_default: true });
      showSuccess(`Default comment updated for Grade ${scaleById.get(templateGradeId(template))?.grade || ""}.`);
      await load();
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to make this the default comment.").message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (template) => {
    setBusy(true);
    try {
      await reportCommentService.deleteTeacherTemplate(template.id);
      showSuccess("Unused comment deleted.");
      await load();
    } catch (requestError) {
      showError(
        parseApiError(
          requestError,
          "This comment is referenced historically and cannot be deleted. Deactivate or archive it instead.",
        ).message,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <DashboardLayout role="teacher" title="My Comment Templates">
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-text sm:text-[1.65rem]">
              My Comment Templates
            </h1>
            <p className="mt-1 text-sm text-text-muted">
              Save the actual class-teacher comment for one grade. You can keep several comments for the same grade, with one personal default.
            </p>
          </div>
          <Button
            type="button"
            onClick={openCreate}
            disabled={!canCreate || gradingScales.length === 0}
          >
            <Plus className="h-4 w-4" />
            New comment
          </Button>
        </div>

        {!canCreate && !loading ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-800">
            You are not currently assigned as a class teacher. Existing comments remain preserved, but new comment creation and usage are disabled until you receive a class-teacher assignment.
          </div>
        ) : null}

        <label className="flex items-center gap-2 text-sm font-semibold text-text-soft">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
          />
          Include archived comments
        </label>

        {loading ? (
          <LoadingState label="Loading personal comments..." />
        ) : gradingScales.length === 0 ? (
          <Card className="p-6">
            <EmptyState
              title="No grading scale is available"
              description="The school must configure grades before class teachers can save grade-linked comments."
            />
          </Card>
        ) : templates.length === 0 ? (
          <Card className="p-6">
            <EmptyState
              title="No saved comments yet"
              description="Create reusable wording for grades you commonly comment on."
            />
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {templates.map((template) => {
              const gradeId = templateGradeId(template);
              const scale = scaleById.get(gradeId);
              const isDefault = templateIsDefault(template);
              return (
                <Card key={template.id} className="p-4 sm:p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="default">Grade {scale?.grade || "—"}</Badge>
                    <Badge variant={template.status === "active" ? "success" : "default"}>
                      {template.status}
                    </Badge>
                    {isDefault ? <Badge variant="success">Default</Badge> : null}
                  </div>
                  <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-text-soft">
                    {template.text}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2 border-t border-border/70 pt-3">
                    <Button
                      type="button"
                      size="small"
                      variant="outline"
                      onClick={() => openEdit(template)}
                      disabled={busy || template.status === "archived" || !canCreate}
                    >
                      Edit comment
                    </Button>
                    {template.status === "active" && !isDefault ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        onClick={() => makeDefault(template)}
                        disabled={busy || !canCreate}
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Make default
                      </Button>
                    ) : null}
                    {template.status === "active" ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        onClick={() => setStatus(template, "inactive")}
                        disabled={busy}
                      >
                        Deactivate
                      </Button>
                    ) : template.status === "inactive" ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        onClick={() => setStatus(template, "active")}
                        disabled={busy || !canCreate}
                      >
                        Activate
                      </Button>
                    ) : null}
                    {template.status !== "archived" ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        onClick={() => setStatus(template, "archived")}
                        disabled={busy}
                      >
                        <Archive className="h-4 w-4" />
                        Archive
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="small"
                      variant="danger"
                      onClick={() => remove(template)}
                      disabled={busy}
                    >
                      <Trash2 className="h-4 w-4" />
                      Delete if unused
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      <Modal
        open={Boolean(editor)}
        title={editor?.id ? "Edit teacher comment" : "Create teacher comment"}
        description={
          editor?.id
            ? "The grade stays fixed. Edit the wording or make this your default comment for that grade."
            : "Write the comment exactly as you want it used and assign it to one grade."
        }
        onClose={() => !busy && setEditor(null)}
        closeOnOverlay={!busy}
      >
        {editor ? (
          <form onSubmit={save} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">Grade</span>
              <select
                className="input-base"
                value={editor.gradingScaleId}
                disabled={Boolean(editor.id)}
                required
                onChange={(event) =>
                  setEditor((current) => ({ ...current, gradingScaleId: event.target.value }))
                }
              >
                {gradingScales.map((scale) => (
                  <option key={scale.id} value={scale.id}>
                    {gradeLabel(scale)}
                  </option>
                ))}
              </select>
              {editor.id ? (
                <p className="mt-1 text-xs text-text-muted">
                  Create another comment if you want separate wording for another grade.
                </p>
              ) : null}
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">
                Class-teacher comment
              </span>
              <textarea
                className="input-base min-h-36"
                maxLength={2000}
                required
                placeholder="e.g. An excellent performance this term. Keep it up."
                value={editor.text}
                onChange={(event) =>
                  setEditor((current) => ({ ...current, text: event.target.value }))
                }
              />
            </label>
            <label className="flex items-start gap-3 rounded-xl border border-border/70 p-3 text-sm text-text-soft">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={editor.isDefault}
                disabled={Boolean(editor.id && editor.isDefault)}
                onChange={(event) =>
                  setEditor((current) => ({ ...current, isDefault: event.target.checked }))
                }
              />
              <span>
                <span className="font-semibold text-text">Use as my default for this grade</span>
                <span className="mt-0.5 block text-xs text-text-muted">
                  Your first active comment for a grade becomes the default automatically. Choosing another comment as default replaces the old default.
                </span>
              </span>
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setEditor(null)} disabled={busy}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={busy || !editor.text.trim() || !editor.gradingScaleId}
              >
                <Save className="h-4 w-4" />
                {busy ? "Saving..." : "Save comment"}
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </DashboardLayout>
  );
}

export default TeacherCommentTemplatesPage;
