import { useEffect, useMemo, useState } from "react";
import { Archive, Plus, Save, Trash2 } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
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
  `${scale.grade}${scale.remark ? ` · ${scale.remark}` : ""}`;

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
        await reportCommentService.updateTeacherTemplate(editor.id, payload);
        showSuccess("Template updated. Existing student comments were not changed.");
      } else {
        await reportCommentService.createTeacherTemplate(payload);
        showSuccess("Personal teacher comment template created.");
      }
      setEditor(null);
      await load();
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to save template.").message);
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (template, status) => {
    setBusy(true);
    try {
      await reportCommentService.updateTeacherTemplate(template.id, { status });
      showSuccess(status === "archived" ? "Template archived." : "Template status updated.");
      await load();
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to update template status.").message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (template) => {
    setBusy(true);
    try {
      await reportCommentService.deleteTeacherTemplate(template.id);
      showSuccess("Unused template deleted.");
      await load();
    } catch (requestError) {
      showError(
        parseApiError(
          requestError,
          "This template is referenced historically and cannot be deleted. Deactivate or archive it instead.",
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
              Personal class-teacher wording mapped to the school grading scale. Templates never alter historical submitted comments.
            </p>
          </div>
          <Button type="button" onClick={openCreate} disabled={!canCreate}>
            <Plus className="h-4 w-4" />
            New template
          </Button>
        </div>

        {!canCreate && !loading ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-800">
            You are not currently assigned as a class teacher. Existing templates remain available for history, but new template creation and usage are disabled until you receive a class-teacher assignment.
          </div>
        ) : null}

        <label className="flex items-center gap-2 text-sm font-semibold text-text-soft">
          <input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />
          Include archived templates
        </label>

        {loading ? (
          <LoadingState label="Loading personal templates..." />
        ) : templates.length === 0 ? (
          <Card className="p-6">
            <EmptyState title="No comment templates yet" description="Create reusable wording for grades you commonly comment on." />
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {templates.map((template) => (
              <Card key={template.id} className="p-4 sm:p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold text-text">{template.name}</h2>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge variant={template.status === "active" ? "success" : "default"}>{template.status}</Badge>
                      {(template.grading_scale_ids || []).map((id) => (
                        <Badge key={id} variant="default">
                          {scaleById.get(id)?.grade || "Grade"}
                          {(template.default_grading_scale_ids || []).includes(id) ? " · Default" : ""}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
                <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-text-soft">{template.text}</p>
                <div className="mt-4 flex flex-wrap gap-2 border-t border-border/70 pt-3">
                  <Button type="button" size="small" variant="outline" onClick={() => openEdit(template)} disabled={busy || template.status === "archived"}>
                    Edit
                  </Button>
                  {template.status === "active" ? (
                    <Button type="button" size="small" variant="outline" onClick={() => setStatus(template, "inactive")} disabled={busy}>
                      Deactivate
                    </Button>
                  ) : template.status === "inactive" ? (
                    <Button type="button" size="small" variant="outline" onClick={() => setStatus(template, "active")} disabled={busy || !canCreate}>
                      Activate
                    </Button>
                  ) : null}
                  {template.status !== "archived" ? (
                    <Button type="button" size="small" variant="outline" onClick={() => setStatus(template, "archived")} disabled={busy}>
                      <Archive className="h-4 w-4" />
                      Archive
                    </Button>
                  ) : null}
                  <Button type="button" size="small" variant="danger" onClick={() => remove(template)} disabled={busy}>
                    <Trash2 className="h-4 w-4" />
                    Delete if unused
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={Boolean(editor)}
        title={editor?.id ? "Edit teacher comment template" : "Create teacher comment template"}
        description="Choose the grades this wording applies to and optionally make it your personal default for a grade."
        onClose={() => !busy && setEditor(null)}
        closeOnOverlay={!busy}
      >
        {editor ? (
          <form onSubmit={save} className="space-y-4">
            <Input label="Template name" value={editor.name} required onChange={(event) => setEditor((current) => ({ ...current, name: event.target.value }))} />
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">Template text</span>
              <textarea className="input-base min-h-32" maxLength={2000} required value={editor.text} onChange={(event) => setEditor((current) => ({ ...current, text: event.target.value }))} />
            </label>
            <div>
              <p className="text-sm font-semibold text-text-soft">Applies to grades</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {gradingScales.map((scale) => {
                  const selected = editor.gradingScaleIds.includes(scale.id);
                  const isDefault = editor.defaultGradingScaleIds.includes(scale.id);
                  return (
                    <div key={scale.id} className="rounded-xl border border-border p-3">
                      <label className="flex items-center gap-2 text-sm font-semibold text-text">
                        <input type="checkbox" checked={selected} onChange={(event) => toggleGrade(scale.id, event.target.checked)} />
                        {gradeLabel(scale)}
                      </label>
                      <label className="mt-2 flex items-center gap-2 text-xs text-text-muted">
                        <input type="checkbox" checked={isDefault} onChange={(event) => toggleDefault(scale.id, event.target.checked)} />
                        My default for Grade {scale.grade}
                      </label>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setEditor(null)} disabled={busy}>Cancel</Button>
              <Button type="submit" disabled={busy || !editor.name.trim() || !editor.text.trim()}>
                <Save className="h-4 w-4" />
                {busy ? "Saving..." : "Save template"}
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </DashboardLayout>
  );
}

export default TeacherCommentTemplatesPage;
