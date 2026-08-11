import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Archive,
  Ban,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  GraduationCap,
  MoreHorizontal,
  PlusCircle,
  RotateCcw,
  ShieldOff,
  Trash2,
  Undo2,
  UserCheck,
  UserMinus,
  UserRound,
} from "lucide-react";

import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StudentAccessCodeSlipModal from "../../components/students/StudentAccessCodeSlipModal";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Dropdown from "../../components/ui/Dropdown";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { useToast } from "../../hooks/useToast";
import academicService from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { parseApiError } from "../../services/api";
import { studentService } from "../../services/studentService";
import { displayName } from "../../utils/user";

const PAGE_SIZE = 24;
const STUDENT_STATUSES = ["active", "suspended", "withdrawn", "graduated", "expelled"];
const GENDER_OPTIONS = ["male", "female"];

const EMPTY_FILTERS = {
  search: "",
  classId: "",
  status: "active",
  includeArchived: false,
};

const localDateInputValue = (date = new Date()) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const formatDate = (value) => {
  if (!value) return "Not set";
  const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
};

const classLabel = (item) =>
  [item?.academic_level_name, item?.arm].filter(Boolean).join(" ") || item?.id || "Class";

const studentClassLabel = (student) =>
  [student?.class_name, student?.class_arm].filter(Boolean).join(" ") || "Not assigned";

const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);

const lifecycleConfig = {
  suspend: {
    label: "Suspend",
    icon: Ban,
    method: "suspendStudent",
    variant: "outline",
    usesPromotionHold: true,
  },
  reinstate: {
    label: "Reinstate",
    icon: UserCheck,
    method: "reinstateStudent",
    variant: "success",
  },
  reinstateExpelled: {
    label: "Reinstate expelled",
    icon: UserCheck,
    method: "reinstateExpelledStudent",
    variant: "success",
    usesClassSession: true,
    usesEffectiveDate: true,
  },
  withdraw: {
    label: "Withdraw",
    icon: UserMinus,
    method: "withdrawStudent",
    variant: "outline",
    usesEffectiveDate: true,
  },
  expel: {
    label: "Expel",
    icon: ShieldOff,
    method: "expelStudent",
    variant: "danger",
    usesEffectiveDate: true,
  },
  graduate: {
    label: "Graduate",
    icon: GraduationCap,
    method: "graduateStudent",
    variant: "outline",
    usesGraduationDate: true,
  },
  archive: {
    label: "Archive",
    icon: Archive,
    method: "archiveStudent",
    variant: "danger",
  },
  restore: {
    label: "Restore",
    icon: Undo2,
    method: "restoreStudent",
    variant: "success",
  },
};

const actionsForStudent = (student) => {
  if (student.is_archived) return ["restore"];
  const status = String(student.status || "").toLowerCase();
  if (status === "active") return ["suspend", "withdraw", "expel", "graduate", "archive"];
  if (status === "suspended") return ["reinstate", "withdraw", "expel", "archive"];
  if (status === "expelled") return ["reinstateExpelled", "archive"];
  return ["archive"];
};

function SelectField({
  label,
  name,
  value,
  onChange,
  options,
  placeholder,
  error,
  required,
  searchable = true,
}) {
  return (
    <SearchableSelect
      label={label}
      name={name}
      value={value || ""}
      options={options}
      placeholder={placeholder || "Select"}
      searchPlaceholder={`Search ${String(label || "options").toLowerCase()}`}
      searchable={searchable}
      clearable={!required}
      required={required}
      error={error}
      onChange={(nextValue) =>
        onChange({
          target: {
            name,
            value: nextValue,
          },
        })
      }
    />
  );
}

function buildAccessNotice(result) {
  if (!result?.access_code) return null;
  return {
    title: "Student access code",
    description: "Give this one-time code to the student so they can set a new password.",
    fields: [
      { label: "Student", value: result.full_name || "Student" },
      { label: "Admission number", value: result.admission_number },
      { label: "Access code", value: result.access_code },
      { label: "Expires", value: formatDate(result.expires_at) },
    ],
  };
}

function StudentCard({ student, busy, onEdit, onReset, onHistory, onLifecycle, onHardDelete }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const actions = actionsForStudent(student);

  return (
    <Card className="flex min-h-[20rem] flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
            <UserRound className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h3 className="break-words font-semibold text-text">{displayName(student)}</h3>
            <p className="mt-1 text-xs text-text-muted">{student.admission_number}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge variant={student.status === "active" ? "success" : "default"}>
            {titleCase(student.status)}
          </Badge>
          {student.is_archived ? <Badge variant="error">Archived</Badge> : null}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 rounded-2xl bg-surface-muted/30 px-4 py-3 text-sm">
        <div>
          <p className="text-xs font-semibold uppercase text-text-muted">Class</p>
          <p className="mt-1 text-text-soft">{studentClassLabel(student)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-text-muted">Admission</p>
          <p className="mt-1 text-text-soft">{formatDate(student.admission_date)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-text-muted">Profile</p>
          <p className="mt-1 text-text-soft">{titleCase(student.profile_status)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-text-muted">Credentials</p>
          <p className="mt-1 text-text-soft">
            {student.password_reset_required ? "Setup required" : "Configured"}
          </p>
        </div>
      </div>

      <div className="mt-auto grid grid-cols-2 gap-2 pt-4">
        <Button type="button" size="small" variant="outline" onClick={() => onEdit(student)} disabled={busy}>
          Edit profile
        </Button>
        <Button type="button" size="small" variant="outline" onClick={() => onHistory(student)} disabled={busy}>
          <BookOpen className="h-4 w-4" />
          Class history
        </Button>
        <Button type="button" size="small" variant="outline" onClick={() => onReset(student)} disabled={busy || student.is_archived}>
          <RotateCcw className="h-4 w-4" />
          Reset code
        </Button>
        <Dropdown
          open={menuOpen}
          onOpenChange={setMenuOpen}
          align="right"
          strategy="fixed"
          className="w-64"
          trigger={
            <Button type="button" size="small" variant="outline" disabled={busy} className="w-full justify-between">
              Lifecycle
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          }
        >
          <div className="grid gap-1">
            {actions.map((key) => {
              const item = lifecycleConfig[key];
              const Icon = item.icon;
              return (
                <button
                  key={key}
                  type="button"
                  className={`flex min-h-10 items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold transition hover:bg-surface-muted ${["archive", "expel"].includes(key) ? "text-error" : "text-text-soft"}`}
                  onClick={() => {
                    setMenuOpen(false);
                    onLifecycle(student, key);
                  }}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
            <button
              type="button"
              className="flex min-h-10 items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold text-error transition hover:bg-error-soft"
              onClick={() => {
                setMenuOpen(false);
                onHardDelete(student);
              }}
            >
              <Trash2 className="h-4 w-4" />
              Hard-delete check
            </button>
          </div>
        </Dropdown>
      </div>
    </Card>
  );
}

function StudentDirectoryPage() {
  const navigate = useNavigate();
  const { showSuccess, showError, showWarning } = useToast();
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(EMPTY_FILTERS);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [accessNotice, setAccessNotice] = useState(null);
  const [editState, setEditState] = useState(null);
  const [lifecycleState, setLifecycleState] = useState(null);
  const [historyState, setHistoryState] = useState(null);
  const [hardDeleteState, setHardDeleteState] = useState(null);
  const [accessCodeConfirmation, setAccessCodeConfirmation] = useState(null);

  const classOptions = useMemo(
    () => classes.map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );
  const sessionOptions = useMemo(
    () => sessions.map((item) => ({ value: item.id, label: item.name || item.id })),
    [sessions],
  );
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadReferenceData = useCallback(async () => {
    const [classResult, sessionResult] = await Promise.all([
      classService.getClasses({ limit: 100 }),
      academicService.listSessions({ limit: 100 }),
    ]);
    setClasses(asItems(classResult));
    setSessions(asItems(sessionResult));
  }, []);

  const loadStudents = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await studentService.getAdminStudents({
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
        search: appliedFilters.search.trim() || undefined,
        classId: appliedFilters.classId || undefined,
        status: appliedFilters.status || undefined,
        includeArchived: appliedFilters.includeArchived,
      });
      setStudents(asItems(response));
      setTotal(Number(response?.total || 0));
    } catch (requestError) {
      setError(parseApiError(requestError, "Failed to load students.").message);
    } finally {
      setLoading(false);
    }
  }, [appliedFilters, page]);

  useEffect(() => {
    loadReferenceData().catch((requestError) => {
      setError(parseApiError(requestError, "Failed to load classes and sessions.").message);
    });
  }, [loadReferenceData]);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setPage(1);
      setAppliedFilters({ ...draftFilters });
    }, draftFilters.search.trim() ? 250 : 0);

    return () => window.clearTimeout(timeoutId);
  }, [draftFilters]);

  const refresh = async () => {
    await loadStudents();
  };

  const openEdit = (student) => {
    setFieldErrors({});
    setEditState({
      student,
      form: {
        first_name: student.first_name || "",
        last_name: student.last_name || "",
        gender: student.gender || "",
        date_of_birth: student.date_of_birth || "",
        state_of_origin: student.state_of_origin || "",
        arm: student.arm || "",
      },
    });
  };

  const submitEdit = async (event) => {
    event.preventDefault();
    if (!editState) return;
    setBusyId(editState.student.id);
    setFieldErrors({});
    const payload = Object.fromEntries(
      Object.entries(editState.form)
        .map(([key, value]) => [key, value === "" ? null : value]),
    );
    try {
      await studentService.updateAdminStudent(editState.student.id, payload);
      showSuccess("Student profile updated.");
      setEditState(null);
      await refresh();
    } catch (requestError) {
      const parsed = parseApiError(requestError, "Failed to update student.");
      setFieldErrors(parsed.fieldErrors || {});
      showError(parsed.message);
    } finally {
      setBusyId("");
    }
  };

  const openLifecycle = (student, actionKey) => {
    const currentSession = sessions.find((item) => item.is_current) || sessions[0];
    setFieldErrors({});
    setLifecycleState({
      student,
      actionKey,
      form: {
        reason: "",
        effective_date: localDateInputValue(),
        graduation_date: localDateInputValue(),
        promotion_hold: true,
        target_class_id: student.class_id || classes[0]?.id || "",
        academic_session_id: currentSession?.id || "",
      },
    });
  };

  const submitLifecycle = async (event) => {
    event.preventDefault();
    if (!lifecycleState) return;
    const { student, actionKey, form } = lifecycleState;
    const config = lifecycleConfig[actionKey];
    const reason = form.reason.trim();
    if (reason.length < 3) {
      setFieldErrors({ reason: "Enter a reason with at least three characters." });
      return;
    }
    const payload = { reason };
    if (config.usesPromotionHold) payload.promotion_hold = form.promotion_hold;
    if (config.usesEffectiveDate) payload.effective_date = form.effective_date;
    if (config.usesGraduationDate) payload.graduation_date = form.graduation_date;
    if (config.usesClassSession) {
      payload.target_class_id = form.target_class_id;
      payload.academic_session_id = form.academic_session_id;
      if (!payload.target_class_id || !payload.academic_session_id) {
        setFieldErrors({
          target_class_id: payload.target_class_id ? undefined : "Choose a class.",
          academic_session_id: payload.academic_session_id ? undefined : "Choose a session.",
        });
        return;
      }
    }

    setBusyId(student.id);
    try {
      const response = await studentService[config.method](student.id, payload);
      const updatedStudent = response?.student || response;
      showSuccess(`${config.label} completed.`);
      setLifecycleState(null);
      if (
        ["restore", "reinstate", "reinstateExpelled"].includes(actionKey) &&
        updatedStudent?.password_reset_required
      ) {
        showWarning("Student access is restored, but a new access code is still required.");
      }
      await refresh();
    } catch (requestError) {
      const parsed = parseApiError(requestError, `Failed to ${config.label.toLowerCase()} student.`);
      setFieldErrors(parsed.fieldErrors || {});
      showError(parsed.message);
    } finally {
      setBusyId("");
    }
  };

  const resetAccessCode = async (student) => {
    setBusyId(student.id);
    try {
      const result = await studentService.resetStudentAccessCode(student.id);
      setAccessNotice(buildAccessNotice(result));
      showSuccess("New student access code generated.");
      setAccessCodeConfirmation(null);
      await refresh();
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to generate access code.").message);
    } finally {
      setBusyId("");
    }
  };

  const openHistory = async (student) => {
    setHistoryState({ student, loading: true, items: [], mode: "history", form: null });
    try {
      const response = await studentService.getEnrollmentHistory(student.id);
      setHistoryState({ student, loading: false, items: asItems(response), mode: "history", form: null });
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to load class history.").message);
      setHistoryState(null);
    }
  };

  const startClassChange = () => {
    if (!historyState) return;
    const currentSession = sessions.find((item) => item.is_current) || sessions[0];
    setFieldErrors({});
    setHistoryState((current) => ({
      ...current,
      mode: "change",
      form: {
        target_class_id: "",
        academic_session_id: currentSession?.id || "",
        effective_date: localDateInputValue(),
        outcome: "reclassified",
        reason: "",
      },
    }));
  };

  const submitClassChange = async (event) => {
    event.preventDefault();
    if (!historyState?.form) return;
    const { student, form } = historyState;
    if (!form.target_class_id || !form.academic_session_id || form.reason.trim().length < 3) {
      setFieldErrors({
        target_class_id: form.target_class_id ? undefined : "Choose a class.",
        academic_session_id: form.academic_session_id ? undefined : "Choose a session.",
        reason: form.reason.trim().length >= 3 ? undefined : "Enter a reason.",
      });
      return;
    }
    setBusyId(student.id);
    try {
      await studentService.changeStudentClass(student.id, {
        ...form,
        reason: form.reason.trim(),
      });
      const response = await studentService.getEnrollmentHistory(student.id);
      setHistoryState({ student, loading: false, items: asItems(response), mode: "history", form: null });
      showSuccess("Student class changed and enrollment history updated.");
      await refresh();
    } catch (requestError) {
      const parsed = parseApiError(requestError, "Failed to change student class.");
      setFieldErrors(parsed.fieldErrors || {});
      showError(parsed.message);
    } finally {
      setBusyId("");
    }
  };

  const inspectHardDelete = async (student) => {
    setHardDeleteState({ student, loading: true, eligibility: null, reason: "", confirmation: "" });
    try {
      const eligibility = await studentService.getHardDeleteEligibility(student.id);
      setHardDeleteState({ student, loading: false, eligibility, reason: "", confirmation: "" });
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to inspect delete eligibility.").message);
      setHardDeleteState(null);
    }
  };

  const submitHardDelete = async (event) => {
    event.preventDefault();
    if (!hardDeleteState?.eligibility?.eligible) return;
    if (hardDeleteState.confirmation !== "DELETE_UNUSED_STUDENT" || hardDeleteState.reason.trim().length < 3) {
      showWarning("Enter the exact confirmation text and a reason.");
      return;
    }
    setBusyId(hardDeleteState.student.id);
    try {
      await studentService.hardDeleteStudent(hardDeleteState.student.id, {
        confirmation: "DELETE_UNUSED_STUDENT",
        reason: hardDeleteState.reason.trim(),
      });
      showSuccess("Unused student record permanently deleted.");
      setHardDeleteState(null);
      await refresh();
    } catch (requestError) {
      showError(parseApiError(requestError, "Failed to hard-delete student.").message);
    } finally {
      setBusyId("");
    }
  };

  const clearFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  };

  if (loading && students.length === 0 && !error) {
    return <LoadingState label="Loading students..." />;
  }

  return (
    <div className="space-y-5">
      <StudentAccessCodeSlipModal
        notice={accessNotice}
        onClose={() => setAccessNotice(null)}
        onCopied={() => showSuccess("Access code copied.")}
        onCopyFailed={() => showError("Could not copy access details.")}
        onPrintFailed={() => showError("Could not open the print window.")}
      />

      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
          {error}
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="section-title">Students</h2>
          <p className="mt-1 text-sm text-text-muted">Create and manage student records.</p>
        </div>
        <Button type="button" onClick={() => navigate("/admin/students/create")}>
          <PlusCircle className="h-4 w-4" />
          Create student
        </Button>
      </div>

      <Card className="p-4 sm:p-5">
        <form onSubmit={(event) => event.preventDefault()} className="grid gap-3 md:grid-cols-4 xl:grid-cols-5">
          <Input
            label="Search"
            value={draftFilters.search}
            placeholder="Name or admission number"
            onChange={(event) => setDraftFilters((current) => ({ ...current, search: event.target.value }))}
          />
          <SelectField
            label="Class"
            value={draftFilters.classId}
            onChange={(event) => setDraftFilters((current) => ({ ...current, classId: event.target.value }))}
            options={classOptions}
            placeholder="All classes"
          />
          <SelectField
            label="Status"
            value={draftFilters.status}
            onChange={(event) => setDraftFilters((current) => ({ ...current, status: event.target.value }))}
            options={STUDENT_STATUSES.map((value) => ({ value, label: titleCase(value) }))}
            placeholder="All statuses"
          />
          <label className="flex min-h-11 items-center gap-2 self-end rounded-xl border border-border px-3 text-sm font-semibold text-text-soft">
            <input
              type="checkbox"
              checked={draftFilters.includeArchived}
              onChange={(event) => setDraftFilters((current) => ({ ...current, includeArchived: event.target.checked }))}
            />
            Include archived
          </label>
          <div className="grid gap-2 self-end">
            <Button type="button" size="small" variant="outline" onClick={clearFilters}>Clear</Button>
          </div>
        </form>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-muted">
          {total} student record{total === 1 ? "" : "s"}
        </p>
        <p className="text-sm text-text-muted">Page {page} of {pageCount}</p>
      </div>

      {students.length === 0 ? (
        <Card className="p-6">
          <EmptyState 
            title="No students found" 
            description="Adjust the filters or create a student." 
            actionLabel="Create student"
            onAction={() => navigate("/admin/students/create")}
          />
        </Card>
      ) : (
        <section className="directory-card-grid mobile-scroll-list grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {students.map((student) => (
            <StudentCard
              key={student.id}
              student={student}
              busy={busyId === student.id}
              onEdit={openEdit}
              onReset={setAccessCodeConfirmation}
              onHistory={openHistory}
              onLifecycle={openLifecycle}
              onHardDelete={inspectHardDelete}
            />
          ))}
        </section>
      )}

      <div className="mobile-list-pagination flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-text-muted sm:hidden">
          Page {page}/{pageCount}
        </span>
        <div className="ml-auto grid grid-cols-2 gap-2 sm:flex">
        <Button
          type="button"
          variant="outline"
          size="small"
          disabled={page <= 1 || loading}
          onClick={() => setPage((current) => Math.max(1, current - 1))}
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="small"
          disabled={page >= pageCount || loading}
          onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
        </div>
      </div>

      <Modal
        open={Boolean(editState)}
        title="Edit student profile"
        description="Update profile fields. Empty optional fields are cleared explicitly."
        onClose={() => !busyId && setEditState(null)}
        closeOnOverlay={!busyId}
      >
        {editState ? (
          <form onSubmit={submitEdit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="First name" value={editState.form.first_name} required error={fieldErrors.first_name} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, first_name: event.target.value } }))} />
              <Input label="Last name" value={editState.form.last_name} required error={fieldErrors.last_name} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, last_name: event.target.value } }))} />
              <SelectField label="Gender" value={editState.form.gender} options={GENDER_OPTIONS.map((value) => ({ value, label: titleCase(value) }))} error={fieldErrors.gender} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, gender: event.target.value } }))} />
              <Input label="Date of birth" type="date" value={editState.form.date_of_birth} required error={fieldErrors.date_of_birth} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, date_of_birth: event.target.value } }))} />
              <Input label="State of origin" value={editState.form.state_of_origin} error={fieldErrors.state_of_origin} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, state_of_origin: event.target.value } }))} />
              <Input label="Arm" value={editState.form.arm} error={fieldErrors.arm} onChange={(event) => setEditState((current) => ({ ...current, form: { ...current.form, arm: event.target.value } }))} />
            </div>
            <p className="rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
              To change this student's class, open Class history and use Change class so the placement history is updated.
            </p>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" disabled={Boolean(busyId)} onClick={() => setEditState(null)}>Cancel</Button>
              <Button type="submit" disabled={Boolean(busyId)}>{busyId ? "Saving..." : "Save changes"}</Button>
            </div>
          </form>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(accessCodeConfirmation)}
        title="Generate new access code"
        description={accessCodeConfirmation ? `Generate a new one-time access code for ${displayName(accessCodeConfirmation)}.` : ""}
        onClose={() => !busyId && setAccessCodeConfirmation(null)}
        closeOnOverlay={!busyId}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" disabled={Boolean(busyId)} onClick={() => setAccessCodeConfirmation(null)}>
              Cancel
            </Button>
            <Button type="button" disabled={Boolean(busyId)} onClick={() => resetAccessCode(accessCodeConfirmation)}>
              {busyId ? "Generating..." : "Generate code"}
            </Button>
          </div>
        }
      >
        <p className="text-sm leading-6 text-text-muted">
          The old reset code will no longer be useful once a new one is generated. The student's records and class history are not changed.
        </p>
      </Modal>

      <Modal
        open={Boolean(lifecycleState)}
        title={lifecycleState ? lifecycleConfig[lifecycleState.actionKey].label : "Student lifecycle"}
        description="This action is recorded against the student lifecycle."
        onClose={() => !busyId && setLifecycleState(null)}
        closeOnOverlay={!busyId}
      >
        {lifecycleState ? (
          <form onSubmit={submitLifecycle} className="space-y-4">
            <div className="rounded-xl bg-surface-muted/40 px-4 py-3 text-sm">
              <p className="font-semibold text-text">{displayName(lifecycleState.student)}</p>
              <p className="mt-1 text-text-muted">{lifecycleState.student.admission_number}</p>
            </div>
            {lifecycleConfig[lifecycleState.actionKey].usesEffectiveDate ? (
              <Input label="Effective date" type="date" value={lifecycleState.form.effective_date} required error={fieldErrors.effective_date} onChange={(event) => setLifecycleState((current) => ({ ...current, form: { ...current.form, effective_date: event.target.value } }))} />
            ) : null}
            {lifecycleConfig[lifecycleState.actionKey].usesGraduationDate ? (
              <Input label="Graduation date" type="date" value={lifecycleState.form.graduation_date} required error={fieldErrors.graduation_date} onChange={(event) => setLifecycleState((current) => ({ ...current, form: { ...current.form, graduation_date: event.target.value } }))} />
            ) : null}
            {lifecycleConfig[lifecycleState.actionKey].usesClassSession ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <SelectField label="Target class" value={lifecycleState.form.target_class_id} options={classOptions} required error={fieldErrors.target_class_id} onChange={(event) => setLifecycleState((current) => ({ ...current, form: { ...current.form, target_class_id: event.target.value } }))} />
                <SelectField label="Academic session" value={lifecycleState.form.academic_session_id} options={sessionOptions} required error={fieldErrors.academic_session_id} onChange={(event) => setLifecycleState((current) => ({ ...current, form: { ...current.form, academic_session_id: event.target.value } }))} />
              </div>
            ) : null}
            {lifecycleConfig[lifecycleState.actionKey].usesPromotionHold ? (
              <label className="flex items-center gap-2 rounded-xl border border-border px-3 py-3 text-sm text-text-soft">
                <input type="checkbox" checked={lifecycleState.form.promotion_hold} onChange={(event) => setLifecycleState((current) => ({ ...current, form: { ...current.form, promotion_hold: event.target.checked } }))} />
                Keep the student on promotion hold while suspended
              </label>
            ) : null}
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">Reason</span>
              <textarea className="input-base min-h-28" value={lifecycleState.form.reason} maxLength={500} onChange={(event) => setLifecycleState((current) => ({ ...current, form: { ...current.form, reason: event.target.value } }))} />
              {fieldErrors.reason ? <span className="mt-1 block text-xs text-error">{fieldErrors.reason}</span> : null}
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" disabled={Boolean(busyId)} onClick={() => setLifecycleState(null)}>Cancel</Button>
              <Button type="submit" variant={lifecycleConfig[lifecycleState.actionKey].variant} disabled={Boolean(busyId)}>{busyId ? "Saving..." : "Confirm"}</Button>
            </div>
          </form>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(historyState)}
        title="Class placement history"
        description={historyState ? `${displayName(historyState.student)} · ${historyState.student.admission_number}` : ""}
        onClose={() => !busyId && setHistoryState(null)}
        closeOnOverlay={!busyId}
      >
        {historyState?.loading ? (
          <LoadingState label="Loading enrollment history..." />
        ) : historyState?.mode === "change" ? (
          <form onSubmit={submitClassChange} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField label="Target class" value={historyState.form.target_class_id} options={classOptions} required error={fieldErrors.target_class_id} onChange={(event) => setHistoryState((current) => ({ ...current, form: { ...current.form, target_class_id: event.target.value } }))} />
              <SelectField label="Academic session" value={historyState.form.academic_session_id} options={sessionOptions} required error={fieldErrors.academic_session_id} onChange={(event) => setHistoryState((current) => ({ ...current, form: { ...current.form, academic_session_id: event.target.value } }))} />
              <Input label="Effective date" type="date" value={historyState.form.effective_date} required onChange={(event) => setHistoryState((current) => ({ ...current, form: { ...current.form, effective_date: event.target.value } }))} />
              <SelectField label="Outcome" value={historyState.form.outcome} required options={[{ value: "reclassified", label: "Reclassified" }, { value: "repeated", label: "Repeated" }]} onChange={(event) => setHistoryState((current) => ({ ...current, form: { ...current.form, outcome: event.target.value } }))} />
            </div>
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">Reason</span>
              <textarea className="input-base min-h-24" value={historyState.form.reason} onChange={(event) => setHistoryState((current) => ({ ...current, form: { ...current.form, reason: event.target.value } }))} />
              {fieldErrors.reason ? <span className="mt-1 block text-xs text-error">{fieldErrors.reason}</span> : null}
            </label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setHistoryState((current) => ({ ...current, mode: "history", form: null }))}>Back</Button>
              <Button type="submit" disabled={Boolean(busyId)}>{busyId ? "Saving..." : "Change class"}</Button>
            </div>
          </form>
        ) : historyState ? (
          <div className="space-y-4">
            <div className="flex justify-end">
              <Button type="button" size="small" onClick={startClassChange}>Change class</Button>
            </div>
            {historyState.items.length === 0 ? (
              <EmptyState title="No enrollment history" description="No class-placement records were returned." />
            ) : (
              <div className="divide-y divide-border overflow-hidden rounded-2xl border border-border">
                {historyState.items.map((item) => (
                  <div key={item.id} className="grid gap-2 px-4 py-3 sm:grid-cols-[1fr_auto]">
                    <div>
                      <p className="font-semibold text-text">{[item.class_name, item.class_arm].filter(Boolean).join(" ") || item.class_id}</p>
                      <p className="mt-1 text-xs text-text-muted">{item.academic_session_name || item.academic_session_id} · {titleCase(item.outcome)}</p>
                    </div>
                    <div className="text-sm text-text-muted sm:text-right">
                      <p>{formatDate(item.started_on)} – {item.is_current ? "Current" : formatDate(item.ended_on)}</p>
                      {item.reason ? <p className="mt-1 text-xs">{item.reason}</p> : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(hardDeleteState)}
        title="Hard-delete eligibility"
        description="Permanent deletion is only allowed for accidental records with no historical dependencies."
        onClose={() => !busyId && setHardDeleteState(null)}
        closeOnOverlay={!busyId}
      >
        {hardDeleteState?.loading ? (
          <LoadingState label="Checking dependencies..." />
        ) : hardDeleteState ? (
          <form onSubmit={submitHardDelete} className="space-y-4">
            {hardDeleteState.eligibility?.eligible ? (
              <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-800">
                This record has no protected dependencies and is eligible for permanent deletion.
              </div>
            ) : (
              <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
                Permanent deletion is blocked by: {(hardDeleteState.eligibility?.blocking_dependencies || []).join(", ") || "historical dependencies"}. Archive the record instead.
              </div>
            )}
            {hardDeleteState.eligibility?.eligible ? (
              <>
                <Input label="Type DELETE_UNUSED_STUDENT" value={hardDeleteState.confirmation} onChange={(event) => setHardDeleteState((current) => ({ ...current, confirmation: event.target.value }))} />
                <label className="block">
                  <span className="mb-1.5 block text-sm font-semibold text-text-soft">Reason</span>
                  <textarea className="input-base min-h-24" value={hardDeleteState.reason} onChange={(event) => setHardDeleteState((current) => ({ ...current, reason: event.target.value }))} />
                </label>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setHardDeleteState(null)}>Cancel</Button>
                  <Button type="submit" variant="danger" disabled={Boolean(busyId)}>{busyId ? "Deleting..." : "Permanently delete"}</Button>
                </div>
              </>
            ) : null}
          </form>
        ) : null}
      </Modal>
    </div>
  );
}

export default StudentDirectoryPage;
