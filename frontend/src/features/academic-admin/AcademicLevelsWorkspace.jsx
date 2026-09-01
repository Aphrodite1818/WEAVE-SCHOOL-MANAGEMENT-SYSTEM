import { Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import ConfirmDialog from "../../components/shared/ConfirmDialog";
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
import {
  categorySupportsDepartments,
  normalizeSpecializationTermPosition,
} from "./academicDepartmentCapability";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);
const emptyLevelForm = {
  name: "",
  category: "",
  position: "",
  specialization_required_from_term_position: "",
};
const specializationOptions = [
  { value: "", label: "Optional — classes may remain general" },
  { value: "1", label: "Required from First Term" },
  { value: "2", label: "Required from Second Term" },
  { value: "3", label: "Required from Third Term" },
];
const specializationLabel = (position) =>
  ({
    1: "required from First Term",
    2: "required from Second Term",
    3: "required from Third Term",
  })[Number(position)] || "optional";

function AcademicLevelsWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
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
          : {
              ...current,
              category: allowedCategories[0]?.value || "",
              specialization_required_from_term_position: "",
            },
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
    classes.forEach((row) =>
      counts.set(row.academic_level_id, (counts.get(row.academic_level_id) || 0) + 1),
    );
    return counts;
  }, [classes]);
  const visibleLevels = useMemo(
    () =>
      ["draft", "active", "inactive", "archived"].includes(activeTab)
        ? levels.filter((row) => String(row.status).toLowerCase() === activeTab)
        : levels,
    [activeTab, levels],
  );
  const editingLevel = useMemo(
    () => levels.find((row) => row.id === editingLevelId) || null,
    [editingLevelId, levels],
  );
  const activeForm = editingLevelId ? editingLevelForm : levelForm;
  const activeCategory = activeForm?.category || "";
  const selectedCategorySupportsDepartments = categorySupportsDepartments(
    categoryOptions,
    activeCategory,
  );
  const structuralFieldsLocked = Boolean(
    editingLevel && editingLevel.status !== "draft",
  );

  const selectView = (view) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", view);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  const closeEditor = () => {
    setEditingLevelId("");
    setEditingLevelForm(null);
    setLevelForm({
      ...emptyLevelForm,
      category: categoryOptions[0]?.value || "",
    });
    selectView("overview");
  };

  const updateFormCategory = (value) => {
    const update = (current) => ({
      ...current,
      category: value,
      specialization_required_from_term_position: categorySupportsDepartments(
        categoryOptions,
        value,
      )
        ? current.specialization_required_from_term_position
        : "",
    });
    if (editingLevelId) {
      setEditingLevelForm(update);
    } else {
      setLevelForm(update);
    }
  };

  const createLevel = async (event) => {
    event.preventDefault();
    if (!levelForm.category) return;
    setSaving(true);
    try {
      await academicLevelService.createLevel({
        name: levelForm.name,
        category: levelForm.category,
        position: Number(levelForm.position),
        specialization_required_from_term_position:
          normalizeSpecializationTermPosition(
            categoryOptions,
            levelForm.category,
            levelForm.specialization_required_from_term_position,
          ),
      });
      showSuccess("Academic level created as draft.");
      closeEditor();
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not create academic level."));
    } finally {
      setSaving(false);
    }
  };

  const updateLevel = async (event) => {
    event.preventDefault();
    if (!editingLevelId || !editingLevelForm?.name.trim() || !editingLevelForm?.category) {
      return;
    }
    setSaving(editingLevelId);
    try {
      await academicLevelService.updateLevel(editingLevelId, {
        name: editingLevelForm.name.trim(),
        category: editingLevelForm.category,
        position: Number(editingLevelForm.position),
        specialization_required_from_term_position:
          normalizeSpecializationTermPosition(
            categoryOptions,
            editingLevelForm.category,
            editingLevelForm.specialization_required_from_term_position,
          ),
      });
      showSuccess("Academic level updated.");
      closeEditor();
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
        activate: ["Activate academic level", "Activate"],
        deactivate: ["Deactivate academic level", "Deactivate"],
        archive: ["Archive academic level", "Archive"],
        restore: ["Restore academic level", "Restore"],
        delete: ["Delete empty level", "Delete"],
      }[pendingAction.action]
    : null;
  const showEditor = activeTab === "create" || Boolean(editingLevelId);

  return (
    <>
      <WorkspaceGrid
        editor={
          showEditor ? (
            <WorkspacePanel
              title={editingLevelId ? "Update level" : "Create academic level"}
              description="Levels own curriculum and ordered progression; classes remain optional organization."
            >
              <form className="space-y-3" onSubmit={editingLevelId ? updateLevel : createLevel}>
                <Input
                  label="Level name"
                  value={editingLevelId ? editingLevelForm?.name || "" : levelForm.name}
                  onChange={(event) =>
                    editingLevelId
                      ? setEditingLevelForm((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      : setLevelForm((current) => ({ ...current, name: event.target.value }))
                  }
                  placeholder="JSS1"
                  required
                />
                <SelectControl
                  label="Category"
                  value={editingLevelId ? editingLevelForm?.category || "" : levelForm.category}
                  onChange={updateFormCategory}
                  options={selectOptions}
                  disabled={structuralFieldsLocked}
                  required
                />
                <Input
                  label="Position"
                  type="number"
                  min="1"
                  value={editingLevelId ? editingLevelForm?.position || "" : levelForm.position}
                  onChange={(event) =>
                    editingLevelId
                      ? setEditingLevelForm((current) => ({
                          ...current,
                          position: event.target.value,
                        }))
                      : setLevelForm((current) => ({
                          ...current,
                          position: event.target.value,
                        }))
                  }
                  disabled={structuralFieldsLocked}
                  required
                />
                {selectedCategorySupportsDepartments ? (
                  <div className="space-y-1.5">
                    <SelectControl
                      label="Department specialization"
                      value={
                        editingLevelId
                          ? editingLevelForm?.specialization_required_from_term_position || ""
                          : levelForm.specialization_required_from_term_position
                      }
                      onChange={(value) =>
                        editingLevelId
                          ? setEditingLevelForm((current) => ({
                              ...current,
                              specialization_required_from_term_position: value,
                            }))
                          : setLevelForm((current) => ({
                              ...current,
                              specialization_required_from_term_position: value,
                            }))
                      }
                      options={specializationOptions}
                      disabled={structuralFieldsLocked}
                      searchable={false}
                    />
                    <p className="text-xs leading-5 text-text-muted">
                      Choose when every class in this level must have a department
                      placement. Leave it optional when classes may remain general.
                    </p>
                  </div>
                ) : null}
                {structuralFieldsLocked ? (
                  <p className="text-xs leading-5 text-text-muted">
                    Category, position, and specialization rules are locked after
                    activation. The level name can still be updated.
                  </p>
                ) : null}
                <FormActions
                  submitting={Boolean(saving)}
                  submitLabel={editingLevelId ? "Save level" : "Create level"}
                  editing
                  onCancel={closeEditor}
                />
              </form>
            </WorkspacePanel>
          ) : null
        }
        content={
          activeTab === "create" && !editingLevelId ? null : (
            <RecordList
              title="Academic levels"
              description="Ordered academic stages. Select a level for details, while lifecycle operations remain directly accessible from the list."
              actions={
                !showEditor ? (
                  <Button type="button" onClick={() => selectView("create")}>
                    Create level
                  </Button>
                ) : null
              }
              items={visibleLevels}
              listClassName="max-h-[34rem] overflow-y-auto"
              emptyIcon={Library}
              emptyTitle="No academic levels"
              emptyDescription="Create the first level to begin configuring the academic structure."
              renderTitle={(item) => item.name}
              renderMeta={(item) =>
                `${categoryLabels.get(item.category) || String(item.category).replaceAll("_", " ")} · Position ${item.position}`
              }
              renderDescription={(item) => {
                const supportsDepartments = categorySupportsDepartments(
                  categoryOptions,
                  item.category,
                );
                const specialization = supportsDepartments
                  ? ` · Department specialization ${specializationLabel(
                      item.specialization_required_from_term_position,
                    )}`
                  : "";
                return `${classCounts.get(item.id) || 0} class arms · Progression follows the next configured position${specialization}.`;
              }}
              renderStatus={(item) => item.status}
              showInspector={!showEditor}
              onEdit={(item) => {
                setEditingLevelId(item.id);
                setEditingLevelForm({
                  name: item.name,
                  category: item.category,
                  position: String(item.position),
                  specialization_required_from_term_position:
                    item.specialization_required_from_term_position == null
                      ? ""
                      : String(item.specialization_required_from_term_position),
                });
              }}
              canEdit={(item) => item.status !== "archived"}
              renderActions={(item) => (
                <>
                  {["draft", "inactive"].includes(item.status) ? (
                    <Button
                      size="small"
                      variant="outline"
                      disabled={saving === item.id}
                      onClick={() => setPendingAction({ item, action: "activate" })}
                    >
                      Activate
                    </Button>
                  ) : null}
                  {item.status === "active" ? (
                    <Button
                      size="small"
                      variant="outline"
                      disabled={saving === item.id}
                      onClick={() => setPendingAction({ item, action: "deactivate" })}
                    >
                      Deactivate
                    </Button>
                  ) : null}
                  {item.status === "inactive" ? (
                    <Button
                      size="small"
                      variant="outline"
                      disabled={saving === item.id}
                      onClick={() => setPendingAction({ item, action: "archive" })}
                    >
                      Archive
                    </Button>
                  ) : null}
                  {item.status === "archived" ? (
                    <Button
                      size="small"
                      variant="outline"
                      disabled={saving === item.id}
                      onClick={() => setPendingAction({ item, action: "restore" })}
                    >
                      Restore
                    </Button>
                  ) : null}
                  {item.status === "draft" && !classCounts.get(item.id) ? (
                    <Button
                      size="small"
                      variant="danger"
                      disabled={saving === item.id}
                      onClick={() => setPendingAction({ item, action: "delete" })}
                    >
                      Delete
                    </Button>
                  ) : null}
                </>
              )}
            />
          )
        }
      />
      <ConfirmDialog
        open={Boolean(pendingAction)}
        title={actionConfig?.[0]}
        description={`${pendingAction?.item?.name || "This level"} will move through the supported academic-level lifecycle. The backend will reject the transition if live dependencies make it unsafe.`}
        confirmLabel={actionConfig?.[1]}
        variant={["deactivate", "archive", "delete"].includes(pendingAction?.action) ? "danger" : "primary"}
        isLoading={saving === pendingAction?.item?.id}
        onConfirm={runPendingAction}
        onCancel={() => setPendingAction(null)}
      />
    </>
  );
}

export default AcademicLevelsWorkspace;
