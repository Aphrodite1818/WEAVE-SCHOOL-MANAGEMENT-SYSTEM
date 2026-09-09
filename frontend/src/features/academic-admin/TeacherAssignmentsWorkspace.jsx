import { beginAcademicSubmission, endAcademicSubmission } from "./academicSubmission";
import { ArrowLeft, UserPlus, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { curriculumService } from "../../services/curriculumService";
import { teacherService } from "../../services/teacherService";
import {
  Input,
  RecordList,
  SelectControl,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const PAGE_SIZE = 25;
const DELETE_TEACHER_ASSIGNMENT = "DELETE_TEACHER_ASSIGNMENT";
const today = () => new Date().toISOString().slice(0, 10);

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const teacherLabel = (item) => {
  const account = item?.teacher_account || item?.account || {};
  return (
    [account.first_name, account.last_name].filter(Boolean).join(" ") ||
    item?.teacher_name ||
    account.email ||
    item?.staff_id ||
    item?.teacher_staff_id ||
    "Teacher"
  );
};

const assignmentClassLabel = (item) =>
  [item?.class_name, item?.class_arm].filter(Boolean).join(" ") || "Class";

const formatPeriod = (item) =>
  `${item?.effective_from || "Unknown start"} – ${item?.effective_to || "Present"}`;

const formatDependencyMessage = (preview) => {
  const counts = preview?.dependency_counts || {};
  const details = Object.entries(counts)
    .filter(([, value]) => Number(value || 0) > 0)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`)
    .join("; ");
  return [(preview?.blocker_messages || []).join(" "), details]
    .filter(Boolean)
    .join(" ");
};

function TeacherAssignmentsWorkspace({ activeTab }) {
  const { showSuccess, showError, showWarning } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [currentTerm, setCurrentTerm] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [assignmentTotal, setAssignmentTotal] = useState(0);
  const [assignmentPage, setAssignmentPage] = useState(0);
  const [filters, setFilters] = useState({
    academic_level_id: "",
    teacher_membership_id: "",
    status: "",
  });
  const [assignmentLevelId, setAssignmentLevelId] = useState("");
  const [curriculumSubjects, setCurriculumSubjects] = useState([]);
  const [eligibleClasses, setEligibleClasses] = useState([]);
  const [selectedClassIds, setSelectedClassIds] = useState([]);
  const [form, setForm] = useState({
    curriculum_subject_id: "",
    teacher_membership_id: "",
    effective_from: today(),
  });
  const [reassigning, setReassigning] = useState(null);
  const [ending, setEnding] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [reason, setReason] = useState("");
  const [effectiveTo, setEffectiveTo] = useState(today());
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const currentTermId = currentTerm?.id || "";

  const selectView = useCallback(
    (view) => {
      const next = new URLSearchParams(searchParams);
      next.set("view", view);
      next.delete("tab");
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const resetCreateForm = () => {
    setForm({
      curriculum_subject_id: "",
      teacher_membership_id: "",
      effective_from: today(),
    });
    setSelectedClassIds([]);
  };

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [classResponse, teacherResponse, termResponse] = await Promise.all([
        classService.getClasses({ limit: 500, activeOnly: true }),
        teacherService.listMemberships({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
      ]);
      const nextClasses = asItems(classResponse);
      const nextTerms = asItems(termResponse);
      setClasses(nextClasses);
      setTeachers(
        asItems(teacherResponse).filter(
          (item) => String(item.status || "active").toLowerCase() === "active",
        ),
      );
      setCurrentTerm(
        nextTerms.find(
          (item) => item.is_current && String(item.status || "").toLowerCase() === "open",
        ) || null,
      );
      setAssignmentLevelId((current) =>
        current || nextClasses.find((item) => item.academic_level_id)?.academic_level_id || "",
      );
    } catch (requestError) {
      const message = getErrorMessage(requestError, "Could not load teacher assignments.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [showError]);

  const loadAssignments = useCallback(async () => {
    try {
      const response = await academicService.listTeacherAssignments({
        academic_level_id: filters.academic_level_id || undefined,
        teacher_membership_id: filters.teacher_membership_id || undefined,
        status: filters.status || undefined,
        skip: assignmentPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setAssignments(asItems(response));
      setAssignmentTotal(Number(response?.total || 0));
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not load teacher assignments."));
    }
  }, [assignmentPage, filters, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadAssignments();
  }, [loadAssignments]);

  useEffect(() => {
    if (!assignmentLevelId || !currentTermId || activeTab !== "assign") {
      setCurriculumSubjects([]);
      return;
    }
    curriculumService
      .getCurriculum(assignmentLevelId)
      .then((response) =>
        setCurriculumSubjects(
          (response?.subjects || [])
            .filter((item) => item.is_active !== false && !item.archived_at)
            .map((item) => ({ ...item, id: item.id || item.curriculum_subject_id })),
        ),
      )
      .catch((requestError) => {
        setCurriculumSubjects([]);
        showError(getErrorMessage(requestError, "Could not load curriculum subjects."));
      });
  }, [activeTab, assignmentLevelId, currentTermId, showError]);

  useEffect(() => {
    let cancelled = false;
    if (!form.curriculum_subject_id || !currentTermId || activeTab !== "assign") {
      setEligibleClasses([]);
      setSelectedClassIds([]);
      return undefined;
    }
    curriculumService
      .getEligibleClasses(form.curriculum_subject_id, currentTermId)
      .then((response) => {
        if (cancelled) return;
        const rows = asItems(response).filter(
          (item) => item.academic_level_id === assignmentLevelId,
        );
        setEligibleClasses(rows);
        setSelectedClassIds((current) => {
          const allowed = new Set(
            rows.filter((item) => !item.already_assigned).map((item) => item.class_id),
          );
          return current.filter((id) => allowed.has(id));
        });
      })
      .catch((requestError) => {
        if (cancelled) return;
        setEligibleClasses([]);
        setSelectedClassIds([]);
        showError(getErrorMessage(requestError, "Could not load eligible classes."));
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab, assignmentLevelId, currentTermId, form.curriculum_subject_id, showError]);

  const levelOptions = useMemo(() => {
    const rows = new Map();
    classes.forEach((item) => {
      if (item.academic_level_id && !rows.has(item.academic_level_id)) {
        rows.set(item.academic_level_id, {
          value: item.academic_level_id,
          label: item.academic_level_name || "Academic level",
        });
      }
    });
    return [...rows.values()];
  }, [classes]);

  const teacherOptions = useMemo(
    () => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })),
    [teachers],
  );
  const subjectOptions = useMemo(
    () =>
      curriculumSubjects.map((item) => ({
        value: item.id,
        label: [item.subject_name, item.subject_code, item.is_elective ? "Elective" : null]
          .filter(Boolean)
          .join(" · "),
      })),
    [curriculumSubjects],
  );

  const updateFilters = (patch) => {
    setAssignmentPage(0);
    setFilters((current) => ({ ...current, ...patch }));
  };

  const saveAssignment = async (event) => {
    event.preventDefault();
    if (!currentTermId || !assignmentLevelId || !form.curriculum_subject_id) {
      showWarning("Choose an academic level and subject in the current open term.");
      return;
    }
    if (!form.teacher_membership_id || selectedClassIds.length === 0) {
      showWarning("Choose a teacher and at least one eligible class.");
      return;
    }
    const submission = beginAcademicSubmission(event, Boolean(saving));
    if (!submission) return;
    setSaving("create");
    try {
      await curriculumService.createTeacherAssignmentsBulk({
        class_ids: selectedClassIds,
        curriculum_subject_id: form.curriculum_subject_id,
        academic_term_id: currentTermId,
        teacher_membership_id: form.teacher_membership_id,
        effective_from: form.effective_from,
      });
      showSuccess(
        `Teacher assigned to ${selectedClassIds.length} class${selectedClassIds.length === 1 ? "" : "es"}.`,
      );
      resetCreateForm();
      await loadAssignments();
      selectView("overview");
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not create teacher assignments."));
    } finally {
      endAcademicSubmission(submission);
      setSaving("");
    }
  };

  const submitReassign = async (event) => {
    event.preventDefault();
    if (!reassigning || !currentTermId || reason.trim().length < 3) {
      showWarning("Choose a replacement teacher and enter an audit reason.");
      return;
    }
    setSaving(reassigning.id);
    try {
      await academicService.reassignTeacherAssignment(reassigning.id, {
        academic_term_id: currentTermId,
        teacher_membership_id: form.teacher_membership_id,
        effective_from: form.effective_from,
        reason: reason.trim(),
      });
      showSuccess("Teacher assignment reassigned and history preserved.");
      setReassigning(null);
      setReason("");
      await loadAssignments();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not reassign teacher."));
    } finally {
      setSaving("");
    }
  };

  const submitEnd = async (event) => {
    event.preventDefault();
    if (!ending || !currentTermId || reason.trim().length < 3) return;
    setSaving(ending.id);
    try {
      const preview = await academicService.getTeacherAssignmentDependencies(ending.id);
      if (!preview?.can_end) {
        showError(formatDependencyMessage(preview) || "This assignment cannot be ended.");
        return;
      }
      await academicService.endTeacherAssignment(ending.id, {
        academic_term_id: currentTermId,
        reason: reason.trim(),
        effective_to: effectiveTo || null,
      });
      showSuccess("Assignment ended and retained in history.");
      setEnding(null);
      setReason("");
      await loadAssignments();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not end assignment."));
    } finally {
      setSaving("");
    }
  };

  const requestDelete = async (item) => {
    setReason("");
    try {
      const preview = await academicService.getTeacherAssignmentDependencies(item.id);
      if (!preview?.can_delete) {
        showError(formatDependencyMessage(preview) || "This historical assignment cannot be deleted.");
        return;
      }
      setPendingDelete({ item, preview });
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not inspect assignment dependencies."));
    }
  };

  const deleteAssignment = async () => {
    if (!pendingDelete?.item || reason.trim().length < 3) return;
    setSaving(pendingDelete.item.id);
    try {
      await academicService.deleteTeacherAssignment(pendingDelete.item.id, {
        reason: reason.trim(),
      });
      showSuccess("Unused historical assignment deleted.");
      setPendingDelete(null);
      setReason("");
      await loadAssignments();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not delete assignment."));
    } finally {
      setSaving("");
    }
  };

  const openReassign = (item) => {
    setReason("");
    setForm((current) => ({
      ...current,
      teacher_membership_id: item.teacher_membership_id || "",
      effective_from: today(),
    }));
    setReassigning(item);
  };

  const rowActions = (item) => {
    const status = String(item.status || "").toLowerCase();
    if (status === "current") {
      return (
        <>
          <Button type="button" size="small" variant="outline" disabled={saving === item.id} onClick={() => openReassign(item)}>
            Reassign
          </Button>
          <Button
            type="button"
            size="small"
            variant="danger"
            disabled={saving === item.id}
            onClick={() => {
              setReason("");
              setEffectiveTo(item.effective_from || today());
              setEnding(item);
            }}
          >
            End
          </Button>
        </>
      );
    }
    if (status === "ended") {
      return (
        <Button type="button" size="small" variant="outline" disabled={saving === item.id} onClick={() => requestDelete(item)}>
          Delete unused
        </Button>
      );
    }
    return null;
  };

  const editor = (
    <WorkspacePanel
      title="Assign subject teacher"
      description={
        currentTerm
          ? "Choose a level and subject, then select every eligible class that should receive this teacher assignment."
          : "Open an academic term before creating teacher assignments."
      }
      actions={
        <Button type="button" variant="outline" onClick={() => selectView("overview")}>
          <ArrowLeft className="h-4 w-4" /> Back to assignments
        </Button>
      }
    >
      <form className="space-y-4" onSubmit={saveAssignment}>
        <fieldset disabled={Boolean(saving)} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <SelectControl
              label="Academic level"
              value={assignmentLevelId}
              onChange={(value) => {
                setAssignmentLevelId(value);
                setForm((current) => ({ ...current, curriculum_subject_id: "" }));
                setSelectedClassIds([]);
              }}
              options={levelOptions}
              placeholder="Select academic level"
              disabled={!currentTerm}
              required
            />
            <SelectControl
              label="Subject"
              value={form.curriculum_subject_id}
              onChange={(value) => {
                setForm((current) => ({ ...current, curriculum_subject_id: value }));
                setSelectedClassIds([]);
              }}
              options={subjectOptions}
              placeholder={!assignmentLevelId ? "Select level first" : "Select subject"}
              disabled={!currentTerm || !assignmentLevelId}
              required
            />
            <SelectControl
              label="Teacher"
              value={form.teacher_membership_id}
              onChange={(value) => setForm((current) => ({ ...current, teacher_membership_id: value }))}
              options={teacherOptions}
              placeholder="Select teacher"
              required
            />
            <Input
              label="Effective from"
              type="date"
              value={form.effective_from}
              onChange={(event) => setForm((current) => ({ ...current, effective_from: event.target.value }))}
              required
            />
          </div>

          <div className="rounded-xl border border-border/70 bg-surface-muted/20 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-text">Eligible classes</p>
                <p className="text-xs text-text-muted">Already-covered classes remain unavailable.</p>
              </div>
              <Button
                type="button"
                size="small"
                variant="outline"
                disabled={!eligibleClasses.some((item) => !item.already_assigned)}
                onClick={() =>
                  setSelectedClassIds(
                    eligibleClasses.filter((item) => !item.already_assigned).map((item) => item.class_id),
                  )
                }
              >
                Select all eligible
              </Button>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {eligibleClasses.map((item) => (
                <label key={item.class_id} className="flex items-center gap-2 rounded-lg border border-border/70 bg-surface px-3 py-2 text-sm text-text-soft">
                  <input
                    type="checkbox"
                    checked={selectedClassIds.includes(item.class_id)}
                    disabled={item.already_assigned}
                    onChange={(event) =>
                      setSelectedClassIds((current) =>
                        event.target.checked
                          ? [...current, item.class_id]
                          : current.filter((id) => id !== item.class_id),
                      )
                    }
                  />
                  <span>
                    {item.display_name || item.class_name || "Class"}
                    {item.department_name ? ` · ${item.department_name}` : ""}
                    {item.already_assigned ? " · already assigned" : ""}
                  </span>
                </label>
              ))}
              {form.curriculum_subject_id && eligibleClasses.length === 0 ? (
                <p className="text-sm text-text-muted">No eligible classes for this subject and level.</p>
              ) : null}
            </div>
          </div>

          <Button type="submit" disabled={!currentTerm || !selectedClassIds.length || saving === "create"}>
            <UserPlus className="h-4 w-4" />
            {saving === "create"
              ? "Assigning..."
              : `Create ${selectedClassIds.length || ""} assignment${selectedClassIds.length === 1 ? "" : "s"}`}
          </Button>
        </fieldset>
      </form>
    </WorkspacePanel>
  );

  if (error && !loading) {
    return (
      <WorkspacePanel title="Teacher assignments unavailable">
        <p className="text-sm text-error">{error}</p>
        <Button type="button" className="mt-4" onClick={loadBase}>Retry</Button>
      </WorkspacePanel>
    );
  }

  if (activeTab === "assign") return editor;

  return (
    <>
      <div className="mb-4 grid gap-3 rounded-xl border border-border/70 bg-surface px-4 py-4 sm:grid-cols-3">
        <SelectControl
          label="Academic level"
          value={filters.academic_level_id}
          onChange={(value) => updateFilters({ academic_level_id: value })}
          options={levelOptions}
          placeholder="All academic levels"
          clearable
        />
        <SelectControl
          label="Teacher"
          value={filters.teacher_membership_id}
          onChange={(value) => updateFilters({ teacher_membership_id: value })}
          options={teacherOptions}
          placeholder="All teachers"
          clearable
        />
        <SelectControl
          label="Lifecycle"
          value={filters.status}
          onChange={(value) => updateFilters({ status: value })}
          options={[
            { value: "scheduled", label: "Scheduled" },
            { value: "current", label: "Current" },
            { value: "ended", label: "Ended" },
          ]}
          placeholder="All lifecycle states"
          clearable
        />
      </div>

      <RecordList
        title={`Teacher assignments${loading ? "" : ` (${assignmentTotal})`}`}
        description="One list for current, scheduled and historical teaching coverage. Reassign and end actions preserve assignment history."
        actions={
          <Button type="button" onClick={() => selectView("assign")}>
            <UserPlus className="h-4 w-4" /> Assign teacher
          </Button>
        }
        items={assignments}
        loading={loading}
        emptyIcon={Users}
        emptyTitle="No teacher assignments"
        emptyDescription="Create an assignment or adjust the level, teacher or lifecycle filters."
        recordLabel="Subject assignment"
        detailsLabel="Coverage"
        renderTitle={(item) => item.subject_name || item.subject_code || "Subject"}
        renderMeta={(item) => item.subject_code || assignmentClassLabel(item)}
        renderDescription={(item) =>
          `${assignmentClassLabel(item)} · ${item.teacher_name || item.teacher_staff_id || "Teacher"} · ${formatPeriod(item)}`
        }
        renderStatus={(item) => String(item.status || "ended").toLowerCase()}
        renderActions={rowActions}
        renderInspector={(item) => (
          <AssignmentInspector item={item} actions={rowActions(item)} />
        )}
      />

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-text-muted">
          Showing {assignments.length} of {assignmentTotal} assignments
        </p>
        <div className="flex gap-2">
          <Button type="button" size="small" variant="outline" disabled={assignmentPage === 0 || loading} onClick={() => setAssignmentPage((value) => Math.max(0, value - 1))}>
            Previous
          </Button>
          <Button type="button" size="small" variant="outline" disabled={(assignmentPage + 1) * PAGE_SIZE >= assignmentTotal || loading} onClick={() => setAssignmentPage((value) => value + 1)}>
            Next
          </Button>
        </div>
      </div>

      <Modal
        open={Boolean(reassigning)}
        title="Reassign teacher"
        description="Replace the current teacher from an effective date while retaining the existing assignment as history."
        onClose={saving ? undefined : () => setReassigning(null)}
        footer={
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" disabled={Boolean(saving)} onClick={() => setReassigning(null)}>Cancel</Button>
            <Button type="submit" form="teacher-reassign-form" disabled={Boolean(saving) || !form.teacher_membership_id || reason.trim().length < 3}>
              {saving ? "Saving..." : "Confirm reassign"}
            </Button>
          </div>
        }
      >
        <form id="teacher-reassign-form" className="space-y-3" onSubmit={submitReassign}>
          <SelectControl label="Replacement teacher" value={form.teacher_membership_id} onChange={(value) => setForm((current) => ({ ...current, teacher_membership_id: value }))} options={teacherOptions} required />
          <Input label="Effective from" type="date" value={form.effective_from} onChange={(event) => setForm((current) => ({ ...current, effective_from: event.target.value }))} required />
          <Input label="Audit reason" value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={500} required />
        </form>
      </Modal>

      <Modal
        open={Boolean(ending)}
        title="End assignment"
        description="Close this teaching assignment at an explicit date. Historical evidence remains available."
        onClose={saving ? undefined : () => setEnding(null)}
        footer={
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" disabled={Boolean(saving)} onClick={() => setEnding(null)}>Cancel</Button>
            <Button type="submit" form="teacher-end-form" variant="danger" disabled={Boolean(saving) || reason.trim().length < 3}>
              {saving ? "Ending..." : "Confirm end"}
            </Button>
          </div>
        }
      >
        <form id="teacher-end-form" className="space-y-3" onSubmit={submitEnd}>
          <Input label="Effective end date" type="date" value={effectiveTo} onChange={(event) => setEffectiveTo(event.target.value)} required />
          <Input label="Audit reason" value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={500} required />
        </form>
      </Modal>

      <TypedConfirmationDialog
        open={Boolean(pendingDelete)}
        title="Delete unused historical assignment"
        description="Permanent deletion is available only when the backend confirms this ended assignment has no protected dependencies."
        confirmationText={DELETE_TEACHER_ASSIGNMENT}
        confirmLabel="Delete assignment"
        variant="danger"
        isLoading={saving === pendingDelete?.item?.id}
        confirmDisabled={reason.trim().length < 3}
        onConfirm={deleteAssignment}
        onCancel={() => setPendingDelete(null)}
      >
        <Input label="Audit reason" value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={500} required />
      </TypedConfirmationDialog>
    </>
  );
}

function AssignmentInspector({ item, actions }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-surface">
      <div className="border-b border-border/70 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-semibold text-text">{item.subject_name || "Subject"}</p>
            <p className="mt-1 text-xs text-text-muted">{assignmentClassLabel(item)}</p>
          </div>
          <Badge variant={String(item.status).toLowerCase() === "current" ? "success" : String(item.status).toLowerCase() === "scheduled" ? "warning" : "default"}>
            {String(item.status || "ended").toLowerCase()}
          </Badge>
        </div>
      </div>
      <div className="space-y-3 p-4 text-sm">
        <div><p className="text-xs font-semibold uppercase text-text-faint">Teacher</p><p className="mt-1 text-text">{item.teacher_name || item.teacher_staff_id || "Teacher"}</p></div>
        <div><p className="text-xs font-semibold uppercase text-text-faint">Effective period</p><p className="mt-1 text-text">{formatPeriod(item)}</p></div>
        <div><p className="text-xs font-semibold uppercase text-text-faint">Lifecycle actions</p><div className="mt-2 flex flex-wrap gap-2">{actions || <span className="text-text-muted">No action available</span>}</div></div>
      </div>
    </div>
  );
}

export default TeacherAssignmentsWorkspace;
