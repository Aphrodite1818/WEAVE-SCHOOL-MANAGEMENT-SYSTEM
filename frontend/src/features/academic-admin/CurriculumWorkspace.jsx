import CurriculumCopyPanel from "./CurriculumCopyPanel";
import { beginAcademicSubmission, endAcademicSubmission, finishAcademicCreation } from "./academicSubmission";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicLevelService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { curriculumService } from "../../services/curriculumService";
import { departmentService } from "../../services/departmentService";
import { subjectService } from "../../services/subject.service";
import {
  FormActions,
  Input,
  RecordList,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import { levelSupportsSpecialization } from "./academicDepartmentCapability";

const items = (value) => (Array.isArray(value) ? value : value?.items || []);

const scopeLabel = (row) => {
  const departments = row?.departments || [];
  if (departments.length === 0) return "General";
  return departments
    .map((item) => item.department_name || "Department")
    .filter(Boolean)
    .join(" · ");
};

export default function CurriculumWorkspace({ activeTab = "subjects" }) {
  const { showError, showSuccess } = useToast();
  const levelRequest = useRef(0);
  const [levels, setLevels] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [levelDepartments, setLevelDepartments] = useState([]);
  const [levelId, setLevelId] = useState("");
  const [curriculum, setCurriculum] = useState(null);
  const [selectedSubjectIds, setSelectedSubjectIds] = useState([]);
  const [query, setQuery] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [addDepartmentIds, setAddDepartmentIds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
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
    const request = ++levelRequest.current;
    if (!levelId) {
      setCurriculum(null);
      setLevelDepartments([]);
      return;
    }
    setLoading(true);
    setLoadError("");
    setCurriculum(null);
    try {
      const [curriculumResponse, departmentResponse] = await Promise.all([
        curriculumService.getCurriculum(levelId),
        departmentService.getLevelDepartments(levelId, { activeOnly: true }),
      ]);
      if (request !== levelRequest.current) return;
      const curriculumRows = curriculumResponse?.subjects || [];
      setCurriculum(curriculumResponse);
      setLevelDepartments(items(departmentResponse));
      setScopeSubjectId((current) =>
        curriculumRows.some((row) => row.id === current)
          ? current
          : curriculumRows[0]?.id || "",
      );
    } catch (error) {
      if (request !== levelRequest.current) return;
      setLoadError(getErrorMessage(error, "Could not load this level curriculum."));
    } finally {
      if (request === levelRequest.current) setLoading(false);
    }
  }, [levelId]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadLevel();
    return () => { levelRequest.current += 1; };
  }, [loadLevel]);

  useEffect(() => {
    setEditorMode("");
    setSelectedSubjectIds([]);
    setAddDepartmentIds([]);
    setReviewing(false);
  }, [activeTab, levelId]);

  const curriculumSubjects = useMemo(() => curriculum?.subjects || [], [curriculum]);
  const selectedLevel = useMemo(
    () => levels.find((row) => row.id === levelId) || null,
    [levelId, levels],
  );
  const specializationEnabled = levelSupportsSpecialization(selectedLevel);
  const attached = useMemo(
    () => new Set(curriculumSubjects.map((row) => row.subject_id)),
    [curriculumSubjects],
  );
  const available = subjects.filter(
    (row) => !attached.has(row.id) && row.is_active !== false && !row.archived_at,
  );
  const matchingSubjects = subjects.filter((row) => row.name.toLowerCase().includes(query.trim().toLowerCase()));
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
    if (!selectedSubjectIds.length || selectedSubjectIds.length > 100 || !levelId || !reviewing) return;
    const submission = beginAcademicSubmission(event, Boolean(saving));
    if (!submission) return;
    setSaving("subject");
    try {
      await curriculumService.addSubjects(levelId, {
        subjects: selectedSubjectIds.map((subject_id) => ({
          subject_id, is_elective: elective,
          academic_level_department_ids: specializationEnabled
            ? addDepartmentIds
            : [],
        })),
      });
      showSuccess(`${selectedSubjectIds.length} subjects added to the curriculum.`);
      finishAcademicCreation(submission, () => {
        setSelectedSubjectIds([]);
        setElective(false);
        setAddDepartmentIds([]);
        setReviewing(false);
      }, () => setEditorMode(""));
      await loadLevel();
    } catch (error) {
      showError(getErrorMessage(error, "Could not confirm subjects were saved. Refresh the curriculum before retrying."));
    } finally {
      endAcademicSubmission(submission);
      setSaving("");
    }
  };

  const copyCurriculum = async (event, sourceLevelId) => {
    const submission = beginAcademicSubmission(event, Boolean(saving));
    if (!submission) return;
    setSaving("copy");
    try {
      const result = await curriculumService.copyCurriculum(levelId, sourceLevelId);
      showSuccess(`${result.created} subjects copied. ${result.skipped_existing} already present; ${result.skipped_inactive} inactive subjects skipped.`);
      setEditorMode("");
      await loadLevel();
    } catch (error) {
      showError(getErrorMessage(error, "Could not confirm the curriculum was copied. Refresh before retrying."));
    } finally {
      endAcademicSubmission(submission);
      setSaving("");
    }
  };

  const toggleElective = async (row) => {
    if (saving) return;
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
    if (saving) return;
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
    if (!specializationEnabled || !scopeSubjectId || saving) return;
    const submission = beginAcademicSubmission(event, Boolean(saving));
    if (!submission) return;
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
      endAcademicSubmission(submission);
      setSaving("");
    }
  };

  const editApplicability = (row) => {
    if (!specializationEnabled || !levelDepartments.length) return;
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
      disabled={Boolean(saving)}
    />
  );

  if (activeTab === "applicability") {
    const editorOpen =
      editorMode === "applicability" && specializationEnabled;
    return (
      <WorkspaceGrid
        editor={
          editorOpen ? (
            <WorkspacePanel
              title="Subject applicability"
              description="Choose which specializations receive this subject once specialization is active. With no departments selected, the subject is general and remains available to every class."
            >
              <form className="space-y-4" onSubmit={saveApplicability}>
                <fieldset disabled={Boolean(saving)} className="space-y-4">
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
                    {saving === "applicability" ? "Saving…" : "Save changes"}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setEditorMode("")}>
                    Cancel
                  </Button>
                </div>
                </fieldset>
              </form>
            </WorkspacePanel>
          ) : null
        }
        content={
          <RecordList
            title="Subject applicability"
            description={
              specializationEnabled
                ? "Department scope is part of the level curriculum. Before specialization begins, every active curriculum subject remains available to every class."
                : "This level does not specialize. Every curriculum subject is General and available to every class in the level."
            }
            actions={<div className="min-w-[18rem]">{levelControl}</div>}
            loading={loading}
          error={loadError}
          onRetry={loadLevel}
          items={curriculumSubjects}
            emptyTitle="No curriculum subjects"
            emptyDescription="Add subjects to this level before configuring specialization applicability."
            renderTitle={(row) => row.subject_name}
            renderMeta={(row) => (row.is_elective ? "Elective" : "Compulsory")}
            renderDescription={(row) =>
              specializationEnabled
                ? `Available to: ${scopeLabel(row)}`
                : "General — available to every class in this level."
            }
            renderStatus={(row) => (row.is_active === false ? "inactive" : "active")}
            showInspector={!editorOpen}
            renderActions={(row) =>
              specializationEnabled && levelDepartments.length ? (
                <Button
                  size="small"
                  variant="outline"
                  disabled={row.is_active === false}
                  onClick={() => editApplicability(row)}
                >
                  Edit applicability
                </Button>
              ) : null
            }
          />
        }
      />
    );
  }

  const editorOpen = ["subject", "copy"].includes(editorMode);
  return (
    <WorkspaceGrid
      editor={
        editorMode === "copy" && selectedLevel ? (
          <CurriculumCopyPanel key={levelId} levels={levels} target={selectedLevel}
            targetSubjects={curriculumSubjects} targetDepartments={levelDepartments}
            saving={Boolean(saving)} onCopy={copyCurriculum} onCancel={() => setEditorMode("")} />
        ) : editorOpen ? (
          <WorkspacePanel
            title="Add subjects to curriculum"
            description={
              specializationEnabled
                ? "Select subjects, set elective status and department applicability, then review before saving."
                : "Select subjects, set elective status, then review before saving. Subjects in this level are General."
            }
          >
            <form className="space-y-3" onSubmit={addSubject}>
              <fieldset disabled={Boolean(saving)} className="space-y-3">
                {!reviewing ? (
                  <>
                    <Input label="Search subjects" value={query} onChange={(event) => setQuery(event.target.value)} autoFocus />
                    <Button type="button" variant="outline" onClick={() => setSelectedSubjectIds((current) => [...new Set([...current, ...available.filter((row) => row.name.toLowerCase().includes(query.toLowerCase())).map((row) => row.id)])])}>
                      Select all matching available subjects
                    </Button>
                    <div className="max-h-72 space-y-2 overflow-y-auto rounded-lg border border-border p-3">
                      {matchingSubjects.map((row) => (
                        <label key={row.id} className="flex items-center gap-2 text-sm">
                          <input type="checkbox" checked={selectedSubjectIds.includes(row.id)} disabled={attached.has(row.id) || !available.some((item) => item.id === row.id)} onChange={(event) => setSelectedSubjectIds((current) => event.target.checked ? [...current, row.id] : current.filter((id) => id !== row.id))} />
                          {row.name}{attached.has(row.id) ? " - Already added" : row.is_active === false || row.archived_at ? " - Inactive" : ""}
                        </label>
                      ))}
                      {!matchingSubjects.length ? <p>No subjects match your search.</p> : null}
                    </div>
                    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={elective} onChange={(event) => setElective(event.target.checked)} /> Elective subjects</label>
                    {specializationEnabled ? (
                      <>
                        <p className="text-sm font-semibold">Department applicability</p>
                        <p className="text-sm text-text-muted">No departments selected means General. These settings apply to every selected subject.</p>
                        {levelDepartments.map((row) => (
                          <label key={row.id} className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={addDepartmentIds.includes(row.id)} onChange={(event) => setAddDepartmentIds((current) => event.target.checked ? [...current, row.id] : current.filter((id) => id !== row.id))} />
                            {row.department_name}
                          </label>
                        ))}
                      </>
                    ) : null}
                    {selectedSubjectIds.length > 100 ? <p role="alert" className="text-sm text-error">Select at most 100 subjects per batch.</p> : null}
                    <Button type="button" disabled={!selectedSubjectIds.length || selectedSubjectIds.length > 100} onClick={() => setReviewing(true)}>Review {selectedSubjectIds.length} subjects</Button>
                  </>
                ) : (
                  <>
                    <p className="text-sm">{subjects.filter((row) => selectedSubjectIds.includes(row.id)).map((row) => row.name).join(", ")}</p>
                    <p className="text-sm">{elective ? "Elective" : "Compulsory"} / {specializationEnabled && addDepartmentIds.length ? levelDepartments.filter((row) => addDepartmentIds.includes(row.id)).map((row) => row.department_name).join(", ") : "General"}</p>
                    <Button type="button" variant="outline" onClick={() => setReviewing(false)}>Change selection</Button>
                    <FormActions repeatable submitting={Boolean(saving)} onCancel={() => setEditorMode("")} />
                  </>
                )}
              </fieldset>
            </form>
          </WorkspacePanel>
        ) : null
      }
      content={
        <RecordList
          title={curriculum?.level_name ? `${curriculum.level_name} curriculum` : "Curriculum"}
          description="The persistent level subject set used by teacher assignments, results, CBT, and report cards."
          actions={
            <div className="flex w-full min-w-0 flex-col gap-3 sm:w-72">
              <div className="w-full min-w-0">{levelControl}</div>
              {!editorOpen ? (
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" disabled={loading || Boolean(loadError) || !curriculum} onClick={() => setEditorMode("copy")}>
                    Copy curriculum
                  </Button>
                  <Button type="button" disabled={loading || Boolean(loadError) || !curriculum} onClick={() => setEditorMode("subject")}>
                    Add subjects
                  </Button>
                </div>
              ) : null}
            </div>
          }
          loading={loading}
          error={loadError}
          onRetry={loadLevel}
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
                disabled={Boolean(saving)}
                onClick={() => toggleElective(row)}
              >
                {row.is_elective ? "Make compulsory" : "Make elective"}
              </Button>
              <Button
                size="small"
                variant="outline"
                disabled={Boolean(saving)}
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
