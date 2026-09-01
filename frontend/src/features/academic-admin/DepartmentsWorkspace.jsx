import { Building2, Link2, School } from "lucide-react";
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
  const [levelDepartments, setLevelDepartments] = useState([]);
  const [levelId, setLevelId] = useState("");

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [name, setName] = useState("");
  const [attachDepartmentId, setAttachDepartmentId] = useState("");

  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [academicLevelDepartmentId, setAcademicLevelDepartmentId] = useState("");
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

  const levelClasses = useMemo(
    () => classes.filter((row) => row.academic_level_id === levelId),
    [classes, levelId],
  );

  const loadLevelDepartments = useCallback(async () => {
    if (!levelId) {
      setLevelDepartments([]);
      return;
    }
    try {
      setLevelDepartments(
        items(
          await departmentService.getLevelDepartments(levelId, {
            includeArchived: true,
          }),
        ),
      );
    } catch (error) {
      showError(getErrorMessage(error, "Could not load level department availability."));
    }
  }, [levelId, showError]);

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
    const { scope, item, action } = pendingAction;
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
          await departmentService.activateLevelDepartment(levelId, item.id);
        if (action === "deactivate")
          await departmentService.deactivateLevelDepartment(levelId, item.id);
        if (action === "archive")
          await departmentService.archiveLevelDepartment(levelId, item.id);
        if (action === "restore")
          await departmentService.restoreLevelDepartment(levelId, item.id);
        if (action === "delete")
          await departmentService.deleteLevelDepartment(levelId, item.id);
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
    if (!classId || !termId) return;
    setSaving("placement");
    try {
      if (academicLevelDepartmentId) {
        const assignment = await curriculumService.setClassDepartment(
          classId,
          termId,
          academicLevelDepartmentId,
        );
        setCurrentAssignment(assignment);
        showSuccess("Class specialization set for this term.");
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

  const lifecycleButtons = (row, scope) => {
    const state = lifecycleStatus(row);
    return (
      <>
        {state === "active" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => setPendingAction({ scope, item: row, action: "deactivate" })}
          >
            Deactivate
          </Button>
        ) : null}
        {state === "inactive" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => setPendingAction({ scope, item: row, action: "activate" })}
          >
            Activate
          </Button>
        ) : null}
        {state === "inactive" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => setPendingAction({ scope, item: row, action: "archive" })}
          >
            Archive
          </Button>
        ) : null}
        {state === "archived" ? (
          <Button
            size="small"
            variant="outline"
            onClick={() => setPendingAction({ scope, item: row, action: "restore" })}
          >
            Restore
          </Button>
        ) : null}
        {["inactive", "archived"].includes(state) ? (
          <Button
            size="small"
            variant="danger"
            onClick={() => setPendingAction({ scope, item: row, action: "delete" })}
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
            description="A canonical department can be available in many academic levels without being duplicated."
            actions={
              <SelectControl
                label="Academic level"
                value={levelId}
                onChange={setLevelId}
                options={eligibleLevels.map((row) => ({ value: row.id, label: row.name }))}
              />
            }
            items={levelDepartments}
            emptyIcon={Link2}
            emptyTitle="No departments available"
            emptyDescription="Attach an active department from the school-wide pool."
            renderTitle={(row) => row.department_name || "Department"}
            renderMeta={() => eligibleLevels.find((row) => row.id === levelId)?.name || "Academic level"}
            renderDescription={() =>
              "This mapping is the specialization identity used by term placements and scoped offerings."
            }
            renderStatus={lifecycleStatus}
            renderActions={(row) => lifecycleButtons(row, "level")}
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
                {currentName || "General level placement"}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                {currentName
                  ? "This class receives general subjects plus offerings for this specialization."
                  : "This class receives general level offerings for the selected term."}
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
            : "This changes availability only for the selected academic level. Live term placements and offerings remain protected by backend dependency checks."
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
