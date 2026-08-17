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
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const items = (value) => (Array.isArray(value) ? value : value?.items || []);
const termName = (value) =>
  String(value || "Term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function CurriculumWorkspace() {
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
          current ||
          termRows.find((term) => term.is_current)?.id ||
          termRows[0]?.id ||
          "",
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
        items(departmentResponse).filter(
          (row) => row.is_active !== false && !row.archived_at,
        ),
      );
      setScopeSubjectId((current) =>
        (curriculumResponse?.subjects || []).some((row) => row.id === current)
          ? current
          : curriculumResponse?.subjects?.[0]?.id || "",
      );
      setDepartmentId("");
    } catch (error) {
      showError(
        getErrorMessage(error, "Could not load this level curriculum."),
      );
    }
  }, [levelId, showError]);

  const loadOfferings = useCallback(async () => {
    if (!scopeSubjectId) {
      setOfferings([]);
      return;
    }
    try {
      setOfferings(
        items(await curriculumService.listOfferings(scopeSubjectId)),
      );
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

  const attached = useMemo(
    () => new Set((curriculum?.subjects || []).map((row) => row.subject_id)),
    [curriculum],
  );
  const available = subjects.filter(
    (row) =>
      !attached.has(row.id) && row.is_active !== false && !row.archived_at,
  );
  const termById = useMemo(
    () => new Map(terms.map((row) => [row.id, row])),
    [terms],
  );
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
      await curriculumService.updateSubject(row.id, {
        is_elective: !row.is_elective,
      });
      await loadLevel();
      showSuccess(
        row.is_elective
          ? "Subject is now compulsory."
          : "Subject is now elective.",
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not update curriculum subject."));
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
      await loadOfferings();
      showSuccess(
        departmentId
          ? "Department-specific offering configured."
          : "General level offering configured.",
      );
    } catch (error) {
      showError(
        getErrorMessage(error, "Could not configure this term offering."),
      );
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

  const curriculumSubjects = curriculum?.subjects || [];

  return (
    <div className="space-y-4">
      <WorkspaceGrid
        editor={
          <WorkspacePanel
            title="Add curriculum subject"
            description="Create each subject once in the school subject pool, then attach it to the academic level here."
          >
            <form className="space-y-3" onSubmit={addSubject}>
              <SelectControl
                label="Academic level"
                value={levelId}
                onChange={setLevelId}
                options={levels.map((row) => ({
                  value: row.id,
                  label: row.name,
                }))}
                required
              />
              <SelectControl
                label="Subject"
                value={subjectId}
                onChange={setSubjectId}
                options={available.map((row) => ({
                  value: row.id,
                  label: row.name,
                }))}
                placeholder={
                  available.length
                    ? "Select subject"
                    : "All active subjects are attached"
                }
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
              <Button
                type="submit"
                disabled={saving === "subject" || !subjectId}
              >
                {saving === "subject" ? "Saving…" : "Add to curriculum"}
              </Button>
            </form>
          </WorkspacePanel>
        }
        content={
          <WorkspacePanel
            title={
              curriculum?.level_name
                ? `${curriculum.level_name} curriculum`
                : "Curriculum"
            }
            description="These subjects belong to the level. Term offerings below decide whether each subject is general or department-specific."
          >
            <div className="space-y-2">
              {curriculumSubjects.map((row) => (
                <div
                  key={row.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-border/70 px-3 py-3"
                >
                  <div>
                    <p className="font-semibold text-text">
                      {row.subject_name}
                    </p>
                    <p className="text-xs text-text-muted">
                      {row.is_elective ? "Elective" : "Compulsory"}
                    </p>
                  </div>
                  <Button
                    size="small"
                    variant="outline"
                    disabled={saving === row.id}
                    onClick={() => toggleElective(row)}
                  >
                    {row.is_elective ? "Make compulsory" : "Make elective"}
                  </Button>
                </div>
              ))}
              {!curriculumSubjects.length ? (
                <p className="text-sm text-text-muted">
                  No subjects have been added yet.
                </p>
              ) : null}
            </div>
          </WorkspacePanel>
        }
      />

      <WorkspaceGrid
        editor={
          <WorkspacePanel
            title="Configure term offering"
            description="General subjects reach every class in the level. A department-specific subject can be offered to one or more departments in the same level."
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
              <Button
                type="submit"
                disabled={saving === "offering" || !scopeSubjectId || !termId}
              >
                {saving === "offering" ? "Saving…" : "Configure offering"}
              </Button>
            </form>
          </WorkspacePanel>
        }
        content={
          <WorkspacePanel
            title="Configured term offerings"
            description="A subject may be general for the term or restricted to one or more departments. Remove the general offering before switching to department-specific scopes. Historical terms are protected."
          >
            <div className="space-y-2">
              {offerings.map((row) => {
                const term = termById.get(row.academic_term_id);
                const department = row.department_id
                  ? departmentById.get(row.department_id)
                  : null;
                return (
                  <div
                    key={row.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-border/70 px-3 py-3"
                  >
                    <div>
                      <p className="font-semibold text-text">
                        {term ? termName(term.name) : "Academic term"}
                      </p>
                      <p className="text-xs text-text-muted">
                        {department
                          ? `${department.name} department`
                          : "General · all classes in level"}
                      </p>
                    </div>
                    <Button
                      size="small"
                      variant="outline"
                      disabled={saving === row.id}
                      onClick={() => removeOffering(row)}
                    >
                      Remove
                    </Button>
                  </div>
                );
              })}
              {!offerings.length ? (
                <p className="text-sm text-text-muted">
                  No term offering is configured for the selected curriculum
                  subject.
                </p>
              ) : null}
            </div>
          </WorkspacePanel>
        }
      />
    </div>
  );
}
