import { Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { teacherService } from "../../services/teacherService";
import {
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || "Unnamed class";

const teacherLabel = (item) => {
  const account = item?.teacher_account || item?.account || {};
  const name = [account.first_name, account.last_name].filter(Boolean).join(" ");
  return name || item?.teacher_name || account.email || item?.staff_id || "Teacher";
};

const today = () => new Date().toISOString().slice(0, 10);

function TeacherAssignmentsWorkspace({ activeTab }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [classSubjects, setClassSubjects] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [form, setForm] = useState({
    class_id: "",
    class_subject_id: "",
    teacher_membership_id: "",
  });
  const [filters, setFilters] = useState({
    class_id: "",
    teacher_membership_id: "",
  });
  const [editingAssignmentId, setEditingAssignmentId] = useState("");
  const [endingAssignmentId, setEndingAssignmentId] = useState("");
  const [effectiveTo, setEffectiveTo] = useState(today());
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [classResponse, teacherResponse, assignmentResponse] = await Promise.all([
        classService.getClasses({ limit: 100, activeOnly: true }),
        teacherService.listMemberships({ limit: 100 }),
        academicService.listTeacherAssignments({ limit: 100 }),
      ]);
      const nextClasses = asItems(classResponse);
      setClasses(nextClasses);
      setTeachers(
        asItems(teacherResponse).filter(
          (item) => String(item.status || "active").toLowerCase() === "active",
        ),
      );
      setAssignments(asItems(assignmentResponse));
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

  const loadClassSubjects = useCallback(async () => {
    if (!form.class_id) {
      setClassSubjects([]);
      return;
    }
    try {
      const response = await academicService.listOfferedClassSubjects(form.class_id, {
        active_only: true,
        limit: 100,
      });
      setClassSubjects(asItems(response));
    } catch (err) {
      setClassSubjects([]);
      showError(getErrorMessage(err, "Could not load class subjects."));
    }
  }, [form.class_id, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadClassSubjects();
  }, [loadClassSubjects]);

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
      classSubjects.map((item) => ({
        value: item.id,
        label: [item.subject_name, item.subject_code].filter(Boolean).join(" · "),
      })),
    [classSubjects],
  );
  const visibleAssignments = useMemo(
    () =>
      assignments.filter(
        (item) =>
          (!filters.class_id || item.class_id === filters.class_id) &&
          (!filters.teacher_membership_id ||
            item.teacher_membership_id === filters.teacher_membership_id),
      ),
    [assignments, filters.class_id, filters.teacher_membership_id],
  );

  const resetForm = () => {
    setEditingAssignmentId("");
    setForm((current) => ({
      class_id: current.class_id,
      class_subject_id: "",
      teacher_membership_id: "",
    }));
  };

  const openAssignmentEditor = (item) => {
    setEditingAssignmentId(item.id);
    setForm({
      class_id: item.class_id || "",
      class_subject_id: item.class_subject_id || "",
      teacher_membership_id: item.teacher_membership_id || "",
    });

    const next = new URLSearchParams(searchParams);
    next.set("view", "assign");
    next.delete("tab");
    setSearchParams(next);
  };

  const saveAssignment = async (event) => {
    event.preventDefault();
    if (!form.class_subject_id || !form.teacher_membership_id) {
      showWarning("Select a class subject and teacher.");
      return;
    }
    setSaving("assignment");
    try {
      if (editingAssignmentId) {
        await academicService.reassignTeacherAssignment(form.class_subject_id, {
          teacher_membership_id: form.teacher_membership_id,
        });
      } else {
        await academicService.createTeacherAssignment({
          class_subject_id: form.class_subject_id,
          teacher_membership_id: form.teacher_membership_id,
        });
      }
      showSuccess(
        editingAssignmentId
          ? "Teacher assignment updated."
          : "Teacher assigned to class subject.",
      );
      resetForm();
      await loadBase();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save teacher assignment."));
    } finally {
      setSaving("");
    }
  };

  const endAssignment = async (item) => {
    setSaving(item.id);
    try {
      await academicService.endTeacherAssignment(item.id, {
        effective_to: effectiveTo || null,
      });
      showSuccess("Assignment ended and retained in history.");
      setEndingAssignmentId("");
      await loadBase();
    } catch (err) {
      showError(getErrorMessage(err, "Could not end assignment."));
    } finally {
      setSaving("");
    }
  };

  const editor = (
    <WorkspacePanel
      title={editingAssignmentId ? "Change assigned teacher" : "Assign subject teacher"}
      description="Assignments use teacher membership IDs, not global teacher account IDs."
    >
      <form className="space-y-3" onSubmit={saveAssignment}>
        <SelectControl
          label="Class"
          value={form.class_id}
          onChange={(value) =>
            setForm((current) => ({
              ...current,
              class_id: value,
              class_subject_id: "",
            }))
          }
          options={classOptions}
          required
          disabled={Boolean(editingAssignmentId)}
        />
        <SelectControl
          label="Class subject"
          value={form.class_subject_id}
          onChange={(value) =>
            setForm((current) => ({ ...current, class_subject_id: value }))
          }
          options={subjectOptions}
          placeholder={
            subjectOptions.length === 0
              ? "No active subjects attached"
              : "Select class subject"
          }
          required
          disabled={Boolean(editingAssignmentId) || subjectOptions.length === 0}
        />
        <SelectControl
          label="Teacher"
          value={form.teacher_membership_id}
          onChange={(value) =>
            setForm((current) => ({ ...current, teacher_membership_id: value }))
          }
          options={teacherOptions}
          placeholder="Select active teacher membership"
          required
        />
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button type="submit" disabled={saving === "assignment"}>
            {saving === "assignment"
              ? "Saving..."
              : editingAssignmentId
                ? "Change teacher"
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
      title={activeTab === "history" ? "Assignment history" : "Teacher assignments"}
      description="Filter and manage current or historical class-subject assignments."
    >
      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <SelectControl
          label="Filter by class"
          value={filters.class_id}
          onChange={(value) => setFilters((current) => ({ ...current, class_id: value }))}
          options={classOptions}
          placeholder="All classes"
        />
        <SelectControl
          label="Filter by teacher"
          value={filters.teacher_membership_id}
          onChange={(value) =>
            setFilters((current) => ({ ...current, teacher_membership_id: value }))
          }
          options={teacherOptions}
          placeholder="All teachers"
        />
      </div>

      {(activeTab === "active"
        ? visibleAssignments.filter((item) => item.is_active)
        : activeTab === "history" || activeTab === "end" || activeTab === "reassign"
          ? visibleAssignments
          : visibleAssignments
      ).length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <Users className="mx-auto h-7 w-7 text-text-muted" />
          <p className="mt-3 text-sm font-semibold text-text">No assignments found</p>
          <p className="mt-1 text-sm text-text-muted">
            Create an assignment or adjust the filters.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {(activeTab === "active"
            ? visibleAssignments.filter((item) => item.is_active)
            : visibleAssignments
          ).map((item) => (
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
                <p>{[item.class_name, item.class_arm].filter(Boolean).join(" ")}</p>
                <p>{item.teacher_name || item.teacher_staff_id || "Teacher"}</p>
              </div>
              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  onClick={() => openAssignmentEditor(item)}
                >
                  Change teacher
                </Button>
                {item.is_active ? (
                  <Button
                    type="button"
                    size="small"
                    variant="danger"
                    disabled={saving === item.id}
                    onClick={() => {
                      setEndingAssignmentId(item.id);
                      setEffectiveTo(today());
                    }}
                  >
                    End
                  </Button>
                ) : null}
              </div>
              {endingAssignmentId === item.id ? (
                <form
                  className="mt-3 rounded-xl border border-error/20 bg-error-soft p-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    endAssignment(item);
                  }}
                >
                  <label className="block text-xs font-semibold text-error">
                    Effective end date
                    <input
                      type="date"
                      className="input-base mt-1"
                      value={effectiveTo}
                      onChange={(event) => setEffectiveTo(event.target.value)}
                    />
                  </label>
                  <div className="mt-2 flex gap-2">
                    <Button type="submit" size="small" variant="danger" disabled={saving === item.id}>
                      {saving === item.id ? "Ending..." : "Confirm end"}
                    </Button>
                    <Button type="button" size="small" variant="outline" onClick={() => setEndingAssignmentId("")}>
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : null}
            </div>
          ))}
        </div>
      )}
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
  if (activeTab === "active" || activeTab === "history" || activeTab === "end" || activeTab === "reassign") return review;
  return <WorkspaceGrid editor={editor} content={review} />;
}

export default TeacherAssignmentsWorkspace;
