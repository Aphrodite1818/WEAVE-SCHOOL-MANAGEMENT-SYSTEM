import { useCallback, useEffect, useMemo, useState } from "react";

import { displayClass } from "../../components/academic/academicDisplay";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import {
  academicLevelService,
  armLabelService,
  classService,
} from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { teacherService } from "../../services/teacherService";
import {
  FormActions,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import { isAssignableClassTeacher } from "./classTeacherEligibility";

const asItems = (value) => Array.isArray(value) ? value : value?.items || [];
const emptyClassForm = {
  academic_level_id: "",
  arm_label_id: "",
  teacher_membership_id: "",
};

const teacherLabel = (item) => {
  const account = item?.teacher_account || item?.account || {};
  return [account.first_name, account.last_name].filter(Boolean).join(" ")
    || account.email
    || item.staff_id
    || "Teacher";
};

function ClassesWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [levels, setLevels] = useState([]);
  const [classes, setClasses] = useState([]);
  const [armLabels, setArmLabels] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [classForm, setClassForm] = useState(emptyClassForm);
  const [editingClassId, setEditingClassId] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [levelRows, classRows, armLabelRows, teacherRows] = await Promise.all([
        academicLevelService.getLevels({ activeOnly: true }),
        classService.getClasses({ includeArchived: true }),
        armLabelService.getArmLabels({ includeArchived: true }),
        teacherService.getTeachers({ limit: 100 }),
      ]);
      setLevels(asItems(levelRows));
      setClasses(asItems(classRows));
      setArmLabels(asItems(armLabelRows));
      setTeachers(asItems(teacherRows).filter(isAssignableClassTeacher));
    } catch (error) {
      showError(getErrorMessage(error, "Could not load class structure."));
    }
  }, [showError]);

  useEffect(() => { load(); }, [load]);

  const levelOptions = useMemo(
    () => levels.map((item) => ({ value: item.id, label: item.name })),
    [levels],
  );
  const teacherOptions = useMemo(
    () => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })),
    [teachers],
  );
  const armLabelOptions = useMemo(
    () => armLabels
      .filter((item) => item.is_active && !item.archived_at)
      .map((item) => ({ value: item.id, label: item.label })),
    [armLabels],
  );

  const saveClass = async (event) => {
    event.preventDefault();
    const wasEditing = Boolean(editingClassId);
    setSaving(true);
    try {
      const payload = {
        ...classForm,
        teacher_membership_id: classForm.teacher_membership_id || null,
      };
      if (wasEditing) {
        await classService.updateClass(editingClassId, payload);
      } else {
        await classService.createClass(payload);
      }
      setClassForm(emptyClassForm);
      setEditingClassId("");
      showSuccess(wasEditing ? "Class arm updated." : "Class arm created.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, wasEditing ? "Could not update class arm." : "Could not create class arm."));
    } finally {
      setSaving(false);
    }
  };

  const updateLifecycle = async (item, action) => {
    setSaving(item.id);
    try {
      if (action === "activate") await classService.activateClass(item.id);
      if (action === "deactivate") await classService.deactivateClass(item.id);
      if (action === "archive") await classService.archiveClass(item.id);
      if (action === "restore") await classService.restoreClass(item.id);
      showSuccess(`Class ${action}d.`);
      await load();
    } catch (error) {
      showError(getErrorMessage(error, `Could not ${action} this class.`));
    } finally {
      setSaving(false);
    }
  };

  const filteredClasses = classes.filter((item) => {
    if (activeTab === "active") return item.is_active && !item.archived_at;
    if (activeTab === "inactive") return !item.is_active && !item.archived_at;
    if (activeTab === "archived") return Boolean(item.archived_at);
    return true;
  });
  const showEditor = ["overview", "create"].includes(activeTab) || Boolean(editingClassId);

  return (
    <WorkspaceGrid
      editor={showEditor ? (
        <WorkspacePanel
          title={editingClassId ? "Edit class arm" : "Create class arm"}
          description="Choose the authoritative level and reusable arm label for this class group."
        >
          <form className="space-y-3" onSubmit={saveClass}>
            <SelectControl
              label="Academic level"
              value={classForm.academic_level_id}
              onChange={(value) => setClassForm((current) => ({
                ...current,
                academic_level_id: value,
              }))}
              options={levelOptions}
              required
            />
            <SelectControl
              label="Arm"
              value={classForm.arm_label_id}
              onChange={(value) => setClassForm((current) => ({
                ...current,
                arm_label_id: value,
              }))}
              options={armLabelOptions}
              placeholder="Select arm"
              required
            />
            <SelectControl
              label="Class teacher"
              value={classForm.teacher_membership_id}
              onChange={(value) => setClassForm((current) => ({
                ...current,
                teacher_membership_id: value,
              }))}
              options={teacherOptions}
              clearable
            />
            <FormActions
              submitting={saving === true}
              submitLabel={editingClassId ? "Save class" : "Create class"}
              editing={Boolean(editingClassId)}
              onCancel={() => {
                setEditingClassId("");
                setClassForm(emptyClassForm);
              }}
            />
          </form>
        </WorkspacePanel>
      ) : null}
      content={activeTab === "create" && !editingClassId ? null : (
        <WorkspacePanel
          title="Classes and arms"
          description="Each class is a concrete student grouping within one level."
        >
          {filteredClasses.length ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {filteredClasses.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-border/70 bg-surface p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-text">{displayClass(item)}</p>
                      <p className="mt-1 text-sm text-text-muted">
                        {item.teacher_membership_id ? "Class teacher assigned" : "No class teacher"}
                      </p>
                    </div>
                    <Badge
                      variant={item.archived_at ? "warning" : item.is_active ? "success" : "error"}
                    >
                      {item.archived_at ? "archived" : item.is_active ? "active" : "inactive"}
                    </Badge>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {!item.archived_at ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => {
                          setEditingClassId(item.id);
                          setClassForm({
                            academic_level_id: item.academic_level_id,
                            arm_label_id: item.arm_label_id || "",
                            teacher_membership_id: item.teacher_membership_id || "",
                          });
                        }}
                      >
                        Edit
                      </Button>
                    ) : null}
                    {!item.archived_at && item.is_active ? (
                      <Button
                        size="small"
                        variant="outline"
                        disabled={saving === item.id}
                        onClick={() => updateLifecycle(item, "deactivate")}
                      >
                        Deactivate
                      </Button>
                    ) : null}
                    {!item.archived_at && !item.is_active ? (
                      <>
                        <Button
                          size="small"
                          variant="outline"
                          disabled={saving === item.id}
                          onClick={() => updateLifecycle(item, "activate")}
                        >
                          Activate
                        </Button>
                        <Button
                          size="small"
                          variant="outline"
                          disabled={saving === item.id}
                          onClick={() => updateLifecycle(item, "archive")}
                        >
                          Archive
                        </Button>
                      </>
                    ) : null}
                    {item.archived_at ? (
                      <Button
                        size="small"
                        variant="outline"
                        disabled={saving === item.id}
                        onClick={() => updateLifecycle(item, "restore")}
                      >
                        Restore
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">No classes match this lifecycle view.</p>
          )}
        </WorkspacePanel>
      )}
    />
  );
}

export default ClassesWorkspace;
