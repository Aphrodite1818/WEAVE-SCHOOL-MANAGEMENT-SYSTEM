import { useEffect, useState } from "react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import LoadingState from "../../components/shared/LoadingState";
import { classService } from "../../services/academicsService";
import { studentService } from "../../services/studentService";
import { teacherService } from "../../services/teacherService";
import { parentService } from "../../services/parentService";
import { getErrorMessage, parseApiError } from "../../services/api";
import { useToast } from "../../hooks/useToast";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { formatUsageValue } from "../../features/subscriptions/subscriptionConfig";

const USER_TYPES = ["student", "teacher", "parent"];

const INITIAL_STUDENT_FORM = {
  first_name: "",
  last_name: "",
  class_id: "",
};

const INITIAL_TEACHER_FORM = {
  email: "",
  first_name: "",
  last_name: "",
  staff_id: "",
};

const INITIAL_PARENT_FORM = {
  email: "",
  first_name: "",
  last_name: "",
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

function CreateUserPage() {
  const [activeTab, setActiveTab] = useState("student");
  const [classOptions, setClassOptions] = useState([]);
  const [studentForm, setStudentForm] = useState(INITIAL_STUDENT_FORM);
  const [teacherForm, setTeacherForm] = useState(INITIAL_TEACHER_FORM);
  const [parentForm, setParentForm] = useState(INITIAL_PARENT_FORM);
  const [isLoadingContext, setIsLoadingContext] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [successPayload, setSuccessPayload] = useState(null);
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

  useEffect(() => {
    let mounted = true;

    async function loadContext() {
      setIsLoadingContext(true);
      try {
        const [classesResponse] = await Promise.all([
          classService.getClasses({ limit: 100 }),
        ]);

        if (!mounted) return;

        setClassOptions(
          (classesResponse?.items || []).map((item) => ({
            value: item.id,
            label: [item.name, item.arm].filter(Boolean).join(" ") || "Unnamed class",
          }))
        );
      } catch (err) {
        if (mounted) {
          setError(getErrorMessage(err, "Failed to load class options."));
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

  const handleStudentChange = (event) => {
    const { name, value } = event.target;
    setStudentForm((current) => ({ ...current, [name]: value }));
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

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    resetErrors();
    setSuccessPayload(null);

    try {
      if (activeTab === "student") {
        const result = await studentService.createStudent({
          first_name: studentForm.first_name,
          last_name: studentForm.last_name,
          class_id: studentForm.class_id || null,
        });
        setStudentForm(INITIAL_STUDENT_FORM);
        setSuccessPayload({ type: "student", result });
        showSuccess("Student created successfully.");
        await refreshSubscriptionState({ silent: true });
      } else if (activeTab === "teacher") {
        const result = await teacherService.createTeacher({
          email: teacherForm.email,
          first_name: teacherForm.first_name || null,
          last_name: teacherForm.last_name || null,
          staff_id: teacherForm.staff_id || null,
        });
        setTeacherForm(INITIAL_TEACHER_FORM);
        setSuccessPayload({ type: "teacher", result });
        showSuccess("Teacher created successfully.");
        await refreshSubscriptionState({ silent: true });
      } else {
        const result = await parentService.createParent({
          email: parentForm.email,
          first_name: parentForm.first_name || null,
          last_name: parentForm.last_name || null,
        });
        setParentForm(INITIAL_PARENT_FORM);
        setSuccessPayload({ type: "parent", result });
        showSuccess("Parent created successfully.");
        await refreshSubscriptionState({ silent: true });
      }
    } catch (err) {
      const apiError = parseApiError(err, `Failed to create ${activeTab}.`);
      setFieldErrors(apiError.fieldErrors);
      setError(apiError.message);
      showError(apiError.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderStudentForm = () => (
    <>
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
      <div>
        <label className="mb-1.5 block text-sm font-medium text-text-soft">Class</label>
        <select
          name="class_id"
          value={studentForm.class_id}
          onChange={handleStudentChange}
          className="input-base"
        >
          <option value="">Select class</option>
          {classOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );

  const renderTeacherForm = () => (
    <>
      <Input
        label="Email"
        type="email"
        name="email"
        value={teacherForm.email}
        onChange={handleTeacherChange}
        error={fieldErrors.email}
        required
      />
      <Input
        label="First name"
        name="first_name"
        value={teacherForm.first_name}
        onChange={handleTeacherChange}
        error={fieldErrors.first_name}
      />
      <Input
        label="Last name"
        name="last_name"
        value={teacherForm.last_name}
        onChange={handleTeacherChange}
        error={fieldErrors.last_name}
      />
      <Input
        label="Staff ID"
        name="staff_id"
        value={teacherForm.staff_id}
        onChange={handleTeacherChange}
        error={fieldErrors.staff_id}
      />
    </>
  );

  const renderParentForm = () => (
    <>
      <Input
        label="Email"
        type="email"
        name="email"
        value={parentForm.email}
        onChange={handleParentChange}
        error={fieldErrors.email}
        required
      />
      <Input
        label="First name"
        name="first_name"
        value={parentForm.first_name}
        onChange={handleParentChange}
        error={fieldErrors.first_name}
      />
      <Input
        label="Last name"
        name="last_name"
        value={parentForm.last_name}
        onChange={handleParentChange}
        error={fieldErrors.last_name}
      />
    </>
  );

  return (
    <DashboardLayout role="admin" title="Create User">
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
              <TabButton key={type} active={activeTab === type} onClick={() => setActiveTab(type)}>
                {type.charAt(0).toUpperCase() + type.slice(1)}
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
          <h2 className="text-lg font-semibold text-text">
            {activeTab === "student" ? "Student details" : activeTab === "teacher" ? "Teacher details" : "Parent details"}
          </h2>

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
            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {activeTab === "student" && renderStudentForm()}
              {activeTab === "teacher" && renderTeacherForm()}
              {activeTab === "parent" && renderParentForm()}

              <Button
                type="submit"
                disabled={isSubmitting || !activeGuard.allowed}
                className="w-full sm:w-auto"
              >
                {isSubmitting
                  ? "Creating..."
                  : !activeGuard.allowed
                    ? "Upgrade required"
                    : `Create ${activeTab}`}
              </Button>
            </form>
          )}
        </Card>

        {successPayload && (
          <Card className="p-5 sm:p-6">
            {successPayload.type === "student" ? (
              <>
                <h2 className="text-lg font-semibold text-text">Student created successfully</h2>
                <p className="mt-2 text-sm text-text-soft">
                  Admission number: <span className="font-semibold text-text">{successPayload.result.admission_number}</span>
                </p>
                <p className="mt-2 text-sm text-text-soft">
                  Password: <span className="font-semibold text-text">{successPayload.result.default_password || "default"}</span>
                </p>
              </>
            ) : (
              <>
                <h2 className="text-lg font-semibold text-text">
                  {successPayload.type === "teacher" ? "Teacher" : "Parent"} created successfully
                </h2>
                <p className="mt-2 text-sm text-text-soft">
                  Email: <span className="font-semibold text-text">{successPayload.result.email}</span>
                </p>
                <p className="mt-1 text-sm text-text-soft">
                  Status: <span className="font-semibold text-text">{successPayload.result.account_status || "pending"}</span>
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
