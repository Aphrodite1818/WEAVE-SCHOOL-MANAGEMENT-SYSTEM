import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Archive,
  Ban,
  ChevronRight,
  Filter,
  GraduationCap,
  MoreHorizontal,
  PlusCircle,
  RotateCcw,
  ShieldOff,
  Undo2,
  UserCheck,
  UserMinus,
  UserRound,
  X,
} from "lucide-react";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StudentAccessCodeSlipModal from "../../components/students/StudentAccessCodeSlipModal";
import Modal from "../../components/ui/Modal";
import Dropdown from "../../components/ui/Dropdown";
import { classService } from "../../services/academicsService";
import academicService from "../../services/academicService";
import { parseApiError } from "../../services/api";
import { studentService } from "../../services/studentService";
import { useToast } from "../../hooks/useToast";
import { displayName } from "../../utils/user";

const STUDENT_STATUSES = ["active", "suspended", "withdrawn", "graduated", "expelled"];
const GENDER_OPTIONS = ["male", "female"];

const INITIAL_EDIT_FORM = {
  first_name: "",
  last_name: "",
  gender: "",
  date_of_birth: "",
  state_of_origin: "",
  arm: "",
};

const todayInputValue = () => new Date().toISOString().slice(0, 10);

const INITIAL_LIFECYCLE_FORM = {
  reason: "",
  effective_date: todayInputValue(),
  graduation_date: todayInputValue(),
  promotion_hold: true,
  target_class_id: "",
  academic_session_id: "",
};

const lifecycleActions = {
  suspend: {
    label: "Suspend",
    title: "Suspend student",
    description: "Temporarily remove normal academic progression while keeping the student record visible.",
    icon: Ban,
    variant: "outline",
    serviceMethod: "suspendStudent",
    success: "Student suspended.",
    requiresPromotionHold: true,
  },
  reinstate: {
    label: "Reinstate",
    title: "Reinstate student",
    description: "Return a suspended student to active academic status.",
    icon: UserCheck,
    variant: "success",
    serviceMethod: "reinstateStudent",
    success: "Student reinstated.",
  },
  reinstateExpelled: {
    label: "Reinstate expelled",
    title: "Reinstate expelled student",
    description: "Restore an expelled student into a class and academic session.",
    icon: UserCheck,
    variant: "success",
    serviceMethod: "reinstateExpelledStudent",
    success: "Expelled student reinstated.",
    requiresClassSession: true,
    requiresEffectiveDate: true,
  },
  withdraw: {
    label: "Withdraw",
    title: "Withdraw student",
    description: "Close the current enrollment and preserve read-only historical access where applicable.",
    icon: UserMinus,
    variant: "outline",
    serviceMethod: "withdrawStudent",
    success: "Student withdrawn.",
    requiresEffectiveDate: true,
  },
  expel: {
    label: "Expel",
    title: "Expel student",
    description: "End access immediately and record the disciplinary lifecycle transition.",
    icon: ShieldOff,
    variant: "danger",
    serviceMethod: "expelStudent",
    success: "Student expelled.",
    requiresEffectiveDate: true,
  },
  graduate: {
    label: "Graduate",
    title: "Graduate student",
    description: "Mark the student as graduated and close the current enrollment.",
    icon: GraduationCap,
    variant: "outline",
    serviceMethod: "graduateStudent",
    success: "Student graduated.",
    requiresGraduationDate: true,
  },
  archive: {
    label: "Archive",
    title: "Archive student",
    description: "Hide the student from operational lists without deleting history.",
    icon: Archive,
    variant: "danger",
    serviceMethod: "archiveStudent",
    success: "Student archived.",
  },
  restore: {
    label: "Restore",
    title: "Restore archived student",
    description: "Return an archived record to operational visibility.",
    icon: Undo2,
    variant: "success",
    serviceMethod: "restoreStudent",
    success: "Student restored.",
  },
};

const INITIAL_FILTERS = {
  search: "",
  classId: "",
  status: "",
};

const titleCase = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const optionalValue = (value, fallback = "Not provided") => value || fallback;

const formatDateValue = (value) => {
  if (!value) return "Not set";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const className = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || item?.id || "Unknown class";

const studentClassLabel = (student) =>
  [student?.class_name, student?.class_arm].filter(Boolean).join(" ") || "Not assigned";

const enumOptions = (values) =>
  values.map((value) => ({ value, label: titleCase(value) }));

const optionsFrom = (items, labelFn) =>
  (items || []).map((item) => ({ value: item.id, label: labelFn(item) }));

const compactPayload = (payload) =>
  Object.entries(payload).reduce((nextPayload, [key, value]) => {
    nextPayload[key] = value === "" ? null : value;
    return nextPayload;
  }, {});

const currentSessionId = (sessions) =>
  sessions.find((item) => item.is_current)?.id || sessions[0]?.id || "";

const lifecycleOptionsForStudent = (student) => {
  if (student?.is_archived) return ["restore"];

  const status = String(student?.status || "").toLowerCase();
  const actions = ["archive"];

  if (status === "active") {
    actions.unshift("suspend", "withdraw", "expel", "graduate");
  } else if (status === "suspended") {
    actions.unshift("reinstate", "withdraw", "expel");
  } else if (status === "expelled") {
    actions.unshift("reinstateExpelled");
  }

  return actions;
};

function SelectControl({ label, name, value, options, placeholder, onChange, error }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-text-soft">
        {label}
      </label>
      <select className="input-base" name={name} value={value || ""} onChange={onChange}>
        <option value="">{placeholder || "Select an option"}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <p className="mt-1 text-sm text-error">{error}</p>}
    </div>
  );
}

function statusBadge(value, variant = "default") {
  return <Badge variant={variant}>{titleCase(value || "unknown")}</Badge>;
}

function archiveBadge(student) {
  if (!student?.is_archived) return null;
  return <Badge variant="error">Archived</Badge>;
}

function StudentLifecycleDropdown({
  student,
  busyId,
  onLifecycleAction,
  className = "",
}) {
  const [open, setOpen] = useState(false);
  const actions = lifecycleOptionsForStudent(student);
  const studentBusy = Boolean(busyId?.endsWith(student.id));
  const menuItemClass =
    "flex min-h-10 w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold text-text-soft transition hover:bg-surface-muted/70 hover:text-text disabled:cursor-not-allowed disabled:opacity-50";
  const dangerItemClass =
    "flex min-h-10 w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold text-error transition hover:bg-error-soft disabled:cursor-not-allowed disabled:opacity-50";

  const runAndClose = (handler) => {
    setOpen(false);
    handler();
  };

  return (
    <Dropdown
      align="right"
      open={open}
      onOpenChange={setOpen}
      strategy="fixed"
      className="w-64"
      trigger={
        <Button
          type="button"
          variant="outline"
          size="small"
          disabled={studentBusy}
          className={`w-full justify-between ${className}`}
        >
          <span>Lifecycle actions</span>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      }
    >
      <div className="grid gap-1">
        {actions.map((actionKey) => {
          const action = lifecycleActions[actionKey];
          const Icon = action.icon;
          const busy = busyId === `${actionKey}:${student.id}`;
          const isDanger = ["expel", "archive"].includes(actionKey);

          return (
            <button
              key={actionKey}
              type="button"
              className={isDanger ? dangerItemClass : menuItemClass}
              disabled={busy || studentBusy}
              onClick={() => runAndClose(() => onLifecycleAction(student, actionKey))}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{busy ? "Saving..." : action.label}</span>
            </button>
          );
        })}
      </div>
    </Dropdown>
  );
}

function StudentFact({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-[0.6875rem] font-semibold uppercase text-text-muted">
        {label}
      </p>
      <p className="mt-1 break-words text-sm font-medium text-text-soft">
        {value}
      </p>
    </div>
  );
}

function StudentCard({
  student,
  busyId,
  onEdit,
  onResetAccessCode,
  onLifecycleAction,
}) {
  const studentBusy = Boolean(busyId?.endsWith(student.id));

  return (
    <Card className="flex min-h-[19rem] flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
            <UserRound className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="break-words font-semibold text-text">
              {displayName(student)}
            </p>
            <p className="mt-1 break-words text-xs text-text-muted">
              {optionalValue(student.admission_number, "Pending")}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {statusBadge(
            student.status,
            student.status === "active" ? "success" : "default",
          )}
          {archiveBadge(student)}
        </div>
      </div>

      <div className="mt-4 grid gap-3 rounded-2xl bg-surface-muted/30 px-4 py-3 sm:grid-cols-2">
        <StudentFact label="Admission date" value={formatDateValue(student.admission_date)} />
        <StudentFact label="Class" value={studentClassLabel(student)} />
        <StudentFact
          label="Password reset"
          value={student.password_reset_required ? "Required" : "Completed"}
        />
        <StudentFact label="Profile" value={titleCase(student.profile_status || "unknown")} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {student.promotion_hold ? <Badge variant="warning">Promotion hold</Badge> : null}
        {statusBadge(student.profile_status, student.profile_status === "incomplete" ? "warning" : "success")}
      </div>

      <div className="mt-auto pt-4">
        <div className="grid gap-2 sm:grid-cols-2">
          <Button
            type="button"
            variant="outline"
            size="small"
            onClick={() => onEdit(student)}
            disabled={studentBusy}
            className="w-full"
          >
            Edit profile
          </Button>
          <Button
            type="button"
            variant="outline"
            size="small"
            onClick={() => onResetAccessCode(student)}
            disabled={busyId === `reset:${student.id}`}
            className="w-full"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            {busyId === `reset:${student.id}` ? "Generating..." : "Reset code"}
          </Button>
        </div>

        <div className="mt-3">
          <StudentLifecycleDropdown
            student={student}
            busyId={busyId}
            onLifecycleAction={onLifecycleAction}
          />
        </div>
      </div>
    </Card>
  );
}

function buildResetNotice(student) {
  const accessCode = student?.setup_code || student?.access_code;
  if (!student || !accessCode) return null;

  return {
    title: "Student access code reset",
    description: "Give this code to the student so they can log in and create a new password.",
    fields: [
      { label: "Student", value: student.full_name || displayName(student) },
      { label: "Admission number", value: student.admission_number },
      { label: "Access code", value: accessCode },
      { label: "Expires", value: formatDateValue(student.access_code_expires_at || student.expires_at) },
    ],
  };
}

function StudentDirectoryPage() {
  const { showSuccess, showError } = useToast();
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [formData, setFormData] = useState(INITIAL_EDIT_FORM);
  const [editingStudent, setEditingStudent] = useState(null);
  const [lifecycleAction, setLifecycleAction] = useState(null);
  const [lifecycleForm, setLifecycleForm] = useState(INITIAL_LIFECYCLE_FORM);
  const [accessCodeNotice, setAccessCodeNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFilterSheetOpen, setIsFilterSheetOpen] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  const classOptions = useMemo(() => optionsFrom(classes, className), [classes]);

  const loadPage = useCallback(
    async (activeFilters = filters) => {
      setIsLoading(true);
      setError(null);

      try {
        const [classResult, sessionResult, studentResult] = await Promise.all([
          classService.getClasses({ limit: 100 }),
          academicService.listSessions({ limit: 100 }),
          studentService.getAdminStudents({
            limit: 100,
            search: activeFilters.search,
            classId: activeFilters.classId,
            status: activeFilters.status,
          }),
        ]);

        setClasses(Array.isArray(classResult?.items) ? classResult.items : []);
        setSessions(Array.isArray(sessionResult?.items) ? sessionResult.items : []);
        setStudents(Array.isArray(studentResult?.items) ? studentResult.items : []);
        setTotal(Number.isFinite(studentResult?.total) ? studentResult.total : studentResult?.items?.length || 0);
      } catch (err) {
        const parsed = parseApiError(err, "Failed to load students.");
        setError(parsed.message);
      } finally {
        setIsLoading(false);
      }
    },
    [filters]
  );

  useEffect(() => {
    loadPage();
  }, [loadPage]);

  const resetEditForm = () => {
    setEditingStudent(null);
    setFormData(INITIAL_EDIT_FORM);
    setFieldErrors({});
  };

  const handleFormChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleFilterChange = (event) => {
    const { name, value } = event.target;
    setFilters((current) => ({ ...current, [name]: value }));
  };

  const handleEdit = (student) => {
    setEditingStudent(student);
    setFieldErrors({});
    setFormData({
      first_name: student.first_name || "",
      last_name: student.last_name || "",
      gender: student.gender || "",
      date_of_birth: student.date_of_birth || "",
      state_of_origin: student.state_of_origin || "",
      arm: student.arm || "",
    });
  };

  const openLifecycleAction = (student, actionKey) => {
    setFieldErrors({});
    setLifecycleAction({ student, actionKey });
    setLifecycleForm({
      ...INITIAL_LIFECYCLE_FORM,
      effective_date: todayInputValue(),
      graduation_date: todayInputValue(),
      target_class_id: student.class_id || classes[0]?.id || "",
      academic_session_id: currentSessionId(sessions),
    });
  };

  const closeLifecycleAction = () => {
    if (isSubmitting) return;
    setLifecycleAction(null);
    setLifecycleForm(INITIAL_LIFECYCLE_FORM);
    setFieldErrors({});
  };

  const handleLifecycleFormChange = (event) => {
    const { name, type, checked, value } = event.target;
    setLifecycleForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
    setFieldErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!editingStudent) return;

    setIsSubmitting(true);
    setFieldErrors({});

    try {
      await studentService.updateAdminStudent(editingStudent.id, compactPayload(formData));
      showSuccess("Student updated successfully.");
      resetEditForm();
      await loadPage();
    } catch (err) {
      const parsed = parseApiError(err, "Failed to update student.");
      setFieldErrors(parsed.fieldErrors || {});
      showError(parsed.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitLifecycleAction = async (event) => {
    event.preventDefault();
    if (!lifecycleAction) return;

    const { student, actionKey } = lifecycleAction;
    const action = lifecycleActions[actionKey];
    const reason = lifecycleForm.reason.trim();
    if (reason.length < 3) {
      setFieldErrors({ reason: "Enter a reason with at least three characters." });
      return;
    }

    const payload = { reason };
    if (action.requiresPromotionHold) {
      payload.promotion_hold = lifecycleForm.promotion_hold;
    }
    if (action.requiresEffectiveDate) {
      payload.effective_date = lifecycleForm.effective_date;
    }
    if (action.requiresGraduationDate) {
      payload.graduation_date = lifecycleForm.graduation_date;
    }
    if (action.requiresClassSession) {
      payload.target_class_id = lifecycleForm.target_class_id;
      payload.academic_session_id = lifecycleForm.academic_session_id;
      if (!payload.target_class_id || !payload.academic_session_id) {
        setFieldErrors({
          target_class_id: !payload.target_class_id ? "Choose the target class." : undefined,
          academic_session_id: !payload.academic_session_id ? "Choose the academic session." : undefined,
        });
        return;
      }
    }

    setIsSubmitting(true);
    setBusyId(`${actionKey}:${student.id}`);
    setFieldErrors({});

    try {
      await studentService[action.serviceMethod](student.id, payload);
      showSuccess(action.success);
      if (editingStudent?.id === student.id) resetEditForm();
      setLifecycleAction(null);
      setLifecycleForm(INITIAL_LIFECYCLE_FORM);
      await loadPage();
    } catch (err) {
      const parsed = parseApiError(err, `Failed to ${action.label.toLowerCase()} student.`);
      setFieldErrors(parsed.fieldErrors || {});
      showError(parsed.message);
    } finally {
      setIsSubmitting(false);
      setBusyId(null);
    }
  };

  const handleResetAccessCode = async (student) => {
    const label = displayName(student) || student.admission_number || "this student";
    if (!window.confirm(`Generate a new access code for ${label}? The old password will stop working.`)) return;

    setBusyId(`reset:${student.id}`);
    try {
      const result = await studentService.resetStudentAccessCode(student.id);
      const notice = buildResetNotice(result);
      if (notice) setAccessCodeNotice(notice);
      showSuccess("Student access code generated successfully.");
      await loadPage();
    } catch (err) {
      const parsed = parseApiError(err, "Failed to reset student access code.");
      showError(parsed.message);
    } finally {
      setBusyId(null);
    }
  };

  const applyFilters = async (event) => {
    event?.preventDefault();
    await loadPage(filters);
    setIsFilterSheetOpen(false);
  };

  const clearFilters = () => {
    setFilters(INITIAL_FILTERS);
    loadPage(INITIAL_FILTERS);
  };

  if (isLoading && students.length === 0 && !error) {
    return <LoadingState label="Loading students..." fullPage />;
  }

  return (
    <div className="resource-page-shell w-full max-w-none space-y-5 sm:mx-auto sm:max-w-7xl">
      <StudentAccessCodeSlipModal
        notice={accessCodeNotice}
        onClose={() => setAccessCodeNotice(null)}
        onCopied={() => showSuccess("Access code details copied.")}
        onCopyFailed={() => showError("Could not copy details automatically. Please copy them manually.")}
        onPrintFailed={() => showError("Could not open the print window. Check your browser popup setting.")}
      />

      <Modal
        open={Boolean(lifecycleAction)}
        title={lifecycleAction ? lifecycleActions[lifecycleAction.actionKey].title : "Student lifecycle"}
        description={lifecycleAction ? lifecycleActions[lifecycleAction.actionKey].description : ""}
        onClose={closeLifecycleAction}
        closeOnOverlay={!isSubmitting}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" disabled={isSubmitting} onClick={closeLifecycleAction}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="student-lifecycle-form"
              variant={lifecycleAction ? lifecycleActions[lifecycleAction.actionKey].variant : "primary"}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Saving..." : "Confirm lifecycle change"}
            </Button>
          </div>
        }
      >
        {lifecycleAction ? (
          <form id="student-lifecycle-form" onSubmit={submitLifecycleAction} className="space-y-4">
            <div className="rounded-xl border border-border bg-surface-muted/30 px-4 py-3">
              <p className="text-sm font-semibold text-text">
                {displayName(lifecycleAction.student)}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                {optionalValue(lifecycleAction.student.admission_number, "Pending")} | {titleCase(lifecycleAction.student.status)}
              </p>
            </div>

            {lifecycleActions[lifecycleAction.actionKey].requiresEffectiveDate ? (
              <Input
                label="Effective date"
                type="date"
                name="effective_date"
                value={lifecycleForm.effective_date}
                onChange={handleLifecycleFormChange}
                error={fieldErrors.effective_date}
                required
              />
            ) : null}

            {lifecycleActions[lifecycleAction.actionKey].requiresGraduationDate ? (
              <Input
                label="Graduation date"
                type="date"
                name="graduation_date"
                value={lifecycleForm.graduation_date}
                onChange={handleLifecycleFormChange}
                error={fieldErrors.graduation_date}
                required
              />
            ) : null}

            {lifecycleActions[lifecycleAction.actionKey].requiresClassSession ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <SelectControl
                  label="Target class"
                  name="target_class_id"
                  value={lifecycleForm.target_class_id}
                  options={classOptions}
                  placeholder="Select class"
                  onChange={handleLifecycleFormChange}
                  error={fieldErrors.target_class_id}
                />
                <SelectControl
                  label="Academic session"
                  name="academic_session_id"
                  value={lifecycleForm.academic_session_id}
                  options={optionsFrom(sessions, (item) => item.name || item.id)}
                  placeholder="Select session"
                  onChange={handleLifecycleFormChange}
                  error={fieldErrors.academic_session_id}
                />
              </div>
            ) : null}

            {lifecycleActions[lifecycleAction.actionKey].requiresPromotionHold ? (
              <label className="flex items-start gap-3 rounded-xl border border-border bg-surface-muted/30 px-4 py-3 text-sm text-text-soft">
                <input
                  type="checkbox"
                  name="promotion_hold"
                  checked={lifecycleForm.promotion_hold}
                  onChange={handleLifecycleFormChange}
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary/20"
                />
                <span>
                  <span className="block font-semibold text-text">Hold promotion while suspended</span>
                  <span className="mt-0.5 block text-xs text-text-muted">
                    Keeps the student out of automatic progression until they are reinstated.
                  </span>
                </span>
              </label>
            ) : null}

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-text-soft">Reason</span>
              <textarea
                name="reason"
                value={lifecycleForm.reason}
                onChange={handleLifecycleFormChange}
                rows={4}
                maxLength={500}
                className="input-base min-h-28 resize-y"
                placeholder="Record why this lifecycle change is being made."
                required
              />
              {fieldErrors.reason ? (
                <p className="mt-1.5 text-xs font-medium text-error">{fieldErrors.reason}</p>
              ) : null}
            </label>
          </form>
        ) : null}
      </Modal>

      {error && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      )}

      <div className={`resource-page-grid grid w-full min-w-0 gap-5 ${editingStudent ? "2xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]" : ""}`}>
        {editingStudent && (
          <Card className="resource-page-form-card p-4 sm:p-5 2xl:sticky 2xl:top-28 2xl:self-start">
            <h2 className="text-lg font-semibold">Edit student</h2>
            <p className="mt-1 text-sm text-text-muted">
              Update school-managed student details.
            </p>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <Input label="First name" name="first_name" value={formData.first_name} onChange={handleFormChange} error={fieldErrors.first_name} required />
              <Input label="Last name" name="last_name" value={formData.last_name} onChange={handleFormChange} error={fieldErrors.last_name} required />
              <SelectControl label="Gender" name="gender" value={formData.gender} options={enumOptions(GENDER_OPTIONS)} onChange={handleFormChange} error={fieldErrors.gender} />
              <Input label="Date of birth" type="date" name="date_of_birth" value={formData.date_of_birth} onChange={handleFormChange} error={fieldErrors.date_of_birth} />
              <Input label="State of origin" name="state_of_origin" value={formData.state_of_origin} onChange={handleFormChange} error={fieldErrors.state_of_origin} />
              <Input label="Arm" name="arm" value={formData.arm} onChange={handleFormChange} error={fieldErrors.arm} placeholder="A" />

              <div className="grid gap-2 sm:flex sm:flex-wrap">
                <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
                  {isSubmitting ? "Saving..." : "Save changes"}
                </Button>
                <Button type="button" variant="outline" onClick={resetEditForm} className="w-full sm:w-auto">
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        )}

        <div className="resource-page-list-card space-y-5">
          <Card className="p-4 sm:p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Students</h2>
                <p className="mt-1 text-sm text-text-muted">
                  {total} record{total === 1 ? "" : "s"} found.
                </p>
              </div>
              <Link to="/admin/students/create" className="w-full md:w-auto">
                <Button type="button" className="w-full md:w-auto">
                  <PlusCircle className="h-4 w-4" />
                  Create student
                </Button>
              </Link>
            </div>

            <div className="mt-5 flex items-end gap-2 md:hidden">
              <Input name="search" placeholder="Search students" value={filters.search} onChange={handleFilterChange} />
              <Button type="button" variant="outline" size="icon" onClick={() => setIsFilterSheetOpen(true)} aria-label="Open filters" className="shrink-0">
                <Filter className="h-4 w-4" />
              </Button>
              <Button type="button" size="icon" onClick={() => applyFilters()} aria-label="Apply search" className="shrink-0">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            <form onSubmit={applyFilters} className="resource-page-filters mt-5 hidden gap-3 rounded-2xl border border-border bg-surface-muted/40 p-4 md:grid md:grid-cols-3 2xl:grid-cols-4">
              <Input label="Search" name="search" placeholder="Name or admission no." value={filters.search} onChange={handleFilterChange} />
              <SelectControl label="Class" name="classId" value={filters.classId} options={classOptions} placeholder="All classes" onChange={handleFilterChange} />
              <SelectControl label="Status" name="status" value={filters.status} options={enumOptions(STUDENT_STATUSES)} placeholder="All statuses" onChange={handleFilterChange} />
              <div className="grid gap-2 sm:flex sm:items-end">
                <Button type="submit" size="small" className="w-full sm:w-auto">
                  Apply
                </Button>
                <Button type="button" variant="outline" size="small" onClick={clearFilters} className="w-full sm:w-auto">
                  Clear
                </Button>
              </div>
            </form>
          </Card>

          <div>
            {students.length === 0 ? (
              <Card className="p-5 sm:p-6">
                <EmptyState title="No students found" description="Create students from the student section or adjust your filters." />
              </Card>
            ) : (
              <section className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
                {students.map((student) => (
                  <StudentCard
                    key={student.id}
                    student={student}
                    busyId={busyId}
                    onEdit={handleEdit}
                    onResetAccessCode={handleResetAccessCode}
                    onLifecycleAction={openLifecycleAction}
                  />
                ))}
              </section>
            )}
          </div>
        </div>
      </div>

      {isFilterSheetOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end bg-slate-950/35 px-3 pb-3 pt-16 backdrop-blur-sm md:hidden"
          onClick={() => setIsFilterSheetOpen(false)}
        >
          <div
            className="w-full rounded-2xl border border-border bg-surface p-4 shadow-premium"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Filters</h2>
              <Button type="button" variant="ghost" size="icon" onClick={() => setIsFilterSheetOpen(false)} aria-label="Close filters">
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid gap-3">
              <SelectControl label="Class" name="classId" value={filters.classId} options={classOptions} placeholder="All classes" onChange={handleFilterChange} />
              <SelectControl label="Status" name="status" value={filters.status} options={enumOptions(STUDENT_STATUSES)} placeholder="All statuses" onChange={handleFilterChange} />
              <div className="grid grid-cols-2 gap-2 pt-1">
                <Button type="button" variant="outline" onClick={clearFilters}>
                  Clear
                </Button>
                <Button type="button" onClick={() => applyFilters()}>
                  Apply
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StudentDirectoryPage;
