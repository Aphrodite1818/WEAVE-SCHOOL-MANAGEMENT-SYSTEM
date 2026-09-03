import { Building2, Link2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicLevelService, classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { curriculumService } from "../../services/curriculumService";
import { departmentService } from "../../services/departmentService";
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
const termPosition = (value) =>
  ({ first_term: 1, second_term: 2, third_term: 3 })[
    String(value || "").toLowerCase()
  ] || 0;
const lifecycleStatus = (row) =>
  row.archived_at ? "archived" : row.is_active ? "active" : "inactive";
const normalizeName = (value) =>
  String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLocaleLowerCase();

export default function DepartmentsWorkspace({ activeTab = "pool" }) {
  const { showError, showSuccess } = useToast();
  const [levels, setLevels] = useState([]);
  const [categories, setCategories] = useState([]);
  const [classes, setClasses] = useState([]);
  const [terms, setTerms] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [levelDepartmentsByLevel, setLevelDepartmentsByLevel] = useState({});
  const [levelId, setLevelId] = useState("");

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [name, setName] = useState("");
  const [attachDepartmentId, setAttachDepartmentId] = useState("");

  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [academicLevelDepartmentId, setAcademicLevelDepartmentId] = useState("");
  const [sourceTermId, setSourceTermId] = useState("");
  const [currentAssignment, setCurrentAssignment] = useState(null);

  const [pendingAction, setPendingAction] = useState(null);
  const [saving, setSaving] = useState("");

  const loadPool = useCallback(async () => {
    try {
      setDepartments(
        items(await departmentService.getDepartments({ includeArchived: true })),
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load the department pool."));
    }
  }, [showError]);

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
  }, [categories, levels]);

  const levelDepartments = useMemo(
    () => (levelId ? levelDepartmentsByLevel[String(levelId)] || [] : []),
    [levelDepartmentsByLevel, levelId],
  );

  const levelClasses = useMemo(
    () => classes.filter((row) => row.academic_level_id === levelId),
    [classes, levelId],
  );

  const loadLevelDepartments = useCallback(async () => {
    if (!eligibleLevels.length) {
      setLevelDepartmentsByLevel({});
      return;
    }

    try {
      const entries = await Promise.all(
        eligibleLevels.map(async (level) => [
          String(level.id),
          items(
            await departmentService.getLevelDepartments(level.id, {
              includeArchived: true,
            }),
          ),
        ]),
      );
      setLevelDepartmentsByLevel(Object.fromEntries(entries));
    } catch (error) {
      showError(getErrorMessage(error, "Could not load level department availability."));
    }
  }, [eligibleLevels, showError]);

  const loadCurrentAssignment = useCallback(async () => {
    if (!classId || !termId) {
      setCurrentAssignment(null);
      setAcademicLevelDepartmentId("");
      return;
    }
    try {
      const assignment = await curriculumService.getClassDepartment(classId, termId);
      setCurrentAssignment(assignment || null);
      setAcademicLevelDepartmentId(assignment?.academic_level_department_id || "");
    } catch (error) {
      setCurrentAssignment(null);
      setAcademicLevelDepartmentId("");
      showError(getErrorMessage(error, "Could not load this class specialization."));
    }
  }, [classId, termId, showError]);

  useEffect(() => {
    loadBase();
    loadPool();
  }, [loadBase, loadPool]);

  useEffect(() => {
    if (!eligibleLevels.some((row) => row.id === levelId)) {
      setLevelId(eligibleLevels[0]?.id || "");
    }
  }, [eligibleLevels, levelId]);

  useEffect(() => {
    loadLevelDepartments();
  }, [loadLevelDepartments]);

  useEffect(() => {
    if (!levelClasses.some((row) => row.id === classId)) {
      setClassId(levelClasses[0]?.id || "");
    }
  }, [classId, levelClasses]);

  useEffect(() => {
    loadCurrentAssignment();
  }, [loadCurrentAssignment]);

  useEffect(() => {
    setEditorOpen(false);
    setEditing(null);
    setName("");
    setAttachDepartmentId("");
  }, [activeTab]);

  const exactDuplicate = useMemo(() => {
    const candidate = normalizeName(name);
    if (!candidate) return null;
    return (
      departments.find(
        (row) => row.id !== editing?.id && normalizeName(row.name) === candidate,
      ) || null
    );
  }, [departments, editing?.id, name]);

  const attachedCanonicalIds = useMemo(
    () => new Set(levelDepartments.map((row) => row.department_id)),
    [levelDepartments],
  );
  const attachableDepartments = useMemo(
    () =>
      departments.filter(
        (row) =>
          lifecycleStatus(row) === "active" && !attachedCanonicalIds.has(row.id),
      ),
    [attachedCanonicalIds, departments],
  );
  const activeLevelDepartments = useMemo(
    () => levelDepartments.filter((row) => lifecycleStatus(row) === "active"),
    [levelDepartments],
  );
  const selectedLevel = levels.find((row) => row.id === levelId) || null;
  const selectedTerm = terms.find((row) => row.id === termId) || null;
  const specializationActive = Boolean(
    selectedLevel?.specialization_required_from_term_position != null &&
      termPosition(selectedTerm?.name) >=
        Number(selectedLevel.specialization_required_from_term_position),
  );
  const previousTerms = useMemo(
    () =>
      terms.filter(
        (row) =>
          row.id !== termId &&
          row.academic_session_id === selectedTerm?.academic_session_id &&
          termPosition(row.name) < termPosition(selectedTerm?.name),
      ),
    [selectedTerm?.academic_session_id, selectedTerm?.name, termId, terms],
  );

  useEffect(() => {
    const nearest = [...previousTerms].sort(
      (left, right) => termPosition(right.name) - termPosition(left.name),
    )[0];
    setSourceTermId(nearest?.id || "");
  }, [previousTerms]);

  const saveDepartment = async (event) => {
    event.preventDefault();
    if (!name.trim() || exactDuplicate) return;
    setSaving("department");
    try {
      if (editing) {
        await departmentService.updateDepartment(editing.id, { name: name.trim() });
        showSuccess("Department updated across its level mappings.");
      } else {
        await departmentService.createDepartment({ name: name.trim() });
        showSuccess("Department added to the school-wide pool.");
      }
      setEditing(null);
      setName("");
      setEditorOpen(false);
      await loadPool();
      await loadLevelDepartments();
    } catch (error) {
      showError(getErrorMessage(error, "Could not save department."));
    } finally {
      setSaving("");
    }
  };

  const attachToLevel = async (event) => {
    event.preventDefault();
    if (!levelId || !attachDepartmentId) return;
    setSaving("attach");
    try {
      await departmentService.attachDepartment(levelId, attachDepartmentId);
      setAttachDepartmentId("");
      await loadLevelDepartments();
      showSuccess("Department made available to this academic level.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not attach department to this level."));
    } finally {
      setSaving("");
    }
  };

  const runLifecycle = async () => {
    if (!pendingAction) return;
    const { scope, item, action, academicLevelId } = pendingAction;
    setSaving(item.id);
    try {
      if (scope === "pool") {
        if (action === "activate") await departmentService.activateDepartment(item.id);
        if (action === "deactivate") await departmentService.deactivateDepartment(item.id);
        if (action === "archive") await departmentService.archiveDepartment(item.id);
        if (action === "restore") await departmentService.restoreDepartment(item.id);
        if (action === "delete") await departmentService.deleteDepartment(item.id);
        await loadPool();
        await loadLevelDepartments();
      } else {
        if (action === "activate")
          await departmentService.activateLevelDepartment(academicLevelId, item.id);
        if (action === "deactivate")
          await departmentService.deactivateLevelDepartment(academicLevelId, item.id);
        if (action === "archive")
          await departmentService.archiveLevelDepartment(academicLevelId, item.id);
        if (action === "restore")
          await departmentService.restoreLevelDepartment(academicLevelId, item.id);
        if (action === "delete")
          await departmentService.deleteLevelDepartment(academicLevelId, item.id);
        await loadLevelDepartments();
      }
      showSuccess(action === "delete" ? "Record permanently deleted." : `Department ${action}d.`);
      setPendingAction(null);
    } catch (error) {
      showError(getErrorMessage(error, `Could not ${action} this department.`));
    } finally {
      setSaving("");
    }
  };

  const saveClassSpecialization = async (event) => {
    event.preventDefault();
    if (!classId || !termId || !specializationActive || !academicLevelDepartmentId)
      return;
    setSaving("placement");
    try {
      const assignment = await curriculumService.setClassDepartment(
        classId,
        termId,
        academicLevelDepartmentId,
      );
      setCurrentAssignment(assignment);
      showSuccess("Class specialization set for this term.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not update class specialization."));
      await loadCurrentAssignment();
    } finally {
      setSaving("");
    }
  };

  const copyPreviousSpecializations = async () => {
    if (!termId || !sourceTermId) return;
    setSaving("copy");
    try {
      const result = await curriculumService.copyClassDepartments(
        termId,
        sourceTermId,
      );
      await loadCurrentAssignment();
      const copied = Number(result?.copied || 0);
      showSuccess(
        `${copied} class specialization${copied === 1 ? "" : "s"} copied.`,
      );
    } catch (error) {
      showError(
        getErrorMessage(error, "Could not copy previous term specializations."),
      );
    } finally {
      setSaving("");
    }
  };

  const poolActionConfig = {
    activate: ["Activate department", "ACTIVATE_DEPARTMENT", "Activate"],
    deactivate: ["Deactivate department", "DEACTIVATE_DEPARTMENT", "Deactivate"],
    archive: ["Archive department", "ARCHIVE_DEPARTMENT", "Archive"],
    restore: ["Restore department", "RESTORE_DEPARTMENT", "Restore"],
    delete: ["Permanently delete department", "DELETE_DEPARTMENT", "Delete permanently"],
  };
  const levelActionConfig = {
    activate: ["Activate level availability", "ACTIVATE_LEVEL_DEPARTMENT", "Activate"],
    deactivate: ["Deactivate level availability", "DEACTIVATE_LEVEL_DEPARTMENT", "Deactivate"],
    archive: ["Archive level availability", "ARCHIVE_LEVEL_DEPARTMENT", "Archive"],
    restore: ["Restore level availability", "RESTORE_LEVEL_DEPARTMENT", "Restore"],
    delete: ["Remove level availability", "DELETE_LEVEL_DEPARTMENT", "Delete permanently"],
  };
  const actionConfig = pendingAction
    ? (pendingAction.scope === "pool" ? poolActionConfig : levelActionConfig)[
        pendingAction.action
      ]
    : null;

  const lifecycleButtons = (row, scope, academicLevelId = null) => {
    const state = lifecycleStatus(row);
    const queueAction = (action) =>
      setPendingAction({ scope, item: row, action, academicLevelId });

    return (
      <>
        {state === "active" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => queueAction("deactivate")}
          >
            Deactivate
          </Button>
        ) : null}
        {state === "inactive" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => queueAction("activate")}
          >
            Activate
          </Button>
        ) : null}
        {state === "inactive" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => queueAction("archive")}
          >
            Archive
          </Button>
        ) : null}
        {state === "archived" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => queueAction("restore")}
          >
            Restore
          </Button>
        ) : null}
        {["inactive", "archived"].includes(state) ? (
          <Button
            size="small"
            variant="danger"
            onClick={() => queueAction("delete")}
          >
            Delete permanently
          </Button>
        ) : null}
      </>
    );
  };

  if (activeTab === "availability") {
    return (
      <WorkspaceGrid
        editor={
          <WorkspacePanel
            title="Make a department available"
            description="Choose from the school-wide pool. This creates the level-specific specialization identity used by curriculum and class placement."
          >
            <form className="space-y-3" onSubmit={attachToLevel}>
              <SelectControl
                label="Academic level"
                value={levelId}
                onChange={setLevelId}
                options={eligibleLevels.map((row) => ({ value: row.id, label: row.name }))}
                required
              />
              <SelectControl
                label="Department"
                value={attachDepartmentId}
                onChange={setAttachDepartmentId}
                options={attachableDepartments.map((row) => ({
                  value: row.id,
                  label: row.name,
                }))}
                placeholder={
                  attachableDepartments.length
                    ? "Select department from pool"
                    : "All active departments are already attached"
                }
                required
              />
              <Button
                type="submit"
                disabled={saving === "attach" || !levelId || !attachDepartmentId}
              >
                {saving === "attach" ? "Saving…" : "Make available"}
              </Button>
            </form>
          </WorkspacePanel>
        }
        content={
          <RecordList
            title="Level availability"
            description="Each department-enabled academic level shows its department mappings directly."
            items={eligibleLevels}
            emptyIcon={Link2}
            emptyTitle="No department-enabled levels"
            emptyDescription="Configure a department-enabled academic category before assigning departments."
            renderTitle={(row) => row.name}
            renderMeta={(row) => {
              const mappings = levelDepartmentsByLevel[String(row.id)] || [];
              return `${mappings.length} department${mappings.length === 1 ? "" : "s"} assigned`;
            }}
            renderDescription={(row) => {
              const mappings = levelDepartmentsByLevel[String(row.id)] || [];
              if (!mappings.length) return "No departments assigned to this academic level.";
              return mappings
                .map((mapping) => {
                  const status = lifecycleStatus(mapping);
                  const label = mapping.department_name || "Department";
                  return status === "active" ? label : `${label} (${status})`;
                })
                .join(" · ");
            }}
            renderActions={(row) => {
              const mappings = levelDepartmentsByLevel[String(row.id)] || [];
              if (!mappings.length) return null;
              return (
                <div className="grid gap-2">
                  {mappings.map((mapping) => (
                    <div
                      key={mapping.id}
                      className="flex flex-wrap items-center justify-end gap-2"
                    >
                      <span className="text-xs font-semibold text-text-muted">
                        {mapping.department_name || "Department"}
                      </span>
                      {lifecycleButtons(mapping, "level", row.id)}
                    </div>
                  ))}
                </div>
              );
            }}
            showInspector={false}
          />
        }
      />
    );
  }

  if (activeTab === "placements") {
    const currentName =
      currentAssignment?.department_name ||
      levelDepartments.find((row) => row.id === currentAssignment?.academic_level_department_id)
        ?.department_name;
    return (
      <WorkspaceGrid
        content={
          <WorkspacePanel
            title="Current term placement"
            description="A class belongs permanently to its level; specialization is selected per term from that level's active department mappings."
          >
            <div className="rounded-lg border border-border/70 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                {classLabel(levelClasses.find((row) => row.id === classId))}
              </p>
              <p className="mt-1 text-lg font-semibold text-text">
                {currentName ||
                  (specializationActive
                    ? "Not assigned"
                    : "Specialization not active")}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                {currentName
                  ? "This class receives general subjects plus subjects for this specialization."
                  : specializationActive
                    ? "Choose an exact department for this class and term."
                    : "Before specialization begins, every active curriculum subject is eligible."}
              </p>
            </div>
          </WorkspacePanel>
        }
        editor={
          <WorkspacePanel
            title="Set class specialization"
            description="Only active departments available to the selected level can be assigned."
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
              {specializationActive ? (
                <>
              <SelectControl
                label="Department"
                value={academicLevelDepartmentId}
                onChange={setAcademicLevelDepartmentId}
                options={[
                  { value: "", label: "General — no department for this term" },
                  ...activeLevelDepartments.map((row) => ({
                    value: row.id,
                    label: row.department_name || "Department",
                  })),
                ].filter((option) => option.value)}
              />
              <Button
                type="submit"
                disabled={
                  saving === "placement" ||
                  !classId ||
                  !termId ||
                  !academicLevelDepartmentId
                }
              >
                {saving === "placement" ? "Saving…" : "Save term placement"}
              </Button>
                  {previousTerms.length ? (
                    <div className="space-y-2 border-t border-border/70 pt-3">
                      <SelectControl
                        label="Copy from term"
                        value={sourceTermId}
                        onChange={setSourceTermId}
                        options={previousTerms.map((row) => ({
                          value: row.id,
                          label: termName(row.name),
                        }))}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        disabled={saving === "copy" || !sourceTermId}
                        onClick={copyPreviousSpecializations}
                      >
                        {saving === "copy"
                          ? "Copying..."
                          : "Copy previous term specializations"}
                      </Button>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="rounded-lg border border-border/70 px-3 py-3 text-sm text-text-muted">
                  Specialization is not active for this level in the selected
                  term, so no department assignment is required.
                </p>
              )}
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
          editorOpen ? (
            <WorkspacePanel
              title={editing ? "Edit department" : "Add department to pool"}
              description="Department names are school-wide. Level availability is configured separately."
            >
              <form className="space-y-3" onSubmit={saveDepartment}>
                <Input
                  label="Department name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Science"
                  required
                />
                {exactDuplicate ? (
                  <p className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
                    {exactDuplicate.name} already exists in the department pool.
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="submit"
                    disabled={saving === "department" || !name.trim() || Boolean(exactDuplicate)}
                  >
                    {saving === "department"
                      ? "Saving…"
                      : editing
                        ? "Save department"
                        : "Add department"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setEditorOpen(false);
                      setEditing(null);
                      setName("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            </WorkspacePanel>
          ) : null
        }
        content={
          <RecordList
            title="Department pool"
            description="Create each specialization once for the school, then make it available to the academic levels that use it."
            actions={
              !editorOpen ? (
                <Button
                  type="button"
                  onClick={() => {
                    setEditing(null);
                    setName("");
                    setEditorOpen(true);
                  }}
                >
                  Add department
                </Button>
              ) : null
            }
            items={departments}
            emptyIcon={Building2}
            emptyTitle="No departments"
            emptyDescription="Create the first school-wide department definition."
            renderTitle={(row) => row.name}
            renderMeta={() => "School-wide department"}
            renderDescription={() =>
              "Reuse this definition across any department-enabled academic level."
            }
            renderStatus={lifecycleStatus}
            showInspector={!editorOpen}
            onEdit={(row) => {
              setEditing(row);
              setName(row.name);
              setEditorOpen(true);
            }}
            canEdit={(row) => !row.archived_at}
            renderActions={(row) => lifecycleButtons(row, "pool")}
          />
        }
      />
      <TypedConfirmationDialog
        open={Boolean(pendingAction)}
        title={actionConfig?.[0]}
        description={
          pendingAction?.scope === "pool"
            ? "Canonical department lifecycle changes apply everywhere this department is mapped. Active level mappings and historical usage remain protected by backend dependency checks."
            : "This changes availability only for this academic level. Term placements and curriculum applicability remain protected by backend dependency checks."
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
