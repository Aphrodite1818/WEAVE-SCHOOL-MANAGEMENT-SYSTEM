import { Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicLevelService, classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import {
  FormActions,
  Input,
  RecordList,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);
const emptyLevelForm = { name: "", category: "", position: "" };

function AcademicLevelsWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [levels, setLevels] = useState([]);
  const [classes, setClasses] = useState([]);
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [levelForm, setLevelForm] = useState(emptyLevelForm);
  const [editingLevelId, setEditingLevelId] = useState("");
  const [editingLevelForm, setEditingLevelForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [levelRows, classRows, categoryRows] = await Promise.all([
        academicLevelService.getLevels({ includeArchived: true }),
        classService.getClasses({ includeArchived: true }),
        academicLevelService.getCategories(),
      ]);
      const allowedCategories = asItems(categoryRows);
      setLevels(asItems(levelRows));
      setClasses(asItems(classRows));
      setCategoryOptions(allowedCategories);
      setLevelForm((current) =>
        allowedCategories.some((option) => option.value === current.category)
          ? current
          : { ...current, category: allowedCategories[0]?.value || "" },
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load academic levels."));
    }
  }, [showError]);

  useEffect(() => {
    load();
  }, [load]);

  const selectOptions = useMemo(
    () => categoryOptions.map((option) => ({ value: option.value, label: option.label })),
    [categoryOptions],
  );
  const categoryLabels = useMemo(
    () => new Map(categoryOptions.map((option) => [option.value, option.label])),
    [categoryOptions],
  );
  const classCounts = useMemo(() => {
    const counts = new Map();
    classes.forEach((row) => counts.set(row.academic_level_id, (counts.get(row.academic_level_id) || 0) + 1));
    return counts;
  }, [classes]);
  const visibleLevels = useMemo(
    () =>
      ["draft", "active", "inactive", "archived"].includes(activeTab)
        ? levels.filter((row) => String(row.status).toLowerCase() === activeTab)
        : levels,
    [activeTab, levels],
  );

  const createLevel = async (event) => {
    event.preventDefault();
    if (!levelForm.category) return;
    setSaving(true);
    try {
      await academicLevelService.createLevel({ ...levelForm, position: Number(levelForm.position) });
      setLevelForm({ ...emptyLevelForm, category: categoryOptions[0]?.value || "" });
      showSuccess("Academic level created as draft.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not create academic level."));
    } finally {
      setSaving(false);
    }
  };

  const updateLevel = async (event) => {
    event.preventDefault();
    if (!editingLevelId || !editingLevelForm?.name.trim() || !editingLevelForm?.category) return;
    setSaving(editingLevelId);
    try {
      await academicLevelService.updateLevel(editingLevelId, {
        ...editingLevelForm,
        name: editingLevelForm.name.trim(),
        position: Number(editingLevelForm.position),
      });
      setEditingLevelId("");
      setEditingLevelForm(null);
      showSuccess("Academic level updated.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not update this academic level."));
    } finally {
      setSaving(false);
    }
  };

  const runPendingAction = async () => {
    if (!pendingAction) return;
    const { item, action } = pendingAction;
    setSaving(item.id);
    try {
      if (action === "activate") await academicLevelService.activateLevel(item.id);
      if (action === "deactivate") await academicLevelService.deactivateLevel(item.id);
      if (action === "archive") await academicLevelService.archiveLevel(item.id);
      if (action === "restore") await academicLevelService.restoreLevel(item.id);
      if (action === "delete") await academicLevelService.removeLevelFromSetup(item.id);
      showSuccess(`Academic level ${action}d.`);
      setPendingAction(null);
      await load();
    } catch (error) {
      showError(getErrorMessage(error, `Could not ${action} this academic level.`));
    } finally {
      setSaving(false);
    }
  };

  const actionConfig = pendingAction
    ? {
        activate: ["Activate academic level", "ACTIVATE_ACADEMIC_LEVEL", "Activate"],
        deactivate: ["Deactivate academic level", "DEACTIVATE_ACADEMIC_LEVEL", "Deactivate"],
        archive: ["Archive academic level", "ARCHIVE_ACADEMIC_LEVEL", "Archive"],
        restore: ["Restore academic level", "RESTORE_ACADEMIC_LEVEL", "Restore"],
        delete: ["Delete empty level", "DELETE_EMPTY_LEVEL", "Delete"],
      }[pendingAction.action]
    : null;

  return (
    <>
      <WorkspaceGrid
        editor={
          activeTab === "create" || editingLevelId ? (
            <WorkspacePanel title={editingLevelId ? "Update level" : "Create academic level"} description="Levels own curriculum and ordered progression; classes remain optional organization.">
              <form className="space-y-3" onSubmit={editingLevelId ? updateLevel : createLevel}>
                <Input label="Level name" value={editingLevelId ? editingLevelForm?.name || "" : levelForm.name} onChange={(event) => editingLevelId ? setEditingLevelForm((current) => ({ ...current, name: event.target.value })) : setLevelForm((current) => ({ ...current, name: event.target.value }))} placeholder="JSS1" required />
                <SelectControl label="Category" value={editingLevelId ? editingLevelForm?.category || "" : levelForm.category} onChange={(value) => editingLevelId ? setEditingLevelForm((current) => ({ ...current, category: value })) : setLevelForm((current) => ({ ...current, category: value }))} options={selectOptions} required />
                <Input label="Position" type="number" min="1" value={editingLevelId ? editingLevelForm?.position || "" : levelForm.position} onChange={(event) => editingLevelId ? setEditingLevelForm((current) => ({ ...current, position: event.target.value })) : setLevelForm((current) => ({ ...current, position: event.target.value }))} required />
                <FormActions submitting={Boolean(saving)} submitLabel={editingLevelId ? "Save level" : "Create level"} editing={Boolean(editingLevelId)} onCancel={() => { setEditingLevelId(""); setEditingLevelForm(null); }} />
              </form>
            </WorkspacePanel>
          ) : null
        }
        content={
          activeTab === "create" && !editingLevelId ? null : (
            <RecordList
              title="Academic levels"
              description="The lifecycle controls whether a level can receive classes, curriculum, enrollments, and progression work."
              items={visibleLevels}
              listClassName="max-h-[34rem] overflow-y-auto"
              emptyIcon={Library}
              emptyTitle="No academic levels"
              emptyDescription="Create the first level to begin configuring the academic structure."
              renderTitle={(item) => item.name}
              renderMeta={(item) => `${categoryLabels.get(item.category) || String(item.category).replaceAll("_", " ")} · Position ${item.position}`}
              renderDescription={(item) => `${classCounts.get(item.id) || 0} class arms · Progression follows the next configured position.`}
              renderStatus={(item) => item.status}
              onEdit={(item) => {
                setEditingLevelId(item.id);
                setEditingLevelForm({ name: item.name, category: item.category, position: String(item.position) });
              }}
              canEdit={(item) => item.status !== "archived"}
              renderActions={(item) => (
                <>
                  {["draft", "inactive"].includes(item.status) ? <Button size="small" variant="outline" disabled={saving === item.id} onClick={() => setPendingAction({ item, action: "activate" })}>Activate</Button> : null}
                  {item.status === "active" ? <Button size="small" variant="outline" disabled={saving === item.id} onClick={() => setPendingAction({ item, action: "deactivate" })}>Deactivate</Button> : null}
                  {item.status === "inactive" ? <Button size="small" variant="outline" disabled={saving === item.id} onClick={() => setPendingAction({ item, action: "archive" })}>Archive</Button> : null}
                  {item.status === "archived" ? <Button size="small" variant="outline" disabled={saving === item.id} onClick={() => setPendingAction({ item, action: "restore" })}>Restore</Button> : null}
                  {item.status === "draft" && !classCounts.get(item.id) ? <Button size="small" variant="danger" disabled={saving === item.id} onClick={() => setPendingAction({ item, action: "delete" })}>Delete</Button> : null}
                </>
              )}
            />
          )
        }
      />
      <TypedConfirmationDialog open={Boolean(pendingAction)} title={actionConfig?.[0]} description={`${pendingAction?.item?.name || "This level"} will move through the supported academic-level lifecycle. The backend will reject unsafe transitions with live dependencies.`} confirmationText={actionConfig?.[1] || ""} confirmLabel={actionConfig?.[2]} variant={["deactivate", "archive", "delete"].includes(pendingAction?.action) ? "danger" : "primary"} isLoading={saving === pendingAction?.item?.id} onConfirm={runPendingAction} onCancel={() => setPendingAction(null)} />
    </>
  );
}

export default AcademicLevelsWorkspace;
