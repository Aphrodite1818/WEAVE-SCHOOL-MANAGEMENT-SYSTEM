import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import {
  academicLevelService,
  departmentService,
} from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { curriculumService } from "../../services/curriculumService";
import { subjectService } from "../../services/subject.service";
import {
  RecordList,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const items = (value) => (Array.isArray(value) ? value : value?.items || []);
const termName = (value) =>
  String(value || "Term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function CurriculumWorkspace({ activeTab = "subjects" }) {
  const { showError, showSuccess } = useToast();
  const [levels, setLevels] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [terms, setTerms] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [levelId, setLevelId] = useState("");
  const [curriculum, setCurriculum] = useState(null);
  const [subjectId, setSubjectId] = useState("");
  const [elective, setElective] = useState(false);
  const [scopeSubjectId, setScopeSubjectId] = useState("");
  const [termId, setTermId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [offerings, setOfferings] = useState([]);
  const [editorMode, setEditorMode] = useState("");
  const [saving, setSaving] = useState("");

  const loadBase = useCallback(async () => {
    try {
      const [levelResponse, subjectResponse, termResponse] = await Promise.all([
        academicLevelService.getLevels({ activeOnly: true }),
        subjectService.getSubjects({ limit: 500 }),
        academicService.listTerms({ limit: 100 }),
      ]);
      const levelRows = items(levelResponse);
      const termRows = items(termResponse).filter((term) =>
        ["draft", "open"].includes(String(term.status || "").toLowerCase()),
      );
      setLevels(levelRows);
      setSubjects(items(subjectResponse));
      setTerms(termRows);
      setLevelId((current) => current || levelRows[0]?.id || "");
      setTermId(
        (current) =>
          current || termRows.find((term) => term.is_current)?.id || termRows[0]?.id || "",
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load curriculum setup."));
    }
  }, [showError]);

  const loadLevel = useCallback(async () => {
    if (!levelId) {
      setCurriculum(null);
      setDepartments([]);
      return;
    }
    try {
      const [curriculumResponse, departmentResponse] = await Promise.all([
        curriculumService.getCurriculum(levelId),
        departmentService.getDepartments(levelId),
      ]);
      setCurriculum(curriculumResponse);
      setDepartments(
        items(departmentResponse).filter((row) => row.is_active !== false && !row.archived_at),
      );
      setScopeSubjectId((current) =>
        (curriculumResponse?.subjects || []).some((row) => row.id === current)
          ? current
          : curriculumResponse?.subjects?.[0]?.id || "",
      );
      setDepartmentId("");
    } catch (error) {
      showError(getErrorMessage(error, "Could not load this level curriculum."));
    }
  }, [levelId, showError]);

  const loadOfferings = useCallback(async () => {
    if (!scopeSubjectId) {
      setOfferings([]);
      return;
    }
    try {
      setOfferings(items(await curriculumService.listOfferings(scopeSubjectId)));
    } catch (error) {
      showError(getErrorMessage(error, "Could not load subject offerings."));
    }
  }, [scopeSubjectId, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);
  useEffect(() => {
    loadLevel();
  }, [loadLevel]);
  useEffect(() => {
    loadOfferings();
  }, [loadOfferings]);
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
  const termById = useMemo(() => new Map(terms.map((row) => [row.id, row])), [terms]);
  const departmentById = useMemo(
    () => new Map(departments.map((row) => [row.id, row])),
    [departments],
  );

  const addSubject = async (event) => {
    event.preventDefault();
    if (!subjectId || !levelId) return;
    setSaving("subject");
    try {
      await curriculumService.addSubject(levelId, {
        subject_id: subjectId,
        is_elective: elective,
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

  const addOffering = async (event) => {
    event.preventDefault();
    if (!scopeSubjectId || !termId) return;
    setSaving("offering");
    try {
      await curriculumService.addOffering(scopeSubjectId, {
        academic_term_id: termId,
        department_id: departmentId || null,
      });
      setEditorMode("");
      await loadOfferings();
      showSuccess(
        departmentId
          ? "Department-specific offering configured."
          : "General level offering configured.",
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not configure this term offering."));
    } finally {
      setSaving("");
    }
  };

  const removeOffering = async (row) => {
    setSaving(row.id);
    try {
      await curriculumService.removeOffering(row.id);
      await loadOfferings();
      showSuccess("Term offering removed.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not remove this term offering."));
    } finally {
      setSaving("");
    }
  };

  const offeringRows = offerings.map((row) => {
    const term = termById.get(row.academic_term_id);
    const department = row.department_id ? departmentById.get(row.department_id) : null;
    return {
      ...row,
      termLabel: term ? termName(term.name) : "Academic term",
      scopeLabel: department ? `${department.name} department` : "General · all classes in level",
    };
  });

  const levelControl = (
    <SelectControl
      label="Academic level"
      value={levelId}
      onChange={setLevelId}
      options={levels.map((row) => ({ value: row.id, label: row.name }))}
      required
    />
  );

  if (activeTab === "offerings") {
    const editorOpen = editorMode === "offering";
    return (
      <WorkspaceGrid
        editor={
          editorOpen ? (
            <WorkspacePanel
              title="Configure term offering"
              description="General offerings reach every class in the level; department offerings target one specialization."
            >
              <form className="space-y-3" onSubmit={addOffering}>
                <SelectControl
                  label="Curriculum subject"
                  value={scopeSubjectId}
                  onChange={setScopeSubjectId}
                  options={curriculumSubjects
                    .filter((row) => row.is_active !== false)
                    .map((row) => ({ value: row.id, label: row.subject_name }))}
                  required
                />
                <SelectControl
                  label="Academic term"
                  value={termId}
                  onChange={setTermId}
                  options={terms.map((row) => ({
                    value: row.id,
                    label: `${termName(row.name)} · ${row.status}`,
                  }))}
                  required
                />
                <SelectControl
                  label="Scope"
                  value={departmentId}
                  onChange={setDepartmentId}
                  options={[
                    { value: "", label: "General — every class in this level" },
                    ...departments.map((row) => ({
                      value: row.id,
                      label: `${row.name} department only`,
                    })),
                  ]}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="submit"
                    disabled={saving === "offering" || !scopeSubjectId || !termId}
                  >
                    {saving === "offering" ? "Saving…" : "Configure offering"}
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
            title="Term offerings"
            description="Offerings decide whether a curriculum subject is taught generally or to a department in a specific term."
            actions={
              <div className="flex min-w-[18rem] flex-col gap-2 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1">{levelControl}</div>
                {!editorOpen ? (
                  <Button type="button" onClick={() => setEditorMode("offering")}>
                    Configure offering
                  </Button>
                ) : null}
              </div>
            }
            items={offeringRows}
            emptyTitle="No term offerings"
            emptyDescription="Configure a term and scope for the selected curriculum subject."
            renderTitle={(row) => row.termLabel}
            renderMeta={(row) => row.scopeLabel}
            renderDescription={() =>
              curriculumSubjects.find((row) => row.id === scopeSubjectId)?.subject_name ||
              "Curriculum subject"
            }
            renderStatus={() => "configured"}
            showInspector={!editorOpen}
            renderActions={(row) => (
              <Button
                size="small"
                variant="outline"
                disabled={saving === row.id}
                onClick={() => removeOffering(row)}
              >
                Remove
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
            description="Create a subject once in the school subject pool, then attach it to this academic level."
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
          description="The level-owned source used by term offerings, teacher assignments, results, and reports."
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
          renderDescription={() =>
            "Available for term offerings, teacher assignments, results, and report cards."
          }
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
