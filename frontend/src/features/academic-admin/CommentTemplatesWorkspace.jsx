import { Archive, CheckCircle2, Plus, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import PerformanceRangeInput from "../../components/reporting/PerformanceRangeInput";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { reportCommentService } from "../../services/reportCommentService";
import { WorkspacePanel } from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const rangeKey = (item) => `${Number(item.minimum_score)}:${Number(item.maximum_score)}`;
const rangeLabel = (item) => `${Number(item.minimum_score)}% – ${Number(item.maximum_score)}%`;

function CommentTemplatesWorkspace({ activeTab }) {
  const { showSuccess, showError } = useToast();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setTemplates(
        asItems(await reportCommentService.listAdminTemplates({ include_archived: true })),
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load principal comments."));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    load();
  }, [load]);

  const visibleTemplates = useMemo(() => {
    if (activeTab === "active") return templates.filter((item) => item.status === "active");
    if (activeTab === "inactive") return templates.filter((item) => item.status === "inactive");
    if (activeTab === "archived") return templates.filter((item) => item.status === "archived");
    return templates;
  }, [activeTab, templates]);

  const groups = useMemo(() => {
    const grouped = new Map();
    visibleTemplates.forEach((template) => {
      const key = rangeKey(template);
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(template);
    });
    return Array.from(grouped.values()).sort(
      (left, right) => Number(right[0].minimum_score) - Number(left[0].minimum_score),
    );
  }, [visibleTemplates]);

  const openCreate = (range = null) =>
    setEditor({
      id: null,
      text: "",
      minimum: range ? Number(range.minimum_score) : 60,
      maximum: range ? Number(range.maximum_score) : 70,
      isDefault: false,
    });

  const openEdit = (template) =>
    setEditor({
      id: template.id,
      text: template.text,
      minimum: Number(template.minimum_score),
      maximum: Number(template.maximum_score),
      isDefault: Boolean(template.is_default),
    });

  const save = async (event) => {
    event.preventDefault();
    if (!editor?.text.trim()) return;
    setBusy(true);
    const payload = {
      text: editor.text.trim(),
      minimum_score: editor.minimum,
      maximum_score: editor.maximum,
      is_default: editor.isDefault,
    };
    try {
      if (editor.id) {
        await reportCommentService.updateAdminTemplate(editor.id, payload);
        showSuccess("Principal comment updated. Historical report text was not changed.");
      } else {
        await reportCommentService.createAdminTemplate(payload);
        showSuccess("Principal comment saved for this performance range.");
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
      showSuccess(`Default principal comment updated for ${rangeLabel(template)}.`);
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
        description="Define non-overlapping overall-performance ranges. Each range can keep several comments, but exactly one active comment is the default used by automatic report generation."
        actions={
          <Button type="button" onClick={() => openCreate()} disabled={busy}>
            <Plus className="h-4 w-4" /> New range comment
          </Button>
        }
      >
        {loading ? (
          <p className="text-sm text-text-muted">Loading comments...</p>
        ) : groups.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
            No comments in this lifecycle state.
          </div>
        ) : (
          <div className="space-y-4">
            {groups.map((group) => {
              const range = group[0];
              return (
                <section key={rangeKey(range)} className="rounded-2xl border border-border/70 bg-surface p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="default">{rangeLabel(range)}</Badge>
                        <span className="text-xs text-text-muted">{group.length} comment{group.length === 1 ? "" : "s"}</span>
                      </div>
                      <p className="mt-1 text-xs text-text-muted">
                        Scores at both boundaries belong to this range. Other configured ranges cannot overlap it.
                      </p>
                    </div>
                    {range.status !== "archived" ? (
                      <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => openCreate(range)}>
                        <Plus className="h-4 w-4" /> Add wording
                      </Button>
                    ) : null}
                  </div>

                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    {group.map((template) => (
                      <div key={template.id} className="rounded-xl border border-border/70 bg-surface-muted/20 p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={template.status === "active" ? "success" : "default"}>{template.status}</Badge>
                          {template.is_default ? <Badge variant="success">System default</Badge> : null}
                        </div>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-text-soft">{template.text}</p>
                        <div className="mt-4 flex flex-wrap gap-2 border-t border-border/70 pt-3">
                          <Button type="button" size="small" variant="outline" disabled={busy || template.status === "archived"} onClick={() => openEdit(template)}>
                            Edit
                          </Button>
                          {template.status === "active" && !template.is_default ? (
                            <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => makeDefault(template)}>
                              <CheckCircle2 className="h-4 w-4" /> Make default
                            </Button>
                          ) : null}
                          {template.status === "active" ? (
                            <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => setStatus(template, "inactive")}>Deactivate</Button>
                          ) : template.status === "inactive" ? (
                            <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => setStatus(template, "active")}>Activate</Button>
                          ) : null}
                          {template.status !== "archived" ? (
                            <Button type="button" size="small" variant="outline" disabled={busy} onClick={() => setStatus(template, "archived")}>
                              <Archive className="h-4 w-4" /> Archive
                            </Button>
                          ) : null}
                          <Button type="button" size="small" variant="danger" disabled={busy} onClick={() => remove(template)}>
                            <Trash2 className="h-4 w-4" /> Delete if unused
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </WorkspacePanel>

      <Modal
        open={Boolean(editor)}
        title={editor?.id ? "Edit principal comment" : "Create principal comment"}
        description="Choose the student's overall-performance percentage range, then write the wording used for that range."
        onClose={() => !busy && setEditor(null)}
        closeOnOverlay={!busy}
      >
        {editor ? (
          <form onSubmit={save} className="space-y-5">
            <PerformanceRangeInput
              minimum={editor.minimum}
              maximum={editor.maximum}
              disabled={busy}
              onChange={({ minimum, maximum }) =>
                setEditor((current) => ({ ...current, minimum, maximum }))
              }
            />
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">Principal comment</span>
              <textarea
                className="input-base min-h-36"
                maxLength={2000}
                required
                placeholder="e.g. Good overall performance. Keep building on this progress."
                value={editor.text}
                onChange={(event) => setEditor((current) => ({ ...current, text: event.target.value }))}
              />
            </label>
            <label className="flex items-start gap-3 rounded-xl border border-border/70 p-3 text-sm text-text-soft">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={editor.isDefault}
                disabled={Boolean(editor.id && editor.isDefault)}
                onChange={(event) => setEditor((current) => ({ ...current, isDefault: event.target.checked }))}
              />
              <span>
                <span className="font-semibold text-text">Use as the system default for this exact range</span>
                <span className="mt-0.5 block text-xs text-text-muted">
                  The first active comment for a range becomes its default automatically. Making another comment default replaces the old default for that same range.
                </span>
              </span>
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" disabled={busy} onClick={() => setEditor(null)}>Cancel</Button>
              <Button type="submit" disabled={busy || !editor.text.trim()}>
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
