import { Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import MultiSelect from "../../components/ui/MultiSelect";
import Modal from "../../components/ui/Modal";
import { displayClass } from "../../components/academic/academicDisplay";
import { useToast } from "../../hooks/useToast";
import { academicLevelService, classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { subjectService } from "../../services/subject.service";
import { teacherService } from "../../services/teacherService";
import {
  CheckboxControl,
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
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [selectedLevelId, setSelectedLevelId] = useState("");
  const [levelSubjects, setLevelSubjects] = useState([]);
  const [levelName, setLevelName] = useState("");
  const [classForm, setClassForm] = useState({ academic_level_id: "", arm: "", teacher_membership_id: "" });
  const [subjectForm, setSubjectForm] = useState({ subject_ids: [], is_core: true });
  const [progression, setProgression] = useState({
    progression_mode: "direct",
    next_level_id: "",
    selection_target_type: "level",
    target_level_ids: [],
    target_classroom_ids: [],
  });
  const [editingClassId, setEditingClassId] = useState("");
  const [editingLevelId, setEditingLevelId] = useState("");
  const [editingLevelName, setEditingLevelName] = useState("");
  const [levelPendingDeletion, setLevelPendingDeletion] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [levelRows, classRows, subjectRows, teacherRows] = await Promise.all([
        academicLevelService.getLevels({ includeArchived: true }),
        classService.getClasses({ includeArchived: true }),
        subjectService.getSubjects({ limit: 100 }),
        teacherService.getTeachers({ limit: 100 }),
      ]);
      setLevels(asItems(levelRows));
      setClasses(asItems(classRows));
      setSubjects(asItems(subjectRows));
      setTeachers(asItems(teacherRows).filter(isAssignableClassTeacher));
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

  const levelOptions = useMemo(() => levels.map((item) => ({ value: item.id, label: item.name })), [levels]);
  const teacherOptions = useMemo(() => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })), [teachers]);
  const attached = useMemo(() => new Set(levelSubjects.map((item) => item.subject_id)), [levelSubjects]);
  const subjectOptions = useMemo(() => subjects.filter((item) => !attached.has(item.id)).map((item) => ({ value: item.id, label: item.name })), [subjects, attached]);

  const createLevel = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await academicLevelService.createLevel({ name: levelName });
      setLevelName("");
      showSuccess("Academic level created.");
      await load();
    } catch (error) { showError(getErrorMessage(error, "Could not create academic level.")); }
    finally { setSaving(false); }
  };

  const updateLevel = async (event) => {
    event.preventDefault();
    if (!editingLevelId || !editingLevelName.trim()) return;
    setSaving(editingLevelId);
    try {
      await academicLevelService.updateLevel(editingLevelId, {
        name: editingLevelName.trim(),
      });
      setEditingLevelId("");
      setEditingLevelName("");
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
        setEditingLevelName("");
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
      setClassForm({ academic_level_id: "", arm: "", teacher_membership_id: "" });
      setEditingClassId("");
      showSuccess(editingClassId ? "Class arm updated." : "Class arm created.");
      await load();
    } catch (error) { showError(getErrorMessage(error, "Could not create class arm.")); }
    finally { setSaving(false); }
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

  const saveProgression = async (event) => {
    event.preventDefault();
    if (!selectedLevelId) return;
    setSaving(true);
    try {
      await academicLevelService.configureProgression(selectedLevelId, progression);
      showSuccess("Level progression updated.");
      setSelectedLevelId("");
      setProgression({
        progression_mode: "direct",
        next_level_id: "",
        selection_target_type: "level",
        target_level_ids: [],
        target_classroom_ids: [],
      });
      await load();
    } catch (error) { showError(getErrorMessage(error, "Could not update level progression.")); }
    finally { setSaving(false); }
  };

  const editProgression = async (item) => {
    setSelectedLevelId(item.id);
    try {
      const configuration = await academicLevelService.getProgression(item.id);
      setProgression({
        progression_mode: configuration.progression_mode,
        next_level_id: configuration.next_level_id || "",
        selection_target_type: configuration.selection_target_type || "level",
        target_level_ids: configuration.target_level_ids || [],
        target_classroom_ids: configuration.target_classroom_ids || [],
      });
    } catch (error) {
      showError(getErrorMessage(error, "Could not load level progression."));
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
      : activeTab === "progression"
        ? "Choose a level"
        : "Academic levels";
    const levelWorkspaceDescription = activeTab === "manage"
      ? "Update level names or remove genuinely empty levels."
      : activeTab === "progression"
        ? "Select one level, then configure its progression separately."
        : "Review the level structure and arm distribution at a glance.";

    return (
      <>
        <WorkspaceGrid
          editor={activeTab === "create" ? (
            <WorkspacePanel
              title="Create academic level"
              description="Levels own curriculum and progression; class arms are created separately."
            >
              <form className="space-y-3" onSubmit={createLevel}>
                <Input
                  label="Level name"
                  value={levelName}
                  onChange={(event) => setLevelName(event.target.value)}
                  placeholder="JSS1"
                  required
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
                      <Badge variant={item.progression_mode === "terminal" ? "success" : "default"}>
                        {String(item.progression_mode || "direct").replace("_", " ")}
                      </Badge>
                    </div>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    {item.next_level_id
                      ? `Progresses to ${levels.find((level) => level.id === item.next_level_id)?.name || "next level"}`
                      : item.progression_mode === "terminal"
                        ? "Final academic level"
                        : item.progression_mode === "student_selection"
                          ? `Students choose an academic ${item.selection_target_type || "destination"}`
                          : "Direct progression requires a next level"}
                  </p>
                  {activeTab === "manage" && editingLevelId === item.id ? (
                    <form className="mt-3 space-y-3 border-t border-border/70 pt-3" onSubmit={updateLevel}>
                      <Input
                        label="Level name"
                        value={editingLevelName}
                        onChange={(event) => setEditingLevelName(event.target.value)}
                        required
                      />
                      <FormActions
                        submitting={saving === item.id}
                        submitLabel="Save level"
                        editing
                        onCancel={() => {
                          setEditingLevelId("");
                          setEditingLevelName("");
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
                          setEditingLevelName(item.name);
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
                  ) : activeTab === "progression" ? (
                    <Button
                      className="mt-3 w-full sm:w-auto"
                      size="small"
                      variant="outline"
                      onClick={() => editProgression(item)}
                    >
                      Configure progression
                    </Button>
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
            <Modal
              open={activeTab === "progression" && Boolean(selectedLevelId)}
              title="Configure level progression"
              description={levels.find((level) => level.id === selectedLevelId)?.name || "Selected academic level"}
              onClose={() => setSelectedLevelId("")}
              className="sm:max-w-xl"
              placement="center"
            >
              <form
                className="space-y-3"
                onSubmit={saveProgression}
              >
                <SelectControl
                  label="Progression mode"
                  value={progression.progression_mode}
                  onChange={(value) => setProgression((current) => ({
                    ...current,
                    progression_mode: value,
                    next_level_id: value === "direct" ? current.next_level_id : "",
                    target_level_ids: value === "student_selection" ? current.target_level_ids : [],
                    target_classroom_ids: value === "student_selection" ? current.target_classroom_ids : [],
                  }))}
                  options={[
                    { value: "direct", label: "Direct" },
                    { value: "student_selection", label: "Student Selection" },
                    { value: "terminal", label: "Terminal" },
                  ]}
                  required
                />
                {progression.progression_mode === "direct" ? (
                  <SelectControl
                    label="Next academic level"
                    value={progression.next_level_id}
                    onChange={(value) => setProgression((current) => ({
                      ...current,
                      next_level_id: value,
                    }))}
                    options={levelOptions.filter((option) => option.value !== selectedLevelId)}
                    required
                  />
                ) : null}
                {progression.progression_mode === "student_selection" ? (
                  <>
                    <SelectControl
                      label="Students choose"
                      value={progression.selection_target_type}
                      onChange={(value) => setProgression((current) => ({
                        ...current,
                        selection_target_type: value,
                        target_level_ids: [],
                        target_classroom_ids: [],
                      }))}
                      options={[
                        { value: "level", label: "Academic Level" },
                        { value: "classroom", label: "ClassRoom" },
                      ]}
                      required
                    />
                    <MultiSelect
                      label="Allowed destinations"
                      name="progression_destinations"
                      value={
                        progression.selection_target_type === "level"
                          ? progression.target_level_ids
                          : progression.target_classroom_ids
                      }
                      onChange={(event) => {
                        const key = progression.selection_target_type === "level"
                          ? "target_level_ids"
                          : "target_classroom_ids";
                        setProgression((current) => ({
                          ...current,
                          [key]: event.target.value,
                        }));
                      }}
                      options={
                        progression.selection_target_type === "level"
                          ? levelOptions.filter((option) => option.value !== selectedLevelId)
                          : classes
                              .filter((item) => item.is_active && !item.archived_at && item.academic_level_id !== selectedLevelId)
                              .map((item) => ({ value: item.id, label: displayClass(item) }))
                      }
                    />
                  </>
                ) : null}
                {progression.progression_mode === "terminal" ? (
                  <p className="text-sm text-text-muted">
                    Terminal is only for genuine final-school completion and has no destination.
                  </p>
                ) : null}
                <FormActions
                  submitting={saving}
                  submitLabel="Save progression"
                  editing
                  onCancel={() => setSelectedLevelId("")}
                />
              </form>
            </Modal>
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
            description="Choose the authoritative level, then enter only the concrete arm."
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
              <Input
                label="Arm"
                value={classForm.arm}
                onChange={(event) => setClassForm((current) => ({
                  ...current,
                  arm: event.target.value,
                }))}
                placeholder="A"
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
                submitting={saving}
                submitLabel={editingClassId ? "Save class" : "Create class"}
                editing={Boolean(editingClassId)}
                onCancel={() => {
                  setEditingClassId("");
                  setClassForm({
                    academic_level_id: "",
                    arm: "",
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
                              arm: item.arm,
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
            <CheckboxControl
              label="Core subjects"
              checked={subjectForm.is_core}
              onChange={(value) => setSubjectForm((current) => ({
                ...current,
                is_core: value,
              }))}
            />
            <FormActions submitting={saving} submitLabel="Add subjects" />
          </form>
        </WorkspacePanel>
      )}
      content={(
        <WorkspacePanel
          title="Subjects for selected level"
          description="Teacher assignment later chooses a concrete class arm."
        >
          {levelSubjects.length ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {levelSubjects.map((item) => (
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
                          ? item.is_core ? "core" : "elective"
                          : "inactive"}
                    </Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {!item.archived_at && item.is_active ? (
                      <Button
                        size="small"
                        variant="outline"
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
                          disabled={saving === item.id}
                          onClick={() => updateLevelSubjectLifecycle(item, "activate")}
                        >
                          Activate
                        </Button>
                        <Button
                          size="small"
                          variant="outline"
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
                        disabled={saving === item.id}
                        onClick={() => updateLevelSubjectLifecycle(item, "restore")}
                      >
                        Restore
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-border p-6 text-center">
              <Library className="mx-auto h-7 w-7 text-text-muted" />
              <p className="mt-2 text-sm text-text-muted">
                No subjects configured for this level.
              </p>
            </div>
          )}
        </WorkspacePanel>
      )}
    />
  );
}

export default ClassStructureWorkspace;
