import { Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import MultiSelect from "../../components/ui/MultiSelect";
import { displayClass } from "../../components/academic/academicDisplay";
import { useToast } from "../../hooks/useToast";
import { academicLevelService, armLabelService, classService, departmentService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { subjectService } from "../../services/subject.service";
import { teacherService } from "../../services/teacherService";
import {
  FormActions,
  Input,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";
import { isAssignableClassTeacher } from "./classTeacherEligibility";

const asItems = (value) => Array.isArray(value) ? value : value?.items || [];
const teacherLabel = (item) => {
  const account = item?.teacher_account || item?.account || {};
  return [account.first_name, account.last_name].filter(Boolean).join(" ") || account.email || item.staff_id || "Teacher";
};

function ClassStructureWorkspace({ activeTab = "overview", domain }) {
  const { showError, showSuccess, showWarning } = useToast();
  const [levels, setLevels] = useState([]);
  const [classes, setClasses] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [armLabels, setArmLabels] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [selectedLevelId, setSelectedLevelId] = useState("");
  const [levelSubjects, setLevelSubjects] = useState([]);
  const [terms, setTerms] = useState([]);
  const [offerings, setOfferings] = useState([]);
  const [selectedOfferingSubjectId, setSelectedOfferingSubjectId] = useState("");
  const [offeringForm, setOfferingForm] = useState({
    academic_term_id: "",
    department_id: "",
    is_elective: false,
  });
  const [levelForm, setLevelForm] = useState({
    name: "",
    category: "",
    position: "",
    specialization_required_from_term_position: "",
  });
  const [classForm, setClassForm] = useState({ academic_level_id: "", department_id: "", arm_label_id: "", teacher_membership_id: "" });
  const [departmentName, setDepartmentName] = useState("");
  const [armLabelForm, setArmLabelForm] = useState({ label: "", position: "" });
  const [subjectForm, setSubjectForm] = useState({ subject_ids: [] });
  const [editingClassId, setEditingClassId] = useState("");
  const [editingLevelId, setEditingLevelId] = useState("");
  const [editingLevelForm, setEditingLevelForm] = useState(null);
  const [levelPendingDeletion, setLevelPendingDeletion] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [levelRows, classRows, departmentRows, armLabelRows, subjectRows, teacherRows, termRows] = await Promise.all([
        academicLevelService.getLevels({ includeArchived: true }),
        classService.getClasses({ includeArchived: true }),
        departmentService.getDepartments(),
        armLabelService.getArmLabels({ includeArchived: true }),
        subjectService.getSubjects({ limit: 100 }),
        teacherService.getTeachers({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
      ]);
      setLevels(asItems(levelRows));
      setClasses(asItems(classRows));
      setDepartments(asItems(departmentRows));
      setArmLabels(asItems(armLabelRows));
      setSubjects(asItems(subjectRows));
      setTeachers(asItems(teacherRows).filter(isAssignableClassTeacher));
      setTerms(asItems(termRows));
      if (domain === "level-subjects") {
        setSelectedLevelId((current) => current || asItems(levelRows)[0]?.id || "");
      }
    } catch (error) {
      showError(getErrorMessage(error, "Could not load academic structure."));
    }
  }, [domain, showError]);

  const loadLevelSubjects = useCallback(async () => {
    if (!selectedLevelId) return setLevelSubjects([]);
    try {
      setLevelSubjects(asItems(await academicService.listLevelSubjects(selectedLevelId, { include_archived: true })));
    } catch (error) {
      setLevelSubjects([]);
      showError(getErrorMessage(error, "Could not load subjects for this level."));
    }
  }, [selectedLevelId, showError]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadLevelSubjects(); }, [loadLevelSubjects]);

  useEffect(() => {
    if (activeTab !== "offerings" || !selectedOfferingSubjectId) {
      setOfferings([]);
      return;
    }
    let active = true;
    academicService
      .listSubjectOfferings(selectedOfferingSubjectId)
      .then((response) => {
        if (active) setOfferings(asItems(response));
      })
      .catch((error) => {
        if (active) showError(getErrorMessage(error, "Could not load subject offerings."));
      });
    return () => {
      active = false;
    };
  }, [activeTab, selectedOfferingSubjectId, showError]);

  const levelOptions = useMemo(() => levels.map((item) => ({ value: item.id, label: item.name })), [levels]);
  const teacherOptions = useMemo(() => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })), [teachers]);
  const departmentOptions = useMemo(() => departments.map((item) => ({ value: item.id, label: item.name })), [departments]);
  const armLabelOptions = useMemo(
    () => armLabels
      .filter((item) => item.is_active && !item.archived_at)
      .map((item) => ({ value: item.id, label: item.label })),
    [armLabels],
  );
  const attached = useMemo(() => new Set(levelSubjects.map((item) => item.subject_id)), [levelSubjects]);
  const subjectOptions = useMemo(() => subjects.filter((item) => !attached.has(item.id)).map((item) => ({ value: item.id, label: item.name })), [subjects, attached]);
  const levelSubjectOptions = useMemo(
    () => levelSubjects
      .filter((item) => item.is_active && !item.archived_at)
      .map((item) => ({ value: item.id, label: item.subject_name })),
    [levelSubjects],
  );
  const termOptions = useMemo(
    () => terms.map((item) => ({
      value: item.id,
      label: `${String(item.name || "").replaceAll("_", " ")} · ${item.academic_session_name || "Academic term"}`,
    })),
    [terms],
  );

  const createLevel = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await academicLevelService.createLevel({
        ...levelForm,
        position: Number(levelForm.position),
        specialization_required_from_term_position:
          levelForm.specialization_required_from_term_position === ""
            ? null
            : Number(levelForm.specialization_required_from_term_position),
      });
      setLevelForm({ name: "", category: "", position: "", specialization_required_from_term_position: "" });
      showSuccess("Academic level created.");
      await load();
    } catch (error) { showError(getErrorMessage(error, "Could not create academic level.")); }
    finally { setSaving(false); }
  };

  const updateLevel = async (event) => {
    event.preventDefault();
    if (!editingLevelId || !editingLevelForm?.name.trim()) return;
    setSaving(editingLevelId);
    try {
      await academicLevelService.updateLevel(editingLevelId, {
        ...editingLevelForm,
        name: editingLevelForm.name.trim(),
        position: Number(editingLevelForm.position),
        specialization_required_from_term_position:
          editingLevelForm.specialization_required_from_term_position === ""
            ? null
            : Number(editingLevelForm.specialization_required_from_term_position),
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
      if (selectedLevelId === level.id) setSelectedLevelId("");
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

  const createClass = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...classForm,
        teacher_membership_id: classForm.teacher_membership_id || null,
      };
      if (editingClassId) {
        await classService.updateClass(editingClassId, payload);
      } else {
        await classService.createClass(payload);
      }
      setClassForm({ academic_level_id: "", department_id: "", arm_label_id: "", teacher_membership_id: "" });
      setEditingClassId("");
      showSuccess(editingClassId ? "Class arm updated." : "Class arm created.");
      await load();
    } catch (error) { showError(getErrorMessage(error, "Could not create class arm.")); }
    finally { setSaving(false); }
  };

  const createDepartment = async () => {
    if (!departmentName.trim()) return;
    setSaving("department");
    try {
      await departmentService.createDepartment({ name: departmentName.trim() });
      setDepartmentName("");
      showSuccess("Department created.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not create department."));
    } finally {
      setSaving(false);
    }
  };

  const createArmLabel = async (event) => {
    event.preventDefault();
    if (!armLabelForm.label.trim()) return;
    setSaving("arm-label");
    try {
      await armLabelService.createArmLabel({
        label: armLabelForm.label.trim(),
        position: armLabelForm.position ? Number(armLabelForm.position) : null,
      });
      setArmLabelForm({ label: "", position: "" });
      showSuccess("Arm label created.");
      await load();
    } catch (error) {
      showError(getErrorMessage(error, "Could not create arm label."));
    } finally {
      setSaving(false);
    }
  };

  const updateClassLifecycle = async (item, action) => {
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

  const updateLevelSubjectLifecycle = async (item, action) => {
    setSaving(item.id);
    try {
      if (action === "activate") await academicService.activateLevelSubject(item.id);
      if (action === "deactivate") await academicService.deactivateLevelSubject(item.id);
      if (action === "archive") await academicService.archiveLevelSubject(item.id);
      if (action === "restore") await academicService.restoreLevelSubject(item.id);
      showSuccess(`Level subject ${action}d.`);
      await loadLevelSubjects();
    } catch (error) {
      showError(getErrorMessage(error, `Could not ${action} this level subject.`));
    } finally {
      setSaving(false);
    }
  };

  const createSubjectOffering = async (event) => {
    event.preventDefault();
    if (!selectedOfferingSubjectId || !offeringForm.academic_term_id) return;
    setSaving(true);
    try {
      await academicService.createSubjectOffering(selectedOfferingSubjectId, {
        academic_term_id: offeringForm.academic_term_id,
        department_id: offeringForm.department_id || null,
        is_elective: offeringForm.is_elective,
      });
      setOfferings(asItems(await academicService.listSubjectOfferings(selectedOfferingSubjectId)));
      setOfferingForm((current) => ({ ...current, department_id: "", is_elective: false }));
      showSuccess("Subject offering created.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not create subject offering."));
    } finally {
      setSaving(false);
    }
  };

  const addSubjects = async (event) => {
    event.preventDefault();
    if (!selectedLevelId || subjectForm.subject_ids.length === 0) return showWarning("Select a level and at least one subject.");
    setSaving(true);
    try {
      await academicService.addLevelSubjectsBulk(selectedLevelId, {
        ...subjectForm,
      });
      setSubjectForm((current) => ({ ...current, subject_ids: [] }));
      showSuccess("Subjects added to the academic level.");
      await loadLevelSubjects();
    } catch (error) { showError(getErrorMessage(error, "Could not add subjects to this level.")); }
    finally { setSaving(false); }
  };

  if (domain === "levels") {
    const levelWorkspaceTitle = activeTab === "manage"
      ? "Manage academic levels"
      : "Academic levels";
    const levelWorkspaceDescription = activeTab === "manage"
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
                  options={[
                    { value: "KINDERGARTEN", label: "Kindergarten" },
                    { value: "PRIMARY", label: "Primary" },
                    { value: "JUNIOR_SECONDARY", label: "Junior Secondary" },
                    { value: "SENIOR_SECONDARY", label: "Senior Secondary" },
                  ]}
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
                <Input
                  label="Specialization required from term position (optional)"
                  type="number"
                  min="1"
                  value={levelForm.specialization_required_from_term_position}
                  onChange={(event) => setLevelForm((current) => ({ ...current, specialization_required_from_term_position: event.target.value }))}
                />
                <FormActions submitting={saving} submitLabel="Create level" />
              </form>
            </WorkspacePanel>
          ) : null}
          content={(
            <WorkspacePanel
              title={levelWorkspaceTitle}
              description={levelWorkspaceDescription}
            >
            <div className="grid max-h-[34rem] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
              {levels.map((item) => {
                const armCount = classes.filter(
                  (classroom) => classroom.academic_level_id === item.id,
                ).length;
                return (
                <div
                  key={item.id}
                  className="rounded-2xl border border-border/70 bg-surface p-4"
                >
                  <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="font-semibold text-text">{item.name}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={armCount > 0 ? "default" : "warning"}>
                        {armCount} arm{armCount === 1 ? "" : "s"}
                      </Badge>
                      <Badge variant="default">
                        {String(item.category || "").replaceAll("_", " ")} · {item.position}
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
                        options={[
                          { value: "KINDERGARTEN", label: "Kindergarten" },
                          { value: "PRIMARY", label: "Primary" },
                          { value: "JUNIOR_SECONDARY", label: "Junior Secondary" },
                          { value: "SENIOR_SECONDARY", label: "Senior Secondary" },
                        ]}
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
                            specialization_required_from_term_position:
                              item.specialization_required_from_term_position == null
                                ? ""
                                : String(item.specialization_required_from_term_position),
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

  if (domain === "arm-labels") {
    return (
      <WorkspaceGrid
        editor={activeTab === "create" ? (
          <WorkspacePanel
            title="Add arm label"
            description="Create one reusable label that can be used across many levels."
          >
            <form className="space-y-3" onSubmit={createArmLabel}>
              <Input
                label="Arm label"
                value={armLabelForm.label}
                onChange={(event) => setArmLabelForm((current) => ({ ...current, label: event.target.value }))}
                placeholder="A"
                required
              />
              <Input
                label="Display position"
                type="number"
                min="1"
                value={armLabelForm.position}
                onChange={(event) => setArmLabelForm((current) => ({ ...current, position: event.target.value }))}
              />
              <FormActions submitting={saving === "arm-label"} submitLabel="Add arm label" />
            </form>
          </WorkspacePanel>
        ) : null}
        content={(
          <WorkspacePanel
            title="Arm labels"
            description="Reusable labels available when creating or editing classes."
          >
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {armLabels.map((item) => (
                <div key={item.id} className="rounded-2xl border border-border/70 bg-surface p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-lg font-semibold text-text">{item.label}</p>
                    <Badge variant={item.is_active && !item.archived_at ? "success" : "warning"}>
                      {item.archived_at ? "Archived" : item.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    {item.position ? `Position ${item.position}` : "No display position"}
                  </p>
                </div>
              ))}
              {!armLabels.length ? (
                <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-text-muted">
                  No arm labels yet.
                </div>
              ) : null}
            </div>
          </WorkspacePanel>
        )}
      />
    );
  }

  if (domain === "classes") {
    const filteredClasses = classes.filter((item) => {
      if (activeTab === "active") return item.is_active && !item.archived_at;
      if (activeTab === "inactive") return !item.is_active && !item.archived_at;
      if (activeTab === "archived") return Boolean(item.archived_at);
      return true;
    });
    const showEditor = ["overview", "create"].includes(activeTab) || editingClassId;

    return (
      <WorkspaceGrid
        editor={showEditor ? (
          <WorkspacePanel
            title={editingClassId ? "Edit class arm" : "Create class arm"}
            description="Choose the authoritative level. Arm is optional organizational placement."
          >
            <form className="space-y-3" onSubmit={createClass}>
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
                placeholder="No arm"
              />
              <SelectControl
                label="Department (optional)"
                value={classForm.department_id}
                onChange={(value) => setClassForm((current) => ({ ...current, department_id: value }))}
                options={departmentOptions}
                clearable
              />
              <div className="rounded-xl border border-border/70 p-3">
                <Input
                  label="New department"
                  value={departmentName}
                  onChange={(event) => setDepartmentName(event.target.value)}
                  placeholder="Science"
                />
                <Button className="mt-2" type="button" size="small" variant="outline" disabled={!departmentName.trim() || saving === "department"} onClick={createDepartment}>
                  {saving === "department" ? "Creating..." : "Create department"}
                </Button>
              </div>
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
                submitting={saving}
                submitLabel={editingClassId ? "Save class" : "Create class"}
                editing={Boolean(editingClassId)}
                onCancel={() => {
                  setEditingClassId("");
                  setClassForm({
                    academic_level_id: "",
                    department_id: "",
                    arm_label_id: "",
                    teacher_membership_id: "",
                  });
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
                          {item.teacher_membership_id
                            ? "Class teacher assigned"
                            : "No class teacher"}
                        </p>
                      </div>
                      <Badge
                        variant={item.archived_at
                          ? "warning"
                          : item.is_active
                            ? "success"
                            : "error"}
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
                              department_id: item.department_id || "",
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
                          onClick={() => updateClassLifecycle(item, "deactivate")}
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
                            onClick={() => updateClassLifecycle(item, "activate")}
                          >
                            Activate
                          </Button>
                          <Button
                            size="small"
                            variant="outline"
                            disabled={saving === item.id}
                            onClick={() => updateClassLifecycle(item, "archive")}
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
                          onClick={() => updateClassLifecycle(item, "restore")}
                        >
                          Restore
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-text-muted">
                No classes match this lifecycle view.
              </p>
            )}
          </WorkspacePanel>
        )}
      />
    );
  }

  if (activeTab === "assign") {
    return (
      <WorkspaceGrid
        editor={(
        <WorkspacePanel
          title="Assign subjects by level"
          description="Configure curriculum once; every arm in the level inherits these subjects."
        >
          <form className="space-y-3" onSubmit={addSubjects}>
            <SelectControl
              label="Academic level"
              value={selectedLevelId}
              onChange={setSelectedLevelId}
              options={levelOptions}
              required
            />
            <MultiSelect
              label="Subjects"
              name="subject_ids"
              value={subjectForm.subject_ids}
              onChange={(event) => setSubjectForm((current) => ({
                ...current,
                subject_ids: event.target.value,
              }))}
              options={subjectOptions}
            />
            <FormActions submitting={saving} submitLabel="Add subjects" />
          </form>
        </WorkspacePanel>
        )}
        content={null}
      />
    );
  }

  if (activeTab === "offerings") {
    return (
      <WorkspaceGrid
        editor={(
          <WorkspacePanel
            title="Create term offering"
            description="Apply a level subject to a term for every student or only one department. Electives appear after meaningful score participation."
          >
            <form className="space-y-3" onSubmit={createSubjectOffering}>
              <SelectControl
                label="Academic level"
                value={selectedLevelId}
                onChange={(value) => {
                  setSelectedLevelId(value);
                  setSelectedOfferingSubjectId("");
                }}
                options={levelOptions}
                required
              />
              <SelectControl
                label="Level subject"
                value={selectedOfferingSubjectId}
                onChange={setSelectedOfferingSubjectId}
                options={levelSubjectOptions}
                required
              />
              <SelectControl
                label="Academic term"
                value={offeringForm.academic_term_id}
                onChange={(value) => setOfferingForm((current) => ({ ...current, academic_term_id: value }))}
                options={termOptions}
                required
              />
              <SelectControl
                label="Department (optional)"
                value={offeringForm.department_id}
                onChange={(value) => setOfferingForm((current) => ({ ...current, department_id: value }))}
                options={departmentOptions}
                placeholder="All departments"
              />
              <label className="flex items-start gap-3 rounded-xl border border-border/70 p-3 text-sm text-text">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4"
                  checked={offeringForm.is_elective}
                  onChange={(event) => setOfferingForm((current) => ({ ...current, is_elective: event.target.checked }))}
                />
                <span>
                  <span className="font-semibold">Elective subject</span>
                  <span className="mt-1 block text-text-muted">Participation begins with the first meaningful recorded score.</span>
                </span>
              </label>
              <FormActions submitting={saving} submitLabel="Create offering" />
            </form>
          </WorkspacePanel>
        )}
        content={(
          <WorkspacePanel
            title="Configured offerings"
            description="Term and department applicability are backend-enforced during results and report generation."
          >
            {offerings.length ? (
              <div className="space-y-3">
                {offerings.map((item) => {
                  const term = terms.find((row) => row.id === item.academic_term_id);
                  const department = departments.find((row) => row.id === item.department_id);
                  return (
                    <div key={item.id} className="rounded-2xl border border-border/70 bg-surface p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-text">{String(term?.name || "Academic term").replaceAll("_", " ")}</p>
                          <p className="mt-1 text-sm text-text-muted">{department?.name || "All departments"}</p>
                        </div>
                        <Badge variant={item.is_elective ? "warning" : "success"}>
                          {item.is_elective ? "elective" : "expected"}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-text-muted">Select a level subject to review its term offerings.</p>
            )}
          </WorkspacePanel>
        )}
      />
    );
  }

  const filteredLevelSubjects = levelSubjects.filter((item) => {
    if (activeTab === "active") return item.is_active && !item.archived_at;
    if (activeTab === "inactive") return !item.is_active && !item.archived_at;
    if (activeTab === "archived") return Boolean(item.archived_at);
    return true;
  });
  const levelSubjectTitle = activeTab === "overview"
    ? "Subjects by academic level"
    : `${activeTab[0].toUpperCase()}${activeTab.slice(1)} level subjects`;
  const levelSubjectDescription = activeTab === "overview"
    ? "Select a level to review its inherited curriculum."
    : "Only mappings in this lifecycle state are shown.";

  return (
    <WorkspacePanel
      title={levelSubjectTitle}
      description={levelSubjectDescription}
      actions={(
        <SelectControl
          label="Academic level"
          value={selectedLevelId}
          onChange={setSelectedLevelId}
          options={levelOptions}
          required
        />
      )}
    >
      {filteredLevelSubjects.length ? (
        <div className="grid max-h-[34rem] gap-3 overflow-y-auto overscroll-contain pr-1 sm:grid-cols-2">
          {filteredLevelSubjects.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-border/70 bg-surface p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-text">{item.subject_name}</p>
                      <p className="text-sm text-text-muted">
                        {item.subject_code || "No code"}
                      </p>
                    </div>
                    <Badge
                      variant={item.archived_at
                        ? "warning"
                        : item.is_active
                          ? "success"
                          : "error"}
                    >
                      {item.archived_at
                        ? "archived"
                        : item.is_active
                          ? "active"
                          : "inactive"}
                    </Badge>
                  </div>
                  {activeTab !== "overview" ? (
                  <div className="mt-4 grid gap-2 sm:flex sm:flex-wrap">
                    {!item.archived_at && item.is_active ? (
                      <Button
                        size="small"
                        variant="outline"
                        className="w-full sm:w-auto"
                        disabled={saving === item.id}
                        onClick={() => updateLevelSubjectLifecycle(item, "deactivate")}
                      >
                        Deactivate
                      </Button>
                    ) : null}
                    {!item.archived_at && !item.is_active ? (
                      <>
                        <Button
                          size="small"
                          variant="outline"
                          className="w-full sm:w-auto"
                          disabled={saving === item.id}
                          onClick={() => updateLevelSubjectLifecycle(item, "activate")}
                        >
                          Activate
                        </Button>
                        <Button
                          size="small"
                          variant="outline"
                          className="w-full sm:w-auto"
                          disabled={saving === item.id}
                          onClick={() => updateLevelSubjectLifecycle(item, "archive")}
                        >
                          Archive
                        </Button>
                      </>
                    ) : null}
                    {item.archived_at ? (
                      <Button
                        size="small"
                        variant="outline"
                        className="w-full sm:w-auto"
                        disabled={saving === item.id}
                        onClick={() => updateLevelSubjectLifecycle(item, "restore")}
                      >
                        Restore
                      </Button>
                    ) : null}
                  </div>
                  ) : null}
                </div>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <Library className="mx-auto h-7 w-7 text-text-muted" />
          <p className="mt-2 text-sm text-text-muted">
            No {activeTab === "overview" ? "subjects are configured" : activeTab} mappings for this level.
          </p>
        </div>
      )}
    </WorkspacePanel>
  );
}

export default ClassStructureWorkspace;
