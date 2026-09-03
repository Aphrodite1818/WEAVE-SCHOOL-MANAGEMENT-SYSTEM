import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicLevelService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { curriculumService } from "../../services/curriculumService";
import { departmentService } from "../../services/departmentService";
import { subjectService } from "../../services/subject.service";
import {
  RecordList,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const items = (value) => (Array.isArray(value) ? value : value?.items || []);

const scopeLabel = (row) => {
  const departments = row?.departments || [];
  if (departments.length === 0) return "All specializations";
  return departments
    .map((item) => item.department_name || "Department")
    .filter(Boolean)
    .join(" · ");
};

export default function CurriculumWorkspace({ activeTab = "subjects" }) {
  const { showError, showSuccess } = useToast();
  const [levels, setLevels] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [levelDepartments, setLevelDepartments] = useState([]);
  const [levelId, setLevelId] = useState("");
  const [curriculum, setCurriculum] = useState(null);
  const [subjectId, setSubjectId] = useState("");
  const [elective, setElective] = useState(false);
  const [scopeSubjectId, setScopeSubjectId] = useState("");
  const [selectedDepartmentIds, setSelectedDepartmentIds] = useState([]);
  const [editorMode, setEditorMode] = useState("");
  const [saving, setSaving] = useState("");

  const loadBase = useCallback(async () => {
    try {
      const [levelResponse, subjectResponse] = await Promise.all([
        academicLevelService.getLevels({ activeOnly: true }),
        subjectService.getSubjects({ limit: 500 }),
      ]);
      const levelRows = items(levelResponse);
      setLevels(levelRows);
      setSubjects(items(subjectResponse));
      setLevelId((current) => current || levelRows[0]?.id || "");
    } catch (error) {
      showError(getErrorMessage(error, "Could not load curriculum setup."));
    }
  }, [showError]);

  const loadLevel = useCallback(async () => {
    if (!levelId) {
      setCurriculum(null);
      setLevelDepartments([]);
      return;
    }
    try {
      const [curriculumResponse, departmentResponse] = await Promise.all([
        curriculumService.getCurriculum(levelId),
        departmentService.getLevelDepartments(levelId, { activeOnly: true }),
      ]);
      const curriculumRows = curriculumResponse?.subjects || [];
      setCurriculum(curriculumResponse);
      setLevelDepartments(items(departmentResponse));
      setScopeSubjectId((current) =>
        curriculumRows.some((row) => row.id === current)
          ? current
          : curriculumRows[0]?.id || "",
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load this level curriculum."));
    }
  }, [levelId, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadLevel();
  }, [loadLevel]);

  useEffect(() => {
    setEditorMode("");
  }, [activeTab, levelId]);

  const curriculumSubjects = useMemo(() => curriculum?.subjects || [], [curriculum]);
  const attached = useMemo(
    () => new Set(curriculumSubjects.map((row) => row.subject_id)),
    [curriculumSubjects],
  );
  const available = subjects.filter(
    (row) => !attached.has(row.id) && row.is_active !== false && !row.archived_at,
  );
  const selectedScopeSubject = useMemo(
    () => curriculumSubjects.find((row) => row.id === scopeSubjectId) || null,
    [curriculumSubjects, scopeSubjectId],
  );

  useEffect(() => {
    setSelectedDepartmentIds(
      (selectedScopeSubject?.departments || []).map(
        (item) => item.academic_level_department_id,
      ),
    );
  }, [selectedScopeSubject]);

  const addSubject = async (event) => {
    event.preventDefault();
    if (!subjectId || !levelId) return;
    setSaving("subject");
    try {
      await curriculumService.addSubject(levelId, {
        subject_id: subjectId,
        is_elective: elective,
        academic_level_department_ids: [],
      });
      setSubjectId("");
      setElective(false);
      setEditorMode("");
      await loadLevel();
      showSuccess("Subject added to the level curriculum.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not add subject."));
    } finally {
      setSaving("");
    }
  };

  const toggleElective = async (row) => {
    setSaving(row.id);
    try {
      await curriculumService.updateSubject(row.id, { is_elective: !row.is_elective });
      await loadLevel();
      showSuccess(row.is_elective ? "Subject is now compulsory." : "Subject is now elective.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not update curriculum subject."));
    } finally {
      setSaving("");
    }
  };

  const updateLifecycle = async (row, action) => {
    setSaving(row.id);
    try {
      if (action === "activate") await curriculumService.activateSubject(row.id);
      if (action === "deactivate") await curriculumService.deactivateSubject(row.id);
      await loadLevel();
      showSuccess(`Curriculum subject ${action}d.`);
    } catch (error) {
      showError(getErrorMessage(error, `Could not ${action} curriculum subject.`));
    } finally {
      setSaving("");
    }
  };

  const toggleDepartment = (departmentId) => {
    setSelectedDepartmentIds((current) =>
      current.includes(departmentId)
        ? current.filter((id) => id !== departmentId)
        : [...current, departmentId],
    );
  };

  const saveApplicability = async (event) => {
    event.preventDefault();
    if (!scopeSubjectId) return;
    setSaving("applicability");
    try {
      await curriculumService.updateSubject(scopeSubjectId, {
        academic_level_department_ids: selectedDepartmentIds,
      });
      setEditorMode("");
      await loadLevel();
      showSuccess(
        selectedDepartmentIds.length
          ? "Subject applicability updated."
          : "Subject is now available to all specializations.",
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not update subject applicability."));
    } finally {
      setSaving("");
    }
  };

  const editApplicability = (row) => {
    setScopeSubjectId(row.id);
    setSelectedDepartmentIds(
      (row.departments || []).map((item) => item.academic_level_department_id),
    );
    setEditorMode("applicability");
  };

  const levelControl = (
    <SelectControl
      label="Academic level"
      value={levelId}
      onChange={setLevelId}
      options={levels.map((row) => ({ value: row.id, label: row.name }))}
      required
    />
  );

  if (activeTab === "applicability") {
    const editorOpen = editorMode === "applicability";
    return (
      <WorkspaceGrid
        editor={
          editorOpen ? (
            <WorkspacePanel
              title="Subject applicability"
              description="Choose which specializations receive this subject once specialization is active. With no departments selected, the subject is general and remains available to every class."
            >
              <form className="space-y-4" onSubmit={saveApplicability}>
                <SelectControl
                  label="Curriculum subject"
                  value={scopeSubjectId}
                  onChange={setScopeSubjectId}
                  options={curriculumSubjects
                    .filter((row) => row.is_active !== false)
                    .map((row) => ({ value: row.id, label: row.subject_name }))}
                  required
                />

                {levelDepartments.length ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-text">Available to</p>
                      <Button
                        type="button"
                        size="small"
                        variant="outline"
                        onClick={() => setSelectedDepartmentIds([])}
                      >
                        All specializations
                      </Button>
                    </div>
                    <div className="space-y-2 rounded-xl border border-border bg-surface-muted p-3">
                      {levelDepartments.map((row) => (
                        <label
                          key={row.id}
                          className="flex items-center gap-3 text-sm text-text"
                        >
                          <input
                            type="checkbox"
                            checked={selectedDepartmentIds.includes(row.id)}
                            onChange={() => toggleDepartment(row.id)}
                          />
                          <span>{row.department_name || "Department"}</span>
                        </label>
                      ))}
                    </div>
                    <p className="text-xs leading-5 text-text-muted">
                      {selectedDepartmentIds.length === 0
                        ? "General subject — available to every specialization."
                        : "Specialization-scoped subject — available only to the selected departments after specialization begins."}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm leading-6 text-text-muted">
                    This level has no department specializations. Subjects are available to every class in the level.
                  </p>
                )}

                <div className="flex flex-wrap gap-2">
                  <Button
                    type="submit"
                    disabled={saving === "applicability" || !scopeSubjectId}
                  >
                    {saving === "applicability" ? "Saving…" : "Save applicability"}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setEditorMode("")}>
                    Cancel
                  </Button>
                </div>
              </form>
            </WorkspacePanel>
          ) : null
        }
        content={
          <RecordList
            title="Subject applicability"
            description="Department scope is part of the level curriculum. Before specialization begins, every active curriculum subject remains available to every class."
            actions={<div className="min-w-[18rem]">{levelControl}</div>}
            items={curriculumSubjects}
            emptyTitle="No curriculum subjects"
            emptyDescription="Add subjects to this level before configuring specialization applicability."
            renderTitle={(row) => row.subject_name}
            renderMeta={(row) => (row.is_elective ? "Elective" : "Compulsory")}
            renderDescription={(row) => `Available to: ${scopeLabel(row)}`}
            renderStatus={(row) => (row.is_active === false ? "inactive" : "active")}
            showInspector={!editorOpen}
            renderActions={(row) => (
              <Button
                size="small"
                variant="outline"
                disabled={row.is_active === false}
                onClick={() => editApplicability(row)}
              >
                Edit applicability
              </Button>
            )}
          />
        }
      />
    );
  }

  const editorOpen = editorMode === "subject";
  return (
    <WorkspaceGrid
      editor={
        editorOpen ? (
          <WorkspacePanel
            title="Add curriculum subject"
            description="Create a subject once in the school subject pool, then attach it to this academic level. New subjects start as general and can be scoped under Subject Applicability."
          >
            <form className="space-y-3" onSubmit={addSubject}>
              <SelectControl
                label="Subject"
                value={subjectId}
                onChange={setSubjectId}
                options={available.map((row) => ({ value: row.id, label: row.name }))}
                placeholder={available.length ? "Select subject" : "All active subjects are attached"}
                required
              />
              <label className="flex items-center gap-2 text-sm font-medium text-text">
                <input
                  type="checkbox"
                  checked={elective}
                  onChange={(event) => setElective(event.target.checked)}
                />
                Elective subject
              </label>
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={saving === "subject" || !subjectId}>
                  {saving === "subject" ? "Saving…" : "Add to curriculum"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setEditorMode("")}>
                  Cancel
                </Button>
              </div>
            </form>
          </WorkspacePanel>
        ) : null
      }
      content={
        <RecordList
          title={curriculum?.level_name ? `${curriculum.level_name} curriculum` : "Curriculum"}
          description="The persistent level subject set used by teacher assignments, results, CBT, and report cards."
          actions={
            <div className="flex min-w-[18rem] flex-col gap-2 sm:flex-row sm:items-end">
              <div className="min-w-0 flex-1">{levelControl}</div>
              {!editorOpen ? (
                <Button type="button" onClick={() => setEditorMode("subject")}>
                  Add subject
                </Button>
              ) : null}
            </div>
          }
          items={curriculumSubjects}
          emptyTitle="No curriculum subjects"
          emptyDescription="Attach a subject from the school subject pool."
          renderTitle={(row) => row.subject_name}
          renderMeta={(row) => (row.is_elective ? "Elective" : "Compulsory")}
          renderDescription={(row) => `Available to: ${scopeLabel(row)}`}
          renderStatus={(row) => (row.is_active === false ? "inactive" : "active")}
          showInspector={!editorOpen}
          renderActions={(row) => (
            <>
              <Button
                size="small"
                variant="outline"
                disabled={saving === row.id}
                onClick={() => toggleElective(row)}
              >
                {row.is_elective ? "Make compulsory" : "Make elective"}
              </Button>
              <Button
                size="small"
                variant="outline"
                disabled={saving === row.id}
                onClick={() =>
                  updateLifecycle(row, row.is_active === false ? "activate" : "deactivate")
                }
              >
                {row.is_active === false ? "Activate" : "Deactivate"}
              </Button>
            </>
          )}
        />
      }
    />
  );
}
