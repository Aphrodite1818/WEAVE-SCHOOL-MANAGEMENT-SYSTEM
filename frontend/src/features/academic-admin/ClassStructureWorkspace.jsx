import { Library } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import MultiSelect from "../../components/ui/MultiSelect";
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
  const [progression, setProgression] = useState({ next_level_id: "", is_terminal: false });
  const [editingClassId, setEditingClassId] = useState("");
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
      setSelectedLevelId((current) => current || asItems(levelRows)[0]?.id || "");
    } catch (error) {
      showError(getErrorMessage(error, "Could not load academic structure."));
    }
  }, [showError]);

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
      await load();
    } catch (error) { showError(getErrorMessage(error, "Could not update level progression.")); }
    finally { setSaving(false); }
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
    return (
      <WorkspaceGrid
        editor={(
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
        )}
        content={(
          <WorkspacePanel
            title="Academic levels"
            description="Configure one progression path per level."
          >
            <div className="grid gap-3">
              {levels.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-border/70 bg-surface p-4"
                >
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-text">{item.name}</p>
                    <Badge variant={item.is_terminal ? "success" : "default"}>
                      {item.is_terminal ? "terminal" : "active"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-text-muted">
                    {item.next_level_id
                      ? `Progresses to ${levels.find((level) => level.id === item.next_level_id)?.name || "next level"}`
                      : item.is_terminal
                        ? "Final academic level"
                        : "Progression not configured"}
                  </p>
                  <Button
                    className="mt-3"
                    size="small"
                    variant="outline"
                    onClick={() => {
                      setSelectedLevelId(item.id);
                      setProgression({
                        next_level_id: item.next_level_id || "",
                        is_terminal: item.is_terminal,
                      });
                    }}
                  >
                    Configure progression
                  </Button>
                </div>
              ))}
            </div>
            {selectedLevelId ? (
              <form
                className="mt-4 space-y-3 border-t border-border pt-4"
                onSubmit={saveProgression}
              >
                <SelectControl
                  label="Next level"
                  value={progression.next_level_id}
                  onChange={(value) => setProgression((current) => ({
                    ...current,
                    next_level_id: value,
                  }))}
                  options={levelOptions.filter((item) => item.value !== selectedLevelId)}
                  disabled={progression.is_terminal}
                  clearable
                />
                <CheckboxControl
                  label="This is the terminal level"
                  checked={progression.is_terminal}
                  onChange={(value) => setProgression({
                    is_terminal: value,
                    next_level_id: value ? "" : progression.next_level_id,
                  })}
                />
                <FormActions submitting={saving} submitLabel="Save progression" />
              </form>
            ) : null}
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
