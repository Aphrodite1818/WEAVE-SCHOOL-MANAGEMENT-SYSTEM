import { Building2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

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
  RecordList,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const items = (value) => (Array.isArray(value) ? value : value?.items || []);
const classLabel = (row) =>
  row?.display_name ||
  [row?.academic_level_name, row?.arm_label].filter(Boolean).join(" ") ||
  "Class";
const termName = (value) =>
  String(value || "Term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
const lifecycleStatus = (row) =>
  row.archived_at ? "archived" : row.is_active ? "active" : "inactive";
const normalizedDepartmentName = (value) =>
  String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLocaleLowerCase();
const editDistance = (left, right) => {
  const a = normalizedDepartmentName(left);
  const b = normalizedDepartmentName(right);
  const previous = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i += 1) {
    const current = [i];
    for (let j = 1; j <= b.length; j += 1) {
      current[j] = Math.min(
        current[j - 1] + 1,
        previous[j] + 1,
        previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
    previous.splice(0, previous.length, ...current);
  }
  return previous[b.length];
};

export default function DepartmentsWorkspace({ activeTab = "overview" }) {
  const { showError, showSuccess } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [levels, setLevels] = useState([]);
  const [categories, setCategories] = useState([]);
  const [classes, setClasses] = useState([]);
  const [terms, setTerms] = useState([]);
  const [levelId, setLevelId] = useState("");
  const [departments, setDepartments] = useState([]);
  const [name, setName] = useState("");
  const [editing, setEditing] = useState(null);
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [currentAssignment, setCurrentAssignment] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
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
      setTermId(
        (current) =>
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
  const visibleDepartments = useMemo(
    () =>
      ["active", "inactive", "archived"].includes(activeTab)
        ? departments.filter((row) => lifecycleStatus(row) === activeTab)
        : departments,
    [activeTab, departments],
  );
  const exactDuplicate = useMemo(() => {
    const candidate = normalizedDepartmentName(name);
    if (!candidate) return null;
    return (
      departments.find(
        (row) =>
          row.id !== editing?.id && normalizedDepartmentName(row.name) === candidate,
      ) || null
    );
  }, [departments, editing?.id, name]);
  const similarDepartment = useMemo(() => {
    if (exactDuplicate || normalizedDepartmentName(name).length < 5) return null;
    return (
      departments.find(
        (row) =>
          row.id !== editing?.id &&
          normalizedDepartmentName(row.name).length >= 5 &&
          editDistance(row.name, name) <= 2,
      ) || null
    );
  }, [departments, editing?.id, exactDuplicate, name]);

  const loadDepartments = useCallback(async () => {
    if (!levelId) {
      setDepartments([]);
      return;
    }
    try {
      setDepartments(
        items(await departmentService.getDepartments(levelId, { includeArchived: true })),
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

  const selectView = (view) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", view);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  const closeEditor = () => {
    setEditing(null);
    setName("");
    selectView("overview");
  };

  const saveDepartment = async (event) => {
    event.preventDefault();
    if (!name.trim() || !levelId) return;
    if (exactDuplicate) {
      showError(`${exactDuplicate.name} already exists in this academic level.`);
      return;
    }
    setSaving("department");
    try {
      if (editing) {
        await departmentService.updateDepartment(levelId, editing.id, { name: name.trim() });
      } else {
        await departmentService.createDepartment(levelId, { name: name.trim() });
      }
      showSuccess(editing ? "Department updated." : "Department created.");
      closeEditor();
      await loadDepartments();
    } catch (error) {
      showError(getErrorMessage(error, "Could not save department."));
    } finally {
      setSaving("");
    }
  };

  const runLifecycle = async () => {
    if (!pendingAction) return;
    const { item, action } = pendingAction;
    setSaving(item.id);
    try {
      if (action === "activate") await departmentService.activateDepartment(levelId, item.id);
      if (action === "deactivate") await departmentService.deactivateDepartment(levelId, item.id);
      if (action === "archive") await departmentService.archiveDepartment(levelId, item.id);
      if (action === "restore") await departmentService.restoreDepartment(levelId, item.id);
      if (action === "delete") await departmentService.deleteDepartment(levelId, item.id);
      showSuccess(
        action === "delete" ? "Department permanently deleted." : `Department ${action}d.`,
      );
      setPendingAction(null);
      await loadDepartments();
    } catch (error) {
      showError(getErrorMessage(error, `Could not ${action} this department.`));
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
  const selectedLevel = eligibleLevels.find((row) => row.id === levelId);
  const actionConfig = pendingAction
    ? {
        activate: ["Activate department", "ACTIVATE_DEPARTMENT", "Activate"],
        deactivate: ["Deactivate department", "DEACTIVATE_DEPARTMENT", "Deactivate"],
        archive: ["Archive department", "ARCHIVE_DEPARTMENT", "Archive"],
        restore: ["Restore department", "RESTORE_DEPARTMENT", "Restore"],
        delete: ["Permanently delete department", "DELETE_DEPARTMENT", "Delete permanently"],
      }[pendingAction.action]
    : null;
  const showEditor = activeTab === "create" || Boolean(editing);

  if (activeTab === "placements") {
    return (
      <WorkspaceGrid
        content={
          <WorkspacePanel
            title="Current term placement"
            description="A class belongs to its level permanently; department specialization is assigned per term."
          >
            {!classId || !termId ? (
              <p className="text-sm text-text-muted">
                Select a class and term to inspect its placement.
              </p>
            ) : (
              <div className="rounded-lg border border-border/70 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  {classLabel(levelClasses.find((row) => row.id === classId))}
                </p>
                <p className="mt-1 text-lg font-semibold text-text">
                  {currentDepartment?.name || "General level placement"}
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  {currentDepartment
                    ? "This class receives general subjects plus offerings for this department."
                    : "This class receives general level offerings for the selected term."}
                </p>
              </div>
            )}
          </WorkspacePanel>
        }
        editor={
          <WorkspacePanel
            title="Set class specialization"
            description="Closed and result-bearing academic periods remain protected by backend lifecycle guards."
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
                options={levelClasses.map((row) => ({ value: row.id, label: classLabel(row) }))}
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
                  ...departments
                    .filter((row) => lifecycleStatus(row) === "active")
                    .map((row) => ({ value: row.id, label: row.name })),
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
        }
      />
    );
  }

  return (
    <>
      <WorkspaceGrid
        editor={
          showEditor ? (
            <WorkspacePanel
              title={editing ? "Edit department" : "Add department"}
              description={`Department definitions are scoped to ${selectedLevel?.name || "the selected academic level"}.`}
            >
              <form className="space-y-3" onSubmit={saveDepartment}>
                <SelectControl
                  label="Academic level"
                  value={levelId}
                  onChange={setLevelId}
                  options={eligibleLevels.map((row) => ({
                    value: row.id,
                    label: row.name,
                  }))}
                  placeholder={
                    eligibleLevels.length
                      ? "Select department-enabled level"
                      : "No department-enabled levels"
                  }
                  disabled={Boolean(editing)}
                  required
                />
                {editing ? (
                  <p className="text-xs leading-5 text-text-muted">
                    A department belongs permanently to one academic level. Create a new
                    department instead of moving this definition to another level.
                  </p>
                ) : null}
                <Input
                  label="Department name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Science"
                  required
                />
                {exactDuplicate ? (
                  <p className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
                    {exactDuplicate.name} already exists in this academic level. Use the
                    existing department instead of creating a duplicate.
                  </p>
                ) : similarDepartment ? (
                  <p className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm text-text-muted">
                    Check the spelling: this looks very similar to {similarDepartment.name}.
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="submit"
                    disabled={
                      saving === "department" ||
                      !levelId ||
                      !name.trim() ||
                      Boolean(exactDuplicate)
                    }
                  >
                    {saving === "department"
                      ? "Saving…"
                      : editing
                        ? "Save department"
                        : "Add department"}
                  </Button>
                  <Button type="button" variant="outline" onClick={closeEditor}>
                    Cancel
                  </Button>
                </div>
              </form>
            </WorkspacePanel>
          ) : null
        }
        content={
          activeTab === "create" && !editing ? null : (
            <RecordList
              title="Departments"
              description="Specializations are defined per academic level and used by term-specific class placements and curriculum offerings."
              actions={
                <div className="flex min-w-[17rem] flex-col gap-2 sm:flex-row sm:items-end">
                  <div className="min-w-0 flex-1">
                    <SelectControl
                      label="Academic level"
                      value={levelId}
                      onChange={setLevelId}
                      options={eligibleLevels.map((row) => ({
                        value: row.id,
                        label: row.name,
                      }))}
                      placeholder="Select level"
                    />
                  </div>
                  {!showEditor ? (
                    <Button
                      type="button"
                      disabled={!levelId}
                      onClick={() => selectView("create")}
                    >
                      Add department
                    </Button>
                  ) : null}
                </div>
              }
              items={visibleDepartments}
              emptyIcon={Building2}
              emptyTitle={
                eligibleLevels.length ? "No departments" : "No department-enabled levels"
              }
              emptyDescription={
                eligibleLevels.length
                  ? "Add the first department for this academic level."
                  : "Activate an academic level whose category supports departments first."
              }
              renderTitle={(row) => row.name}
              renderMeta={() => selectedLevel?.name || "Academic level"}
              renderDescription={() =>
                "Available for term-specific class placement and department-scoped curriculum offerings."
              }
              renderStatus={lifecycleStatus}
              showInspector={!showEditor}
              onEdit={(row) => {
                setEditing(row);
                setName(row.name);
              }}
              canEdit={(row) => !row.archived_at}
              renderActions={(row) => {
                const status = lifecycleStatus(row);
                return (
                  <>
                    {status === "active" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item: row, action: "deactivate" })}
                      >
                        Deactivate
                      </Button>
                    ) : null}
                    {status === "inactive" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item: row, action: "activate" })}
                      >
                        Activate
                      </Button>
                    ) : null}
                    {status === "inactive" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item: row, action: "archive" })}
                      >
                        Archive
                      </Button>
                    ) : null}
                    {status === "archived" ? (
                      <Button
                        size="small"
                        variant="outline"
                        onClick={() => setPendingAction({ item: row, action: "restore" })}
                      >
                        Restore
                      </Button>
                    ) : null}
                    {["inactive", "archived"].includes(status) ? (
                      <Button
                        size="small"
                        variant="danger"
                        onClick={() => setPendingAction({ item: row, action: "delete" })}
                      >
                        Delete permanently
                      </Button>
                    ) : null}
                  </>
                );
              }}
            />
          )
        }
      />
      <TypedConfirmationDialog
        open={Boolean(pendingAction)}
        title={actionConfig?.[0]}
        description={
          pendingAction?.action === "delete"
            ? `${pendingAction?.item?.name || "This department"} will be permanently removed only if it has never been used by a class placement or curriculum offering. Used departments are rejected by the backend and retained as academic history.`
            : `${pendingAction?.item?.name || "This department"} will move through the supported department lifecycle. Live class placements and offerings remain protected by backend dependency checks.`
        }
        confirmationText={actionConfig?.[1] || ""}
        confirmLabel={actionConfig?.[2]}
        variant={["deactivate", "archive", "delete"].includes(pendingAction?.action) ? "danger" : "primary"}
        isLoading={saving === pendingAction?.item?.id}
        onConfirm={runLifecycle}
        onCancel={() => setPendingAction(null)}
      />
    </>
  );
}
