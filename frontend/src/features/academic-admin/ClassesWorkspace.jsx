import { beginAcademicSubmission, endAcademicSubmission, finishAcademicCreation } from "./academicSubmission";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { displayClass } from "../../components/academic/academicDisplay";
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
  RecordList,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import { isAssignableClassTeacher } from "./classTeacherEligibility";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);
const emptyClassForm = {
  academic_level_id: "",
  arm_label_id: "",
  teacher_membership_id: "",
};

const teacherLabel = (item) => {
  const account = item?.teacher_account || item?.account || {};
  return (
    [account.first_name, account.last_name].filter(Boolean).join(" ") ||
    account.email ||
    item.staff_id ||
    "Teacher"
  );
};

function ClassesWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [levels, setLevels] = useState([]);
  const [classes, setClasses] = useState([]);
  const [armLabels, setArmLabels] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [classForm, setClassForm] = useState(emptyClassForm);
  const [editingClassId, setEditingClassId] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
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
      setLoadError(getErrorMessage(error, "Could not load class structure."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const levelOptions = useMemo(
    () => levels.map((item) => ({ value: item.id, label: item.name })),
    [levels],
  );
  const teacherOptions = useMemo(
    () => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })),
    [teachers],
  );
  const armLabelOptions = useMemo(
    () =>
      armLabels
        .filter((item) => item.is_active && !item.archived_at)
        .map((item) => ({ value: item.id, label: item.label })),
    [armLabels],
  );

  const selectView = (view) => {
    const next = new URLSearchParams(searchParams);
    if (view === "create") next.set("returnView", activeTab === "create" ? "overview" : activeTab);
    else next.delete("returnView");
    next.set("view", view);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  const closeEditor = () => {
    setEditingClassId("");
    setClassForm(emptyClassForm);
    selectView(searchParams.get("returnView") || (activeTab === "create" ? "overview" : activeTab));
  };

  const saveClass = async (event) => {
    event.preventDefault();
    const wasEditing = Boolean(editingClassId);
    const submission = beginAcademicSubmission(event, Boolean(saving));
    if (!submission) return;
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
      showSuccess(wasEditing ? "Class arm updated." : "Class arm created.");
      finishAcademicCreation(submission, () => { setClassForm((current) => ({ ...emptyClassForm, academic_level_id: current.academic_level_id })); }, closeEditor, wasEditing);
      await load();
    } catch (error) {
      showError(
        getErrorMessage(
          error,
          wasEditing ? "Could not update class arm." : "Could not create class arm.",
        ),
      );
    } finally {
      endAcademicSubmission(submission);
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
  const showEditor = activeTab === "create" || Boolean(editingClassId);

  return (
    <WorkspaceGrid
      editor={
        showEditor ? (
          <WorkspacePanel
            title={editingClassId ? "Edit class" : "Create class"}
            description="Choose the authoritative level and reusable arm label for this class group."
          >
            <form className="space-y-3" onSubmit={saveClass}>
              <fieldset disabled={Boolean(saving)} className="space-y-3">
                <SelectControl
                  label="Academic level"
                  value={classForm.academic_level_id}
                  onChange={(value) =>
                    setClassForm((current) => ({
                      ...current,
                      academic_level_id: value,
                    }))
                  }
                  options={levelOptions}
                  required
                />
                <SelectControl
                  label="Arm"
                  value={classForm.arm_label_id}
                  onChange={(value) =>
                    setClassForm((current) => ({
                      ...current,
                      arm_label_id: value,
                    }))
                  }
                  options={armLabelOptions}
                  placeholder="Select arm"
                  required
                />
                <SelectControl
                  label="Class teacher"
                  value={classForm.teacher_membership_id}
                  onChange={(value) =>
                    setClassForm((current) => ({
                      ...current,
                      teacher_membership_id: value,
                    }))
                  }
                  options={teacherOptions}
                  clearable
                />
                <FormActions
                  submitting={Boolean(saving)}
                  submitLabel={editingClassId ? "Save class" : "Create class"}
                  repeatable
                  editing={Boolean(editingClassId)}
                  onCancel={closeEditor}
                />
              </fieldset>
            </form>
          </WorkspacePanel>
        ) : null
      }
      content={
          <RecordList
              loading={loading}
              error={loadError}
              onRetry={load}
            title="Classes"
            description="Concrete student groups within academic levels. Select a row to inspect it; lifecycle actions remain available directly from the directory."
            actions={
              !showEditor ? (
                <Button type="button" onClick={() => selectView("create")}>
                  Create class
                </Button>
              ) : null
            }
            items={filteredClasses}
            emptyTitle="No classes"
            emptyDescription="No classes match this lifecycle view."
            renderTitle={displayClass}
            renderMeta={(item) => item.academic_level_name || "Academic level"}
            renderDescription={(item) =>
              item.teacher_membership_id
                ? "Class teacher assigned"
                : "No class teacher assigned"
            }
            renderStatus={(item) =>
              item.archived_at ? "archived" : item.is_active ? "active" : "inactive"
            }
            showInspector={!showEditor}
            onEdit={(item) => {
              setEditingClassId(item.id);
              setClassForm({
                academic_level_id: item.academic_level_id,
                arm_label_id: item.arm_label_id || "",
                teacher_membership_id: item.teacher_membership_id || "",
              });
            }}
            canEdit={(item) => !item.archived_at}
            renderActions={(item) => (
              <>
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
              </>
            )}
          />
      }
    />
  );
}

export default ClassesWorkspace;
