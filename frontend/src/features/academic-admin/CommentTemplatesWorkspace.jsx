import { Archive, Plus, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { reportCommentService } from "../../services/reportCommentService";
import { Input, WorkspacePanel } from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

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
      showError(getErrorMessage(error, "Could not load principal comment templates."));
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
      name: "",
      text: "",
      gradingScaleIds: [],
      defaultGradingScaleIds: [],
    });

  const openEdit = (template) =>
    setEditor({
      id: template.id,
      name: template.name,
      text: template.text,
      gradingScaleIds: template.grading_scale_ids || [],
      defaultGradingScaleIds: template.default_grading_scale_ids || [],
    });

  const toggleGrade = (scaleId, checked) => {
    setEditor((current) => {
      const gradingScaleIds = checked
        ? [...new Set([...current.gradingScaleIds, scaleId])]
        : current.gradingScaleIds.filter((id) => id !== scaleId);
      return {
        ...current,
        gradingScaleIds,
        defaultGradingScaleIds: current.defaultGradingScaleIds.filter((id) =>
          gradingScaleIds.includes(id),
        ),
      };
    });
  };

  const toggleDefault = (scaleId, checked) => {
    setEditor((current) => ({
      ...current,
      gradingScaleIds: [...new Set([...current.gradingScaleIds, scaleId])],
      defaultGradingScaleIds: checked
        ? [...new Set([...current.defaultGradingScaleIds, scaleId])]
        : current.defaultGradingScaleIds.filter((id) => id !== scaleId),
    }));
  };

  const save = async (event) => {
    event.preventDefault();
    if (!editor?.name.trim() || !editor?.text.trim()) return;
    setBusy(true);
    const payload = {
      name: editor.name.trim(),
      text: editor.text.trim(),
      grading_scale_ids: editor.gradingScaleIds,
      default_grading_scale_ids: editor.defaultGradingScaleIds,
    };
    try {
      if (editor.id) {
        await reportCommentService.updateAdminTemplate(editor.id, payload);
        showSuccess("Principal comment template updated. Historical report text was not changed.");
      } else {
        await reportCommentService.createAdminTemplate(payload);
        showSuccess("Personal principal comment template created.");
      }
      setEditor(null);
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not save principal comment template."));
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (template, status) => {
    setBusy(true);
    try {
      await reportCommentService.updateAdminTemplate(template.id, { status });
      showSuccess(status === "archived" ? "Template archived." : "Template status updated.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not update template status."));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (template) => {
    setBusy(true);
    try {
      await reportCommentService.deleteAdminTemplate(template.id);
      showSuccess("Unused template deleted.");
      await load();
    } catch (error) {
      showError(
        getErrorMessage(
          error,
          "Referenced templates cannot be deleted. Deactivate or archive this template instead.",
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
        description="These templates belong only to your admin account. They suggest principal comments by the existing grading scale; they never serve as class-teacher comments."
        actions={
          <Button type="button" onClick={openCreate} disabled={busy}>
            <Plus className="h-4 w-4" /> New template
          </Button>
        }
      >
        {loading ? (
          <p className="text-sm text-text-muted">Loading templates...</p>
        ) : visibleTemplates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
            No templates in this lifecycle state.
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {visibleTemplates.map((template) => (
              <div key={template.id} className="rounded-xl border border-border/70 bg-surface p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-text">{template.name}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge variant={template.status === "active" ? "success" : "default"}>
                        {template.status}
                      </Badge>
                      {(template.grading_scale_ids || []).map((id) => (
                        <Badge key={id} variant="default">
                          {scaleById.get(id)?.grade || "Grade"}
                          {(template.default_grading_scale_ids || []).includes(id)
                            ? " · Default"
                            : ""}
                        </Badge>
                      ))}
                    </div>
                  </div>
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
                    Edit
                  </Button>
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
            ))}
          </div>
        )}
      </WorkspacePanel>

      <Modal
        open={Boolean(editor)}
        title={editor?.id ? "Edit principal comment template" : "Create principal comment template"}
        description="Map reusable wording to existing grading-scale entries. You may define one personal default per grade."
        onClose={() => !busy && setEditor(null)}
        closeOnOverlay={!busy}
      >
        {editor ? (
          <form onSubmit={save} className="space-y-4">
            <Input
              label="Template name"
              value={editor.name}
              required
              onChange={(event) =>
                setEditor((current) => ({ ...current, name: event.target.value }))
              }
            />
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">
                Principal comment
              </span>
              <textarea
                className="input-base min-h-32"
                maxLength={2000}
                required
                value={editor.text}
                onChange={(event) =>
                  setEditor((current) => ({ ...current, text: event.target.value }))
                }
              />
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              {gradingScales.map((scale) => {
                const selected = editor.gradingScaleIds.includes(scale.id);
                const isDefault = editor.defaultGradingScaleIds.includes(scale.id);
                return (
                  <div key={scale.id} className="rounded-xl border border-border p-3">
                    <label className="flex items-center gap-2 text-sm font-semibold text-text">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={(event) => toggleGrade(scale.id, event.target.checked)}
                      />
                      Grade {scale.grade}
                    </label>
                    <label className="mt-2 flex items-center gap-2 text-xs text-text-muted">
                      <input
                        type="checkbox"
                        checked={isDefault}
                        onChange={(event) => toggleDefault(scale.id, event.target.checked)}
                      />
                      My default for Grade {scale.grade}
                    </label>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" disabled={busy} onClick={() => setEditor(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy || !editor.name.trim() || !editor.text.trim()}>
                <Save className="h-4 w-4" /> {busy ? "Saving..." : "Save template"}
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </>
  );
}

export default CommentTemplatesWorkspace;
