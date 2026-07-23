import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import StudentAccessCodeSlipModal from "../../components/students/StudentAccessCodeSlipModal";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { formatUsageValue } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { getErrorMessage, parseApiError } from "../../services/api";
import { parentService } from "../../services/parentService";
import { studentService } from "../../services/studentService";
import { teacherService } from "../../services/teacherService";
import { displayName } from "../../utils/user";

const USER_TYPES = ["student", "teacher", "parent"];
const GENDER_OPTIONS = ["male", "female"];
const RELATIONSHIP_OPTIONS = ["father", "mother", "guardian", "sponsor", "other"];

const INITIAL_STUDENT_FORM = {
  first_name: "",
  last_name: "",
  gender: "",
  date_of_birth: "",
  state_of_origin: "",
  class_id: "",
  parents: [{ email: "", relationship_type: "guardian" }],
};

const INITIAL_TEACHER_FORM = {
  email: "",
  job_title: "",
  department: "",
  employment_type: "",
};

const INITIAL_PARENT_FORM = {
  student_id: "",
  email: "",
  relationship_type: "guardian",
};

const TAB_LABELS = {
  student: "Create Student",
  teacher: "Invite Teacher",
  parent: "Invite Parent",
};

const titleCase = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

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

const enumOptions = (values) =>
  values.map((value) => ({ value, label: titleCase(value) }));

const listItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const cleanOptional = (value) => {
  const cleaned = String(value || "").trim();
  return cleaned || null;
};

function TabButton({ active, children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
        active
          ? "bg-primary text-white"
          : "bg-surface text-text-soft hover:bg-surface-muted"
      }`}
    >
      {children}
    </button>
  );
}

function SelectControl({
  label,
  name,
  value,
  options,
  placeholder,
  onChange,
  error,
  required = false,
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-text-soft">{label}</label>
      <select
        name={name}
        value={value || ""}
        onChange={onChange}
        className="input-base"
        required={required}
      >
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

function buildStudentAccessNotice(student) {
  const accessCode = student?.setup_code || student?.access_code;
  if (!student || !accessCode) return null;

  return {
    title: "Student created successfully",
    description: "Give these details to the student for first-time login.",
    fields: [
      { label: "Student", value: student.full_name || displayName(student) },
      { label: "Admission number", value: student.admission_number },
      { label: "Access code", value: accessCode },
      {
        label: "Expires",
        value: formatDateValue(
          student.access_code_expires_at || student.expires_at,
        ),
      },
    ],
  };
}

function CreateUserPage() {
  const [activeTab, setActiveTab] = useState("student");
  const [classOptions, setClassOptions] = useState([]);
  const [studentOptions, setStudentOptions] = useState([]);
  const [studentForm, setStudentForm] = useState(INITIAL_STUDENT_FORM);
  const [teacherForm, setTeacherForm] = useState(INITIAL_TEACHER_FORM);
  const [parentForm, setParentForm] = useState(INITIAL_PARENT_FORM);
  const [isLoadingContext, setIsLoadingContext] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [successPayload, setSuccessPayload] = useState(null);
  const [accessCodeNotice, setAccessCodeNotice] = useState(null);
  const { showSuccess, showError } = useToast();
  const { getResourceGuard, refreshSubscriptionState } = useSubscription();
  const studentGuard = getResourceGuard("students", {
    featureCode: "student_management",
  });
  const teacherGuard = getResourceGuard("teachers", {
    featureCode: "teacher_management",
  });
  const parentGuard = getResourceGuard("parents", {
    featureCode: "parent_portal",
  });
  const activeGuard =
    activeTab === "student"
      ? studentGuard
      : activeTab === "teacher"
        ? teacherGuard
        : parentGuard;

  const selectedStudentLabel = useMemo(() => {
    const selected = studentOptions.find(
      (student) => student.value === parentForm.student_id,
    );
    return selected?.label || "the selected student";
  }, [parentForm.student_id, studentOptions]);

  useEffect(() => {
    let mounted = true;

    async function loadContext() {
      setIsLoadingContext(true);
      try {
        const [classesResponse, studentsResponse] = await Promise.all([
          classService.getClasses({ limit: 100 }),
          studentService.getAdminStudents({ limit: 100, status: "active" }),
        ]);

        if (!mounted) return;

        setClassOptions(
          listItems(classesResponse)
            .filter((item) => item.is_active !== false)
            .map((item) => ({
              value: item.id,
              label:
                [item.name, item.arm].filter(Boolean).join(" ") ||
                "Unnamed class",
            })),
        );
        setStudentOptions(
          listItems(studentsResponse).map((item) => ({
            value: item.id,
            label: `${displayName(item)} · ${item.admission_number}`,
          })),
        );
      } catch (err) {
        if (mounted) {
          setError(getErrorMessage(err, "Failed to load form options."));
        }
      } finally {
        if (mounted) setIsLoadingContext(false);
      }
    }

    loadContext();

    return () => {
      mounted = false;
    };
  }, []);

  const resetErrors = () => {
    setError(null);
    setFieldErrors({});
  };

  const changeTab = (type) => {
    setActiveTab(type);
    setSuccessPayload(null);
    resetErrors();
  };

  const handleStudentChange = (event) => {
    const { name, value } = event.target;
    setStudentForm((current) => ({ ...current, [name]: value }));
    resetErrors();
  };

  const handleStudentParentChange = (index, field, value) => {
    setStudentForm((current) => ({
      ...current,
      parents: current.parents.map((parent, parentIndex) =>
        parentIndex === index ? { ...parent, [field]: value } : parent,
      ),
    }));
    resetErrors();
  };

  const addStudentParent = () => {
    setStudentForm((current) => {
      if (current.parents.length >= 2) return current;
      return {
        ...current,
        parents: [
          ...current.parents,
          { email: "", relationship_type: "guardian" },
        ],
      };
    });
  };

  const removeStudentParent = (index) => {
    setStudentForm((current) => ({
      ...current,
      parents:
        current.parents.length === 1
          ? [{ email: "", relationship_type: "guardian" }]
          : current.parents.filter((_, parentIndex) => parentIndex !== index),
    }));
    resetErrors();
  };

  const handleTeacherChange = (event) => {
    const { name, value } = event.target;
    setTeacherForm((current) => ({ ...current, [name]: value }));
    resetErrors();
  };

  const handleParentChange = (event) => {
    const { name, value } = event.target;
    setParentForm((current) => ({ ...current, [name]: value }));
    resetErrors();
  };

  const buildStudentParents = () => {
    const parents = studentForm.parents
      .map((parent) => ({
        email: parent.email.trim().toLowerCase(),
        relationship_type: parent.relationship_type,
      }))
      .filter((parent) => parent.email);
    const emails = parents.map((parent) => parent.email);

    if (emails.length !== new Set(emails).size) {
      throw new Error("Each parent invitation must use a different email address.");
    }

    return parents;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    resetErrors();
    setSuccessPayload(null);

    try {
      if (activeTab === "student") {
        const parents = buildStudentParents();
        const result = await studentService.createStudent({
          first_name: studentForm.first_name.trim(),
          last_name: studentForm.last_name.trim(),
          gender: cleanOptional(studentForm.gender),
          date_of_birth: studentForm.date_of_birth,
          state_of_origin: cleanOptional(studentForm.state_of_origin),
          class_id: studentForm.class_id,
          parents,
        });
        setStudentForm(INITIAL_STUDENT_FORM);
        setSuccessPayload({ type: "student", result, invitationCount: parents.length });
        setAccessCodeNotice(buildStudentAccessNotice(result));
        showSuccess(
          parents.length > 0
            ? "Student created and parent invitations queued."
            : "Student created successfully.",
        );
        await refreshSubscriptionState({ silent: true });
      } else if (activeTab === "teacher") {
        const result = await teacherService.createInvitation({
          email: teacherForm.email.trim().toLowerCase(),
          job_title: cleanOptional(teacherForm.job_title),
          department: cleanOptional(teacherForm.department),
          employment_type: cleanOptional(teacherForm.employment_type),
        });
        setTeacherForm(INITIAL_TEACHER_FORM);
        setSuccessPayload({ type: "teacher", result });
        showSuccess("Teacher invitation queued successfully.");
      } else {
        const result = await parentService.createInvitation({
          student_id: parentForm.student_id,
          email: parentForm.email.trim().toLowerCase(),
          relationship_type: parentForm.relationship_type,
        });
        setParentForm(INITIAL_PARENT_FORM);
        setSuccessPayload({
          type: "parent",
          result,
          studentLabel: selectedStudentLabel,
        });
        showSuccess("Parent invitation queued successfully.");
      }
    } catch (err) {
      if (!err?.response && err instanceof Error) {
        setError(err.message);
        showError(err.message);
      } else {
        const apiError = parseApiError(
          err,
          activeTab === "student"
            ? "Failed to create student."
            : "Failed to send invitation.",
        );
        setFieldErrors(apiError.fieldErrors);
        setError(apiError.message);
        showError(apiError.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderStudentForm = () => (
    <div className="space-y-5">
      <section className="space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-text">Student identity</h3>
          <p className="mt-1 text-xs leading-5 text-text-muted">
            Admission number and first-login access code are generated by the backend.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="First name"
            name="first_name"
            value={studentForm.first_name}
            onChange={handleStudentChange}
            error={fieldErrors.first_name}
            required
          />
          <Input
            label="Last name"
            name="last_name"
            value={studentForm.last_name}
            onChange={handleStudentChange}
            error={fieldErrors.last_name}
            required
          />
          <SelectControl
            label="Gender"
            name="gender"
            value={studentForm.gender}
            options={enumOptions(GENDER_OPTIONS)}
            onChange={handleStudentChange}
            error={fieldErrors.gender}
          />
          <Input
            label="Date of birth"
            type="date"
            name="date_of_birth"
            value={studentForm.date_of_birth}
            onChange={handleStudentChange}
            error={fieldErrors.date_of_birth}
            required
          />
          <Input
            label="State of origin"
            name="state_of_origin"
            value={studentForm.state_of_origin}
            onChange={handleStudentChange}
            error={fieldErrors.state_of_origin}
          />
        </div>
      </section>

      <section className="border-t border-border/70 pt-5">
        <h3 className="text-sm font-semibold text-text">Academic placement</h3>
        <p className="mt-1 text-xs leading-5 text-text-muted">
          Every new student is assigned to an active class and current academic session.
        </p>
        <div className="mt-4">
          <SelectControl
            label="Class"
            name="class_id"
            value={studentForm.class_id}
            options={classOptions}
            placeholder="Select class"
            onChange={handleStudentChange}
            error={fieldErrors.class_id}
            required
          />
        </div>
      </section>

      <section className="border-t border-border/70 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-text">Parent invitations</h3>
            <p className="mt-1 text-xs leading-5 text-text-muted">
              Add up to two parent emails. Invitation delivery runs through the background email worker.
            </p>
          </div>
          {studentForm.parents.length < 2 ? (
            <Button type="button" variant="outline" size="small" onClick={addStudentParent}>
              <Plus className="h-4 w-4" />
              Add parent
            </Button>
          ) : null}
        </div>

        <div className="mt-4 space-y-3">
          {studentForm.parents.map((parent, index) => (
            <div
              key={`student-parent-${index}`}
              className="rounded-2xl border border-border/70 bg-surface-muted/25 p-4"
            >
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Parent {index + 1}
                </p>
                <button
                  type="button"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-muted transition hover:bg-error-soft hover:text-error"
                  onClick={() => removeStudentParent(index)}
                  aria-label={`Remove parent ${index + 1}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="Parent email"
                  type="email"
                  value={parent.email}
                  onChange={(event) =>
                    handleStudentParentChange(index, "email", event.target.value)
                  }
                  error={
                    fieldErrors[`parents.${index}.email`] || fieldErrors.parents
                  }
                  placeholder="parent@example.com"
                />
                <SelectControl
                  label="Relationship"
                  value={parent.relationship_type}
                  options={enumOptions(RELATIONSHIP_OPTIONS)}
                  onChange={(event) =>
                    handleStudentParentChange(
                      index,
                      "relationship_type",
                      event.target.value,
                    )
                  }
                  error={fieldErrors[`parents.${index}.relationship_type`]}
                />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );

  const renderTeacherForm = () => (
    <div className="space-y-4">
      <p className="rounded-2xl border border-primary/20 bg-primary-subtle/35 px-4 py-3 text-sm leading-6 text-text-soft">
        This sends an invitation. The teacher creates or uses a global account, accepts the invitation, and then receives a school membership.
      </p>
      <Input
        label="Teacher email"
        type="email"
        name="email"
        value={teacherForm.email}
        onChange={handleTeacherChange}
        error={fieldErrors.email}
        required
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Job title"
          name="job_title"
          value={teacherForm.job_title}
          onChange={handleTeacherChange}
          error={fieldErrors.job_title}
          placeholder="Mathematics Teacher"
        />
        <Input
          label="Department"
          name="department"
          value={teacherForm.department}
          onChange={handleTeacherChange}
          error={fieldErrors.department}
          placeholder="Science"
        />
      </div>
      <Input
        label="Employment type"
        name="employment_type"
        value={teacherForm.employment_type}
        onChange={handleTeacherChange}
        error={fieldErrors.employment_type}
        placeholder="Full-time"
      />
    </div>
  );

  const renderParentForm = () => (
    <div className="space-y-4">
      <p className="rounded-2xl border border-primary/20 bg-primary-subtle/35 px-4 py-3 text-sm leading-6 text-text-soft">
        Parent access is invitation-based and tied to a specific student. Acceptance creates a pending link request for student or administrator approval.
      </p>
      <SelectControl
        label="Student"
        name="student_id"
        value={parentForm.student_id}
        options={studentOptions}
        placeholder="Select student"
        onChange={handleParentChange}
        error={fieldErrors.student_id}
        required
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Parent email"
          type="email"
          name="email"
          value={parentForm.email}
          onChange={handleParentChange}
          error={fieldErrors.email}
          required
        />
        <SelectControl
          label="Relationship"
          name="relationship_type"
          value={parentForm.relationship_type}
          options={enumOptions(RELATIONSHIP_OPTIONS)}
          onChange={handleParentChange}
          error={fieldErrors.relationship_type}
          required
        />
      </div>
    </div>
  );

  const submitLabel =
    activeTab === "student"
      ? "Create student"
      : activeTab === "teacher"
        ? "Send teacher invitation"
        : "Send parent invitation";

  return (
    <DashboardLayout role="admin" title="Create & Invite">
      <StudentAccessCodeSlipModal
        notice={accessCodeNotice}
        onClose={() => setAccessCodeNotice(null)}
        onCopied={() => showSuccess("Access code details copied.")}
        onCopyFailed={() =>
          showError("Could not copy details automatically. Please copy them manually.")
        }
        onPrintFailed={() =>
          showError("Could not open the print window. Check your browser popup setting.")
        }
      />

      <div className="space-y-5">
        <Card className="p-4 sm:p-5">
          <div className="mb-4 grid gap-3 md:grid-cols-3">
            {[
              ["Students", studentGuard.usage],
              ["Teachers", teacherGuard.usage],
              ["Parents", parentGuard.usage],
            ].map(([label, usage]) => (
              <div
                key={label}
                className="rounded-[1.1rem] border border-border/70 bg-surface-muted/30 px-4 py-3"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  {label}
                </p>
                <p className="mt-2 text-base font-semibold text-text">
                  {formatUsageValue(usage)}
                </p>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            {USER_TYPES.map((type) => (
              <TabButton
                key={type}
                active={activeTab === type}
                onClick={() => changeTab(type)}
              >
                {TAB_LABELS[type]}
              </TabButton>
            ))}
          </div>
        </Card>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
            {error}
          </div>
        )}

        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-text">{TAB_LABELS[activeTab]}</h2>
          <p className="mt-1 text-sm text-text-muted">
            {activeTab === "student"
              ? "Create the student, initial class enrollment, login credentials, and optional parent invitations in one workflow."
              : activeTab === "teacher"
                ? "Invite a teacher to join this school without creating a duplicate global account."
                : "Invite an existing or new parent account to request access to a specific student."}
          </p>

          {!activeGuard.allowed && activeGuard.reason ? (
            <div className="mt-4 rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
              {activeGuard.reason}
            </div>
          ) : null}

          {isLoadingContext ? (
            <div className="mt-6">
              <LoadingState label="Loading form options..." />
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 space-y-5">
              {activeTab === "student" && renderStudentForm()}
              {activeTab === "teacher" && renderTeacherForm()}
              {activeTab === "parent" && renderParentForm()}

              <Button
                type="submit"
                disabled={isSubmitting || !activeGuard.allowed}
                className="w-full sm:w-auto"
              >
                {isSubmitting
                  ? activeTab === "student"
                    ? "Creating student..."
                    : "Sending invitation..."
                  : !activeGuard.allowed
                    ? "Upgrade required"
                    : submitLabel}
              </Button>
            </form>
          )}
        </Card>

        {successPayload && (
          <Card className="p-5 sm:p-6">
            {successPayload.type === "student" ? (
              <>
                <h2 className="text-lg font-semibold text-text">
                  Student created successfully
                </h2>
                <p className="mt-2 text-sm text-text-soft">
                  Admission number:{" "}
                  <span className="font-semibold text-text">
                    {successPayload.result.admission_number}
                  </span>
                </p>
                <p className="mt-2 text-sm text-text-soft">
                  Access code:{" "}
                  <span className="font-semibold text-text">
                    {successPayload.result.setup_code || "Shown in slip"}
                  </span>
                </p>
                <p className="mt-2 text-sm text-text-soft">
                  Parent invitations queued:{" "}
                  <span className="font-semibold text-text">
                    {successPayload.invitationCount}
                  </span>
                </p>
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={() =>
                      setAccessCodeNotice(
                        buildStudentAccessNotice(successPayload.result),
                      )
                    }
                  >
                    View / print slip
                  </Button>
                </div>
              </>
            ) : (
              <>
                <h2 className="text-lg font-semibold text-text">
                  {successPayload.type === "teacher"
                    ? "Teacher invitation queued"
                    : "Parent invitation queued"}
                </h2>
                <p className="mt-2 text-sm text-text-soft">
                  Email:{" "}
                  <span className="font-semibold text-text">
                    {successPayload.result.invited_email ||
                      successPayload.result.email}
                  </span>
                </p>
                {successPayload.type === "parent" ? (
                  <p className="mt-1 text-sm text-text-soft">
                    Student:{" "}
                    <span className="font-semibold text-text">
                      {successPayload.studentLabel}
                    </span>
                  </p>
                ) : null}
                <p className="mt-1 text-sm text-text-soft">
                  Status:{" "}
                  <span className="font-semibold text-text">
                    {successPayload.result.status || "pending"}
                  </span>
                </p>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  The email worker will deliver the invitation. The account becomes a school membership only after the recipient accepts it.
                </p>
              </>
            )}
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}

export default CreateUserPage;
