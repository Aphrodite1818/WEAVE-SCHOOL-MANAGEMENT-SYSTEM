import { Archive, CheckCircle2, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import PerformanceRangeInput from "../../components/reporting/PerformanceRangeInput";
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

const rangeKey = (item) => `${Number(item.minimum_score)}:${Number(item.maximum_score)}`;
const rangeLabel = (item) => `${Number(item.minimum_score)}% – ${Number(item.maximum_score)}%`;

function TeacherCommentTemplatesPage() {
  const { showSuccess, showError } = useToast();
  const [summary, setSummary] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editor, setEditor] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [summaryResponse, templateResponse] = await Promise.all([
        reportCommentService.getTeacherCommentSummary(),
        reportCommentService.listTeacherTemplates({ include_archived: includeArchived }),
      ]);
      setSummary(summaryResponse);
      setTemplates(asItems(templateResponse));
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
  const groups = useMemo(() => {
    const grouped = new Map();
    templates.forEach((template) => {
      const key = rangeKey(template);
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(template);
    });
    return Array.from(grouped.values()).sort(
      (left, right) => Number(right[0].minimum_score) - Number(left[0].minimum_score),
    );
  }, [templates]);

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
        await reportCommentService.updateTeacherTemplate(editor.id, payload);
        showSuccess("Comment updated. Existing submitted student comments were not changed.");
      } else {
        await reportCommentService.createTeacherTemplate(payload);
        showSuccess("Class-teacher comment saved for this performance range.");
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
      showSuccess(`Default comment updated for ${rangeLabel(template)}.`);
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
              Save reusable wording for non-overlapping overall-performance ranges. Each range can contain several comments with one personal default.
            </p>
          </div>
          <Button type="button" onClick={() => openCreate()} disabled={!canCreate}>
            <Plus className="h-4 w-4" /> New range comment
          </Button>
        </div>

        {!canCreate && !loading ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-800">
            You are not currently assigned as a class teacher. Existing comments remain preserved, but new comment creation and usage are disabled until you receive a class-teacher assignment.
          </div>
        ) : null}

        <label className="flex items-center gap-2 text-sm font-semibold text-text-soft">
          <input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />
          Include archived comments
        </label>

        {loading ? (
          <LoadingState label="Loading personal comments..." />
        ) : groups.length === 0 ? (
          <Card className="p-6">
            <EmptyState
              title="No saved comments yet"
              description="Create reusable wording for a student's overall-performance percentage range."
            />
          </Card>
        ) : (
          <div className="space-y-4">
            {groups.map((group) => {
              const range = group[0];
              return (
                <Card key={rangeKey(range)} className="p-4 sm:p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="default">{rangeLabel(range)}</Badge>
                        <span className="text-xs text-text-muted">{group.length} comment{group.length === 1 ? "" : "s"}</span>
                      </div>
                      <p className="mt-1 text-xs text-text-muted">Both endpoints are included. Different ranges cannot overlap.</p>
                    </div>
                    {range.status !== "archived" ? (
                      <Button type="button" size="small" variant="outline" onClick={() => openCreate(range)} disabled={busy || !canCreate}>
                        <Plus className="h-4 w-4" /> Add wording
                      </Button>
                    ) : null}
                  </div>
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    {group.map((template) => (
                      <div key={template.id} className="rounded-xl border border-border/70 p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={template.status === "active" ? "success" : "default"}>{template.status}</Badge>
                          {template.is_default ? <Badge variant="success">My default</Badge> : null}
                        </div>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-text-soft">{template.text}</p>
                        <div className="mt-4 flex flex-wrap gap-2 border-t border-border/70 pt-3">
                          <Button type="button" size="small" variant="outline" onClick={() => openEdit(template)} disabled={busy || template.status === "archived" || !canCreate}>Edit</Button>
                          {template.status === "active" && !template.is_default ? (
                            <Button type="button" size="small" variant="outline" onClick={() => makeDefault(template)} disabled={busy || !canCreate}>
                              <CheckCircle2 className="h-4 w-4" /> Make default
                            </Button>
                          ) : null}
                          {template.status === "active" ? (
                            <Button type="button" size="small" variant="outline" onClick={() => setStatus(template, "inactive")} disabled={busy}>Deactivate</Button>
                          ) : template.status === "inactive" ? (
                            <Button type="button" size="small" variant="outline" onClick={() => setStatus(template, "active")} disabled={busy || !canCreate}>Activate</Button>
                          ) : null}
                          {template.status !== "archived" ? (
                            <Button type="button" size="small" variant="outline" onClick={() => setStatus(template, "archived")} disabled={busy}>
                              <Archive className="h-4 w-4" /> Archive
                            </Button>
                          ) : null}
                          <Button type="button" size="small" variant="danger" onClick={() => remove(template)} disabled={busy}>
                            <Trash2 className="h-4 w-4" /> Delete if unused
                          </Button>
                        </div>
                      </div>
                    ))}
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
        description="Choose the student's overall-performance percentage range, then write the wording you want available for that range."
        onClose={() => !busy && setEditor(null)}
        closeOnOverlay={!busy}
      >
        {editor ? (
          <form onSubmit={save} className="space-y-5">
            <PerformanceRangeInput
              minimum={editor.minimum}
              maximum={editor.maximum}
              disabled={busy}
              onChange={({ minimum, maximum }) => setEditor((current) => ({ ...current, minimum, maximum }))}
            />
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">Class-teacher comment</span>
              <textarea
                className="input-base min-h-36"
                maxLength={2000}
                required
                placeholder="e.g. Good overall performance this term. Keep improving."
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
                <span className="font-semibold text-text">Use as my default for this exact range</span>
                <span className="mt-0.5 block text-xs text-text-muted">The first active comment for a range becomes the default automatically. Selecting another one replaces it.</span>
              </span>
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setEditor(null)} disabled={busy}>Cancel</Button>
              <Button type="submit" disabled={busy || !editor.text.trim()}>
                <Save className="h-4 w-4" /> {busy ? "Saving..." : "Save comment"}
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </DashboardLayout>
  );
}

export default TeacherCommentTemplatesPage;
