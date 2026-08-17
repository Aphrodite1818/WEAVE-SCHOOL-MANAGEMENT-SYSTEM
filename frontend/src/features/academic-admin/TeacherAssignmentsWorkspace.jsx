import { Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { curriculumService } from "../../services/curriculumService";
import { teacherService } from "../../services/teacherService";
import {
  Input,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  item?.display_name ||
  [item?.academic_level_name, item?.arm_label].filter(Boolean).join(" ") ||
  "Unnamed class";

const teacherLabel = (item) => {
  const account = item?.teacher_account || item?.account || {};
  const name = [account.first_name, account.last_name].filter(Boolean).join(" ");
  return name || item?.teacher_name || account.email || item?.staff_id || "Teacher";
};

const today = () => new Date().toISOString().slice(0, 10);
const PAGE_SIZE = 25;
const DELETE_TEACHER_ASSIGNMENT = "DELETE_TEACHER_ASSIGNMENT";

const formatPeriod = (item) =>
  `${item.effective_from || "Unknown start"} - ${item.effective_to || "Present"}`;

const formatDependencyMessage = (preview) => {
  const counts = preview?.dependency_counts || {};
  const details = Object.entries(counts)
    .filter(([, value]) => Number(value || 0) > 0)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`)
    .join("; ");
  const blockers = (preview?.blocker_messages || []).join(" ");
  return [blockers, details].filter(Boolean).join(" ");
};

function TeacherAssignmentsWorkspace({ activeTab }) {
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [curriculumSubjects, setCurriculumSubjects] = useState([]);
  const [currentTerm, setCurrentTerm] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [form, setForm] = useState({
    class_id: "",
    curriculum_subject_id: "",
    teacher_membership_id: "",
    effective_from: today(),
  });
  const [filters, setFilters] = useState({
    class_id: "",
    teacher_membership_id: "",
    status:
      activeTab === "reassign" || activeTab === "end"
        ? "active"
        : activeTab === "history"
          ? "ended"
          : "",
    search: "",
  });
  const [assignmentTotal, setAssignmentTotal] = useState(0);
  const [assignmentPage, setAssignmentPage] = useState(0);
  const [editingAssignmentId, setEditingAssignmentId] = useState("");
  const [viewingAssignment, setViewingAssignment] = useState(null);
  const [endingAssignmentId, setEndingAssignmentId] = useState("");
  const [effectiveTo, setEffectiveTo] = useState(today());
  const [pendingDelete, setPendingDelete] = useState(null);
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [classResponse, teacherResponse, termResponse] = await Promise.all([
        classService.getClasses({ limit: 500, activeOnly: true }),
        teacherService.listMemberships({ limit: 100 }),
        academicService.listTerms({ is_current: true, limit: 1 }),
      ]);
      const nextClasses = asItems(classResponse);
      const nextCurrentTerm = asItems(termResponse)[0] || null;
      setClasses(nextClasses);
      setCurrentTerm(nextCurrentTerm);
      setTeachers(
        asItems(teacherResponse).filter(
          (item) => String(item.status || "active").toLowerCase() === "active",
        ),
      );
      setForm((current) => ({
        ...current,
        class_id: current.class_id || nextClasses[0]?.id || "",
      }));
    } catch (err) {
      const message = getErrorMessage(err, "Could not load teacher assignments.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [showError]);

  const loadAssignments = useCallback(async () => {
    try {
      const response = await academicService.listTeacherAssignments({
        class_id: filters.class_id,
        teacher_membership_id: filters.teacher_membership_id,
        status: filters.status,
        search: filters.search,
        skip: assignmentPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setAssignments(asItems(response));
      setAssignmentTotal(Number(response?.total || 0));
    } catch (err) {
      showError(getErrorMessage(err, "Could not load teacher assignments."));
    }
  }, [
    assignmentPage,
    filters.class_id,
    filters.search,
    filters.status,
    filters.teacher_membership_id,
    showError,
  ]);

  const loadCurriculumSubjects = useCallback(async () => {
    if (!form.class_id) {
      setCurriculumSubjects([]);
      return;
    }
    try {
      const classroom = classes.find((item) => item.id === form.class_id);
      if (!classroom?.academic_level_id) {
        setCurriculumSubjects([]);
        return;
      }
      const [curriculumResponse, assignmentsResponse] = await Promise.all([
        curriculumService.getCurriculum(classroom.academic_level_id),
        academicService.listTeacherAssignments({
          class_id: form.class_id,
          status: "active",
          limit: 100,
        }),
      ]);
      const subjects = (curriculumResponse?.subjects || []).filter(
        (item) => item.is_active !== false,
      );
      const activeAssignments = asItems(assignmentsResponse);
      const assignedSubjectIds = new Set(
        activeAssignments.map((item) => item.curriculum_subject_id),
      );
      setCurriculumSubjects(
        subjects.filter(
          (subject) =>
            !assignedSubjectIds.has(subject.id) ||
            subject.id === form.curriculum_subject_id,
        ),
      );
    } catch (err) {
      setCurriculumSubjects([]);
      showError(
        getErrorMessage(err, "Could not load curriculum subjects for this class."),
      );
    }
  }, [classes, form.class_id, form.curriculum_subject_id, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadAssignments();
  }, [loadAssignments]);

  useEffect(() => {
    loadCurriculumSubjects();
  }, [loadCurriculumSubjects]);

  useEffect(() => {
    const nextStatus =
      activeTab === "reassign" || activeTab === "end"
        ? "active"
        : activeTab === "history"
          ? "ended"
          : "";
    setAssignmentPage(0);
    setFilters((current) =>
      current.status === nextStatus ? current : { ...current, status: nextStatus },
    );
    if (activeTab !== "reassign") {
      setEditingAssignmentId("");
    }
    if (activeTab !== "end") {
      setEndingAssignmentId("");
    }
  }, [activeTab]);

  const classOptions = useMemo(
    () => classes.map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );
  const teacherOptions = useMemo(
    () => teachers.map((item) => ({ value: item.id, label: teacherLabel(item) })),
    [teachers],
  );
  const subjectOptions = useMemo(
    () =>
      curriculumSubjects.map((item) => ({
        value: item.id,
        label: [item.subject_name, item.subject_code].filter(Boolean).join(" · "),
      })),
    [curriculumSubjects],
  );

  const resetForm = () => {
    setEditingAssignmentId("");
    setForm((current) => ({
      class_id: current.class_id,
      curriculum_subject_id: "",
      teacher_membership_id: "",
      effective_from: today(),
    }));
  };

  const openAssignmentEditor = (item) => {
    if (!item.is_active) return;
    setEditingAssignmentId(item.id);
    setForm({
      class_id: item.class_id || "",
      curriculum_subject_id: item.curriculum_subject_id || "",
      teacher_membership_id: item.teacher_membership_id || "",
      effective_from: today(),
    });
  };

  const saveAssignment = async (event) => {
    event.preventDefault();
    if (!form.teacher_membership_id) {
      showWarning("Select a teacher.");
      return;
    }
    if (!editingAssignmentId && !form.curriculum_subject_id) {
      showWarning("Select a curriculum subject.");
      return;
    }
    if (!editingAssignmentId && !currentTerm?.id) {
      showWarning("Open an academic term before creating teacher assignments.");
      return;
    }
    setSaving("assignment");
    try {
      if (editingAssignmentId) {
        await academicService.reassignTeacherAssignment(editingAssignmentId, {
          teacher_membership_id: form.teacher_membership_id,
          effective_from: form.effective_from,
        });
      } else {
        await academicService.createTeacherAssignment({
          class_id: form.class_id,
          curriculum_subject_id: form.curriculum_subject_id,
          academic_term_id: currentTerm.id,
          teacher_membership_id: form.teacher_membership_id,
          effective_from: form.effective_from,
        });
      }
      showSuccess(
        editingAssignmentId
          ? "Teacher assignment updated."
          : "Teacher assigned to curriculum subject.",
      );
      resetForm();
      await loadAssignments();
      await loadCurriculumSubjects();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save teacher assignment."));
    } finally {
      setSaving("");
    }
  };

  const endAssignment = async (item) => {
    setSaving(item.id);
    try {
      const preview = await academicService.getTeacherAssignmentDependencies(item.id);
      if (!preview?.can_end) {
        showError(
          formatDependencyMessage(preview) || "This assignment cannot be ended.",
        );
        return;
      }
      await academicService.endTeacherAssignment(item.id, {
        effective_to: effectiveTo || null,
      });
      showSuccess("Assignment ended and retained in history.");
      setEndingAssignmentId("");
      await loadAssignments();
    } catch (err) {
      showError(getErrorMessage(err, "Could not end assignment."));
    } finally {
      setSaving("");
    }
  };

  const openDeleteConfirmation = async (item) => {
    try {
      const preview = await academicService.getTeacherAssignmentDependencies(item.id);
      if (!preview?.can_delete) {
        showError(
          formatDependencyMessage(preview) || "This assignment cannot be deleted.",
        );
        return;
      }
      setPendingDelete({ item, preview });
    } catch (err) {
      showError(
        getErrorMessage(err, "Could not inspect assignment dependencies."),
      );
    }
  };

  const deleteAssignment = async () => {
    if (!pendingDelete?.item) return;
    const item = pendingDelete.item;
    setSaving(item.id);
    try {
      await academicService.deleteTeacherAssignment(item.id);
      showSuccess("Historical assignment deleted.");
      setPendingDelete(null);
      await loadAssignments();
    } catch (err) {
      showError(getErrorMessage(err, "Could not delete teacher assignment."));
    } finally {
      setSaving("");
    }
  };

  const updateFilters = (patch) => {
    setAssignmentPage(0);
    setFilters((current) => ({ ...current, ...patch }));
  };

  const editor = (
    <WorkspacePanel
      title={
        editingAssignmentId ? "Change assigned teacher" : "Assign subject teacher"
      }
      description="Choose the class, curriculum subject, teacher, and start date. Assignment eligibility is validated against the current term."
    >
      <form className="space-y-3" onSubmit={saveAssignment}>
        <SelectControl
          label="Class"
          value={form.class_id}
          onChange={(value) =>
            setForm((current) => ({
              ...current,
              class_id: value,
              curriculum_subject_id: "",
            }))
          }
          options={classOptions}
          required
          disabled={Boolean(editingAssignmentId)}
        />
        <SelectControl
          label="Curriculum subject"
          value={form.curriculum_subject_id}
          onChange={(value) =>
            setForm((current) => ({
              ...current,
              curriculum_subject_id: value,
            }))
          }
          options={subjectOptions}
          placeholder={
            subjectOptions.length === 0
              ? "No available curriculum subjects"
              : "Select subject"
          }
          required
          disabled={
            Boolean(editingAssignmentId) ||
            subjectOptions.length === 0 ||
            !currentTerm?.id
          }
        />
        <SelectControl
          label="Teacher"
          value={form.teacher_membership_id}
          onChange={(value) =>
            setForm((current) => ({ ...current, teacher_membership_id: value }))
          }
          options={teacherOptions}
          placeholder="Select teacher"
          required
        />
        <Input
          label={
            editingAssignmentId
              ? "Replacement effective from"
              : "Effective from"
          }
          type="date"
          value={form.effective_from}
          onChange={(event) =>
            setForm((current) => ({
              ...current,
              effective_from: event.target.value,
            }))
          }
          required
        />
        {!currentTerm?.id && !editingAssignmentId ? (
          <p className="text-sm text-text-muted">
            Open an academic term before assigning subject teachers.
          </p>
        ) : null}
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="submit"
            disabled={saving === "assignment" || (!editingAssignmentId && !currentTerm?.id)}
          >
            {saving === "assignment"
              ? "Saving..."
              : editingAssignmentId
                ? "Reassign teacher"
                : "Create assignment"}
          </Button>
          {editingAssignmentId ? (
            <Button type="button" variant="outline" onClick={resetForm}>
              Cancel
            </Button>
          ) : null}
        </div>
      </form>
    </WorkspacePanel>
  );

  const review = (
    <WorkspacePanel
      title={
        activeTab === "history"
          ? "Assignment history"
          : activeTab === "reassign"
            ? "Reassign teacher"
            : activeTab === "end"
              ? "End assignment"
              : "All assignments"
      }
      description={
        activeTab === "reassign"
          ? "Select an active assignment, then choose the replacement teacher and effective date."
          : activeTab === "end"
            ? "Select an active assignment and record its effective end date."
            : "Filter and review current or historical teacher assignments."
      }
    >
      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <SelectControl
          label="Filter by class"
          value={filters.class_id}
          onChange={(value) => updateFilters({ class_id: value })}
          options={classOptions}
          placeholder="All classes"
        />
        <SelectControl
          label="Filter by teacher"
          value={filters.teacher_membership_id}
          onChange={(value) => updateFilters({ teacher_membership_id: value })}
          options={teacherOptions}
          placeholder="All teachers"
        />
        <SelectControl
          label="Filter by status"
          value={filters.status}
          onChange={(value) => updateFilters({ status: value })}
          options={[
            { value: "active", label: "Active" },
            { value: "ended", label: "Ended" },
          ]}
          placeholder="All statuses"
          disabled={
            activeTab === "reassign" ||
            activeTab === "end" ||
            activeTab === "history"
          }
        />
        <Input
          label="Search"
          value={filters.search}
          onChange={(event) => updateFilters({ search: event.target.value })}
          placeholder="Teacher, staff ID, class, subject"
        />
      </div>

      {assignments.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <Users className="mx-auto h-7 w-7 text-text-muted" />
          <p className="mt-3 text-sm font-semibold text-text">No assignments found</p>
          <p className="mt-1 text-sm text-text-muted">
            Create an assignment or adjust the filters.
          </p>
        </div>
      ) : (
        <div className="max-h-[calc(100vh-22rem)] overflow-y-auto pr-2">
          <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
            {assignments.map((item) => (
              <div
                key={item.id}
                className="flex min-h-[11rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words font-semibold text-text">
                      {item.subject_name || "Subject"}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {item.subject_code || "No subject code"}
                    </p>
                  </div>
                  <Badge variant={item.is_active ? "success" : "error"}>
                    {item.is_active ? "active" : "inactive"}
                  </Badge>
                </div>
                <div className="mt-3 space-y-1 text-sm text-text-muted">
                  <p>
                    {[item.class_name, item.class_arm].filter(Boolean).join(" ")}
                  </p>
                  <p>{item.teacher_name || item.teacher_staff_id || "Teacher"}</p>
                  <p>Effective: {formatPeriod(item)}</p>
                </div>
                <div className="mt-auto flex flex-wrap gap-2 pt-4">
                  <Button
                    type="button"
                    size="small"
                    variant="outline"
                    onClick={() => setViewingAssignment(item)}
                  >
                    View
                  </Button>
                  {item.is_active ? (
                    <>
                      {activeTab === "reassign" ? (
                        <Button
                          type="button"
                          size="small"
                          variant="outline"
                          onClick={() => openAssignmentEditor(item)}
                        >
                          Reassign teacher
                        </Button>
                      ) : null}
                      {activeTab === "end" ? (
                        <Button
                          type="button"
                          size="small"
                          variant="danger"
                          disabled={saving === item.id}
                          onClick={() => {
                            setEndingAssignmentId(item.id);
                            setEffectiveTo(item.effective_from || today());
                          }}
                        >
                          End assignment
                        </Button>
                      ) : null}
                    </>
                  ) : activeTab === "history" ? (
                    <Button
                      type="button"
                      size="small"
                      variant="danger"
                      disabled={saving === item.id}
                      onClick={() => openDeleteConfirmation(item)}
                    >
                      Delete
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-text-muted">
          Showing {assignments.length} of {assignmentTotal} assignments
        </p>
        <div className="flex gap-2">
          <Button
            type="button"
            size="small"
            variant="outline"
            disabled={assignmentPage === 0}
            onClick={() => setAssignmentPage((page) => Math.max(page - 1, 0))}
          >
            Previous
          </Button>
          <Button
            type="button"
            size="small"
            variant="outline"
            disabled={(assignmentPage + 1) * PAGE_SIZE >= assignmentTotal}
            onClick={() => setAssignmentPage((page) => page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
      <Modal
        open={Boolean(viewingAssignment)}
        title={viewingAssignment?.subject_name || "Teacher assignment"}
        description="Assignment details"
        onClose={() => setViewingAssignment(null)}
        footer={
          <div className="flex justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => setViewingAssignment(null)}
            >
              Close
            </Button>
          </div>
        }
      >
        {viewingAssignment ? (
          <div className="space-y-2 text-sm text-text-muted">
            <p>
              Teacher: {viewingAssignment.teacher_name || viewingAssignment.teacher_staff_id || "Teacher"}
            </p>
            <p>
              Class: {[viewingAssignment.class_name, viewingAssignment.class_arm].filter(Boolean).join(" ")}
            </p>
            <p>Subject: {viewingAssignment.subject_name || "Subject"}</p>
            <p>Effective: {formatPeriod(viewingAssignment)}</p>
            <p>Status: {viewingAssignment.is_active ? "active" : "ended"}</p>
          </div>
        ) : null}
      </Modal>
      <Modal
        open={Boolean(editingAssignmentId)}
        title="Reassign teacher"
        description="Choose the replacement teacher and effective start date."
        onClose={saving === "assignment" ? undefined : resetForm}
        closeOnOverlay={saving !== "assignment"}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={resetForm}
              disabled={saving === "assignment"}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="teacher-reassign-form"
              disabled={saving === "assignment"}
            >
              {saving === "assignment" ? "Saving..." : "Confirm reassign"}
            </Button>
          </div>
        }
      >
        <form
          id="teacher-reassign-form"
          className="space-y-3"
          onSubmit={saveAssignment}
        >
          <SelectControl
            label="Replacement teacher"
            value={form.teacher_membership_id}
            onChange={(value) =>
              setForm((current) => ({ ...current, teacher_membership_id: value }))
            }
            options={teacherOptions}
            placeholder="Select replacement teacher"
            required
          />
          <Input
            label="Replacement effective from"
            type="date"
            value={form.effective_from}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                effective_from: event.target.value,
              }))
            }
            required
          />
        </form>
      </Modal>
      <Modal
        open={Boolean(endingAssignmentId)}
        title="End assignment"
        description="Record the effective end date for this teacher assignment."
        onClose={
          saving === endingAssignmentId
            ? undefined
            : () => setEndingAssignmentId("")
        }
        closeOnOverlay={saving !== endingAssignmentId}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => setEndingAssignmentId("")}
              disabled={saving === endingAssignmentId}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="teacher-end-form"
              variant="danger"
              disabled={saving === endingAssignmentId}
            >
              {saving === endingAssignmentId ? "Ending..." : "Confirm end"}
            </Button>
          </div>
        }
      >
        <form
          id="teacher-end-form"
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            const item = assignments.find(
              (assignment) => assignment.id === endingAssignmentId,
            );
            if (item) endAssignment(item);
          }}
        >
          <Input
            label="Effective end date"
            type="date"
            value={effectiveTo}
            onChange={(event) => setEffectiveTo(event.target.value)}
            required
          />
        </form>
      </Modal>
      <TypedConfirmationDialog
        open={Boolean(pendingDelete)}
        title="Delete historical assignment"
        description={pendingDelete?.item ? formatPeriod(pendingDelete.item) : ""}
        confirmationText={DELETE_TEACHER_ASSIGNMENT}
        confirmLabel="Delete assignment"
        variant="danger"
        isLoading={saving === pendingDelete?.item?.id}
        onConfirm={deleteAssignment}
        onCancel={() => setPendingDelete(null)}
      />
    </WorkspacePanel>
  );

  if (error && !loading) {
    return (
      <WorkspacePanel title="Teacher assignments unavailable">
        <p className="text-sm text-error">{error}</p>
        <Button type="button" className="mt-4" onClick={loadBase}>
          Retry
        </Button>
      </WorkspacePanel>
    );
  }

  if (activeTab === "assign") return editor;
  if (
    activeTab === "overview" ||
    activeTab === "history" ||
    activeTab === "end" ||
    activeTab === "reassign"
  ) {
    return review;
  }
  return <WorkspaceGrid editor={editor} content={review} />;
}

export default TeacherAssignmentsWorkspace;
