import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import {
  academicLevelService,
  classService,
  departmentService,
} from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { curriculumService } from "../../services/curriculumService";
import {
  Input,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const items = (value) => (Array.isArray(value) ? value : value?.items || []);
const classLabel = (row) =>
  row?.display_name ||
  [row?.academic_level_name, row?.arm_label].filter(Boolean).join(" ") ||
  "Class";
const termName = (value) =>
  String(value || "Term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function DepartmentsWorkspace() {
  const { showError, showSuccess } = useToast();
  const [levels, setLevels] = useState([]);
  const [categories, setCategories] = useState([]);
  const [classes, setClasses] = useState([]);
  const [terms, setTerms] = useState([]);
  const [levelId, setLevelId] = useState("");
  const [departments, setDepartments] = useState([]);
  const [name, setName] = useState("");
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [currentAssignment, setCurrentAssignment] = useState(null);
  const [saving, setSaving] = useState("");

  const loadBase = useCallback(async () => {
    try {
      const [levelResponse, categoryResponse, classResponse, termResponse] =
        await Promise.all([
          academicLevelService.getLevels({ activeOnly: true }),
          academicLevelService.getCategories(),
          classService.getClasses({ activeOnly: true, limit: 500 }),
          academicService.listTerms({ limit: 100 }),
        ]);
      setLevels(items(levelResponse));
      setCategories(items(categoryResponse));
      setClasses(items(classResponse));
      const termRows = items(termResponse).filter((term) =>
        ["draft", "open"].includes(String(term.status || "").toLowerCase()),
      );
      setTerms(termRows);
      setTermId((current) =>
        current || termRows.find((term) => term.is_current)?.id || termRows[0]?.id || "",
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load department setup."));
    }
  }, [showError]);

  const eligibleLevels = useMemo(() => {
    const allowed = new Set(
      categories.filter((row) => row.supports_departments).map((row) => row.value),
    );
    return levels.filter((row) => allowed.has(row.category));
  }, [levels, categories]);

  const levelClasses = useMemo(
    () => classes.filter((row) => row.academic_level_id === levelId),
    [classes, levelId],
  );

  const loadDepartments = useCallback(async () => {
    if (!levelId) {
      setDepartments([]);
      return;
    }
    try {
      setDepartments(
        items(await departmentService.getDepartments(levelId)).filter(
          (row) => row.is_active !== false && !row.archived_at,
        ),
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load departments."));
    }
  }, [levelId, showError]);

  const loadCurrentAssignment = useCallback(async () => {
    if (!classId || !termId) {
      setCurrentAssignment(null);
      setDepartmentId("");
      return;
    }
    try {
      const assignment = await curriculumService.getClassDepartment(classId, termId);
      setCurrentAssignment(assignment || null);
      setDepartmentId(assignment?.department_id || "");
    } catch (error) {
      setCurrentAssignment(null);
      setDepartmentId("");
      showError(getErrorMessage(error, "Could not load this class specialization."));
    }
  }, [classId, termId, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    if (!eligibleLevels.some((row) => row.id === levelId)) {
      setLevelId(eligibleLevels[0]?.id || "");
    }
  }, [eligibleLevels, levelId]);

  useEffect(() => {
    loadDepartments();
  }, [loadDepartments]);

  useEffect(() => {
    if (!levelClasses.some((row) => row.id === classId)) {
      setClassId(levelClasses[0]?.id || "");
    }
  }, [classId, levelClasses]);

  useEffect(() => {
    loadCurrentAssignment();
  }, [loadCurrentAssignment]);

  const createDepartment = async (event) => {
    event.preventDefault();
    if (!name.trim() || !levelId) return;
    setSaving("department");
    try {
      await departmentService.createDepartment(levelId, { name: name.trim() });
      setName("");
      await loadDepartments();
      showSuccess("Department created.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not create department."));
    } finally {
      setSaving("");
    }
  };

  const saveClassSpecialization = async (event) => {
    event.preventDefault();
    if (!classId || !termId) return;
    setSaving("placement");
    try {
      if (departmentId) {
        const assignment = await curriculumService.setClassDepartment(
          classId,
          termId,
          departmentId,
        );
        setCurrentAssignment(assignment);
        showSuccess("Class department set for this term.");
      } else {
        await curriculumService.clearClassDepartment(classId, termId);
        setCurrentAssignment(null);
        showSuccess("Class returned to general level placement for this term.");
      }
    } catch (error) {
      showError(getErrorMessage(error, "Could not update class specialization."));
      await loadCurrentAssignment();
    } finally {
      setSaving("");
    }
  };

  const currentDepartment = departments.find(
    (row) => row.id === currentAssignment?.department_id,
  );

  return (
    <div className="space-y-4">
      <WorkspaceGrid
        editor={(
          <WorkspacePanel
            title="Add department"
            description="Departments belong to a level. Only institution categories that support specialization appear here."
          >
            <form className="space-y-3" onSubmit={createDepartment}>
              <SelectControl
                label="Academic level"
                value={levelId}
                onChange={setLevelId}
                options={eligibleLevels.map((row) => ({ value: row.id, label: row.name }))}
                required
              />
              <Input
                label="Department name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Science"
                required
              />
              <Button
                type="submit"
                disabled={saving === "department" || !levelId || !name.trim()}
              >
                {saving === "department" ? "Saving…" : "Add department"}
              </Button>
            </form>
          </WorkspacePanel>
        )}
        content={(
          <WorkspacePanel
            title="Level departments"
            description="Department definitions are reusable within this level. They do not change a class until you assign one for a specific term."
          >
            {eligibleLevels.length === 0 ? (
              <p className="text-sm text-text-muted">No configured level supports departments.</p>
            ) : (
              <div className="space-y-2">
                {departments.map((row) => (
                  <div
                    key={row.id}
                    className="rounded-xl border border-border/70 px-3 py-3"
                  >
                    <p className="font-semibold text-text">{row.name}</p>
                  </div>
                ))}
                {!departments.length ? (
                  <p className="text-sm text-text-muted">No departments for this level yet.</p>
                ) : null}
              </div>
            )}
          </WorkspacePanel>
        )}
      />

      <WorkspaceGrid
        editor={(
          <WorkspacePanel
            title="Set class specialization"
            description="Specialization is term-specific. Leave Department as General to keep the class directly under its academic level."
          >
            <form className="space-y-3" onSubmit={saveClassSpecialization}>
              <SelectControl
                label="Academic level"
                value={levelId}
                onChange={setLevelId}
                options={eligibleLevels.map((row) => ({ value: row.id, label: row.name }))}
                required
              />
              <SelectControl
                label="Class"
                value={classId}
                onChange={setClassId}
                options={levelClasses.map((row) => ({
                  value: row.id,
                  label: classLabel(row),
                }))}
                placeholder={levelClasses.length ? "Select class" : "No classes in this level"}
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
                label="Department"
                value={departmentId}
                onChange={setDepartmentId}
                options={[
                  { value: "", label: "General — no department for this term" },
                  ...departments.map((row) => ({ value: row.id, label: row.name })),
                ]}
              />
              <Button
                type="submit"
                disabled={saving === "placement" || !classId || !termId}
              >
                {saving === "placement" ? "Saving…" : "Save term placement"}
              </Button>
            </form>
          </WorkspacePanel>
        )}
        content={(
          <WorkspacePanel
            title="Current term placement"
            description="Changing this setting never progresses a student or changes the class identity. Closed and result-bearing terms are protected from rewrites."
          >
            {!classId || !termId ? (
              <p className="text-sm text-text-muted">Select a class and term to inspect its placement.</p>
            ) : (
              <div className="rounded-xl border border-border/70 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  {classLabel(levelClasses.find((row) => row.id === classId))}
                </p>
                <p className="mt-1 text-lg font-semibold text-text">
                  {currentDepartment?.name || "General level placement"}
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  {currentDepartment
                    ? "This class receives general level subjects plus offerings for this department."
                    : "This class receives only general level offerings for the selected term."}
                </p>
              </div>
            )}
          </WorkspacePanel>
        )}
      />
    </div>
  );
}
