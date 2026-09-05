import { Archive, CheckCircle2, Plus, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { reportCommentService } from "../../services/reportCommentService";
import { WorkspacePanel } from "./AcademicWorkspacePrimitives";

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

function CommentTemplatesWorkspace({ activeTab }) {
  const { showSuccess, showError } = useToast();
  const [templates, setTemplates] = useState([]);
  const [gradingScales, setGradingScales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [templateResponse, gradeResponse] = await Promise.all([
        reportCommentService.listAdminTemplates({ include_archived: true }),
        academicService.listGradingScales({ active_only: true, limit: 100 }),
      ]);
      setTemplates(asItems(templateResponse));
      setGradingScales(asItems(gradeResponse));
    } catch (error) {
      showError(getErrorMessage(error, "Could not load principal comments."));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    load();
  }, [load]);

  const scaleById = useMemo(
    () => new Map(gradingScales.map((item) => [item.id, item])),
    [gradingScales],
  );
  const visibleTemplates = useMemo(() => {
    if (activeTab === "active") return templates.filter((item) => item.status === "active");
    if (activeTab === "inactive") return templates.filter((item) => item.status === "inactive");
    if (activeTab === "archived") return templates.filter((item) => item.status === "archived");
    return templates;
  }, [activeTab, templates]);

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
        await reportCommentService.updateAdminTemplate(editor.id, {
          text: editor.text.trim(),
          is_default: editor.isDefault,
        });
        showSuccess("Principal comment updated. Historical report text was not changed.");
      } else {
        await reportCommentService.createAdminTemplate({
          text: editor.text.trim(),
          grading_scale_id: editor.gradingScaleId,
          is_default: editor.isDefault,
        });
        showSuccess("Principal comment saved for this grade.");
      }
      setEditor(null);
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not save principal comment."));
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (template, status) => {
    setBusy(true);
    try {
      await reportCommentService.updateAdminTemplate(template.id, { status });
      showSuccess(status === "archived" ? "Comment archived." : "Comment status updated.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not update comment status."));
    } finally {
      setBusy(false);
    }
  };

  const makeDefault = async (template) => {
    setBusy(true);
    try {
      await reportCommentService.updateAdminTemplate(template.id, { is_default: true });
      showSuccess(`Default principal comment updated for Grade ${scaleById.get(templateGradeId(template))?.grade || ""}.`);
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not make this the default comment."));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (template) => {
    setBusy(true);
    try {
      await reportCommentService.deleteAdminTemplate(template.id);
      showSuccess("Unused comment deleted.");
      await load();
    } catch (error) {
      showError(
        getErrorMessage(
          error,
          "Referenced comments cannot be deleted. Deactivate or archive this comment instead.",
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <WorkspacePanel
        title="Principal comment templates"
        description="Create the actual principal comment, assign it to one grade, and choose the default wording for that grade. You can save several comments for the same grade."
        actions={
          <Button type="button" onClick={openCreate} disabled={busy || gradingScales.length === 0}>
            <Plus className="h-4 w-4" /> New comment
          </Button>
        }
      >
        {loading ? (
          <p className="text-sm text-text-muted">Loading comments...</p>
        ) : gradingScales.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
            Create grading-scale entries first. Comments are assigned to the existing school grades.
          </div>
        ) : visibleTemplates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
            No comments in this lifecycle state.
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {visibleTemplates.map((template) => {
              const gradeId = templateGradeId(template);
              const scale = scaleById.get(gradeId);
              const isDefault = templateIsDefault(template);
              return (
                <div key={template.id} className="rounded-xl border border-border/70 bg-surface p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="default">Grade {scale?.grade || "—"}</Badge>
                    <Badge variant={template.status === "active" ? "success" : "default"}>
                      {template.status}
                    </Badge>
                    {isDefault ? (
                      <Badge variant="success">Default</Badge>
                    ) : null}
                  </div>
                  <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-text-soft">
                    {template.text}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2 border-t border-border/70 pt-3">
                    <Button
                      type="button"
                      size="small"
                      variant="outline"
                      disabled={busy || template.status === "archived"}
                      onClick={() => openEdit(template)}
                    >
                      Edit comment
                    </Button>
                    {template.status === "active" && !isDefault ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        disabled={busy}
                        onClick={() => makeDefault(template)}
                      >
                        <CheckCircle2 className="h-4 w-4" /> Make default
                      </Button>
                    ) : null}
                    {template.status === "active" ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        disabled={busy}
                        onClick={() => setStatus(template, "inactive")}
                      >
                        Deactivate
                      </Button>
                    ) : template.status === "inactive" ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        disabled={busy}
                        onClick={() => setStatus(template, "active")}
                      >
                        Activate
                      </Button>
                    ) : null}
                    {template.status !== "archived" ? (
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        disabled={busy}
                        onClick={() => setStatus(template, "archived")}
                      >
                        <Archive className="h-4 w-4" /> Archive
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="small"
                      variant="danger"
                      disabled={busy}
                      onClick={() => remove(template)}
                    >
                      <Trash2 className="h-4 w-4" /> Delete if unused
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </WorkspacePanel>

      <Modal
        open={Boolean(editor)}
        title={editor?.id ? "Edit principal comment" : "Create principal comment"}
        description={
          editor?.id
            ? "The grade stays fixed. Edit the wording or make this the default comment for that grade."
            : "Write the comment exactly as it should appear and assign it to one grade."
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
                  To use different wording for another grade, create another comment.
                </p>
              ) : null}
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">
                Principal comment
              </span>
              <textarea
                className="input-base min-h-36"
                maxLength={2000}
                required
                placeholder="e.g. Very good performance. Keep it up."
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
                  The first active comment for a grade becomes its default automatically. To replace a default, choose “Make default” on another comment for the same grade.
                </span>
              </span>
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" disabled={busy} onClick={() => setEditor(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy || !editor.text.trim() || !editor.gradingScaleId}>
                <Save className="h-4 w-4" /> {busy ? "Saving..." : "Save comment"}
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </>
  );
}

export default CommentTemplatesWorkspace;
