import { Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicLevelService, classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import {
  FormActions,
  Input,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const asItems = (value) => Array.isArray(value) ? value : value?.items || [];
const emptyLevelForm = { name: "", category: "", position: "" };

function AcademicLevelsWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [levels, setLevels] = useState([]);
  const [classes, setClasses] = useState([]);
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [levelForm, setLevelForm] = useState(emptyLevelForm);
  const [editingLevelId, setEditingLevelId] = useState("");
  const [editingLevelForm, setEditingLevelForm] = useState(null);
  const [levelPendingDeletion, setLevelPendingDeletion] = useState(null);
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
      setLevelForm((current) => {
        if (allowedCategories.some((option) => option.value === current.category)) return current;
        return { ...current, category: allowedCategories[0]?.value || "" };
      });
    } catch (error) {
      showError(getErrorMessage(error, "Could not load academic levels."));
    }
  }, [showError]);

  useEffect(() => { load(); }, [load]);

  const selectOptions = useMemo(
    () => categoryOptions.map((option) => ({ value: option.value, label: option.label })),
    [categoryOptions],
  );
  const categoryLabels = useMemo(
    () => new Map(categoryOptions.map((option) => [option.value, option.label])),
    [categoryOptions],
  );

  const createLevel = async (event) => {
    event.preventDefault();
    if (!levelForm.category) return;
    setSaving(true);
    try {
      await academicLevelService.createLevel({
        ...levelForm,
        position: Number(levelForm.position),
      });
      setLevelForm({
        ...emptyLevelForm,
        category: categoryOptions[0]?.value || "",
      });
      showSuccess("Academic level created.");
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

  const deleteEmptyLevel = async () => {
    if (!levelPendingDeletion) return;
    const level = levelPendingDeletion;
    setSaving(level.id);
    try {
      await academicLevelService.removeLevelFromSetup(level.id);
      if (editingLevelId === level.id) {
        setEditingLevelId("");
        setEditingLevelForm(null);
      }
      setLevelPendingDeletion(null);
      showSuccess("Empty academic level deleted.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not delete this academic level."));
    } finally {
      setSaving(false);
    }
  };

  const workspaceTitle = activeTab === "manage" ? "Manage academic levels" : "Academic levels";
  const workspaceDescription = activeTab === "manage"
    ? "Update level names or remove genuinely empty levels."
    : "Review the category, position, and organizational class distribution.";

  return (
    <>
      <WorkspaceGrid
        editor={activeTab === "create" ? (
          <WorkspacePanel
            title="Create academic level"
            description="Levels own curriculum and ordered progression; classes remain optional organization."
          >
            <form className="space-y-3" onSubmit={createLevel}>
              <Input
                label="Level name"
                value={levelForm.name}
                onChange={(event) => setLevelForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="JSS1"
                required
              />
              <SelectControl
                label="Category"
                value={levelForm.category}
                onChange={(value) => setLevelForm((current) => ({ ...current, category: value }))}
                options={selectOptions}
                placeholder="Select an institution category"
                required
              />
              <Input
                label="Position"
                type="number"
                min="1"
                value={levelForm.position}
                onChange={(event) => setLevelForm((current) => ({ ...current, position: event.target.value }))}
                required
              />
              <FormActions submitting={saving} submitLabel="Create level" />
            </form>
          </WorkspacePanel>
        ) : null}
        content={(
          <WorkspacePanel title={workspaceTitle} description={workspaceDescription}>
            <div className="grid max-h-[34rem] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
              {levels.map((item) => {
                const armCount = classes.filter((classroom) => classroom.academic_level_id === item.id).length;
                return (
                  <div key={item.id} className="rounded-2xl border border-border/70 bg-surface p-4">
                    <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <p className="font-semibold text-text">{item.name}</p>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={armCount > 0 ? "default" : "warning"}>
                          {armCount} arm{armCount === 1 ? "" : "s"}
                        </Badge>
                        <Badge variant="default">
                          {categoryLabels.get(item.category) || String(item.category || "").replaceAll("_", " ")} · {item.position}
                        </Badge>
                      </div>
                    </div>
                    <p className="mt-2 text-sm text-text-muted">
                      Automatic progression follows the next configured position. Class and arm are assigned separately.
                    </p>
                    {activeTab === "manage" && editingLevelId === item.id ? (
                      <form className="mt-3 space-y-3 border-t border-border/70 pt-3" onSubmit={updateLevel}>
                        <Input
                          label="Level name"
                          value={editingLevelForm?.name || ""}
                          onChange={(event) => setEditingLevelForm((current) => ({ ...current, name: event.target.value }))}
                          required
                        />
                        <SelectControl
                          label="Category"
                          value={editingLevelForm?.category || ""}
                          onChange={(value) => setEditingLevelForm((current) => ({ ...current, category: value }))}
                          options={selectOptions}
                          required
                        />
                        <Input
                          label="Position"
                          type="number"
                          min="1"
                          value={editingLevelForm?.position || ""}
                          onChange={(event) => setEditingLevelForm((current) => ({ ...current, position: event.target.value }))}
                          required
                        />
                        <FormActions
                          submitting={saving === item.id}
                          submitLabel="Save level"
                          editing
                          onCancel={() => {
                            setEditingLevelId("");
                            setEditingLevelForm(null);
                          }}
                        />
                      </form>
                    ) : activeTab === "manage" ? (
                      <div className="mt-3 grid gap-2 sm:flex sm:flex-wrap">
                        <Button
                          size="small"
                          variant="outline"
                          className="w-full sm:w-auto"
                          onClick={() => {
                            setEditingLevelId(item.id);
                            setEditingLevelForm({
                              name: item.name,
                              category: item.category,
                              position: String(item.position),
                            });
                          }}
                        >
                          Update level
                        </Button>
                        {armCount === 0 ? (
                          <Button
                            size="small"
                            variant="danger"
                            className="w-full sm:w-auto"
                            disabled={saving === item.id}
                            onClick={() => setLevelPendingDeletion(item)}
                          >
                            Delete empty level
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
              {!levels.length ? (
                <div className="rounded-2xl border border-dashed border-border p-6 text-center">
                  <Library className="mx-auto h-7 w-7 text-text-muted" />
                  <p className="mt-2 text-sm text-text-muted">
                    No academic levels yet. Use Create Level to add the first one.
                  </p>
                </div>
              ) : null}
            </div>
          </WorkspacePanel>
        )}
      />
      <TypedConfirmationDialog
        open={Boolean(levelPendingDeletion)}
        title="Delete empty academic level"
        description={`${levelPendingDeletion?.name || "This level"} has no class arms. The backend will still reject deletion if another academic record depends on it.`}
        confirmationText="DELETE_EMPTY_LEVEL"
        confirmLabel="Delete level"
        isLoading={saving === levelPendingDeletion?.id}
        onConfirm={deleteEmptyLevel}
        onCancel={() => setLevelPendingDeletion(null)}
      />
    </>
  );
}

export default AcademicLevelsWorkspace;
