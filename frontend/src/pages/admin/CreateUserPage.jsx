import { useEffect, useMemo, useState } from "react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import { classService } from "../../services/academicsService";
import { studentService } from "../../services/studentService";
import { teacherService } from "../../services/teacherService";
import { parentService } from "../../services/parentService";
import { getErrorMessage, parseApiError } from "../../services/api";
import { useToast } from "../../hooks/useToast";

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

  const pageDescription = useMemo(() => {
    if (activeTab === "student") {
      return "Create student accounts with auto-generated admission numbers and the default-password first-login flow.";
    }
    if (activeTab === "teacher") {
      return "Create teacher accounts, optionally assign subjects, and let invite acceptance finish activation.";
    }
    return "Create parent accounts and let invite acceptance finish activation before student-link requests begin.";
  }, [activeTab]);

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
      } else {
        const result = await parentService.createParent({
          email: parentForm.email,
          first_name: parentForm.first_name || null,
          last_name: parentForm.last_name || null,
        });
        setParentForm(INITIAL_PARENT_FORM);
        setSuccessPayload({ type: "parent", result });
        showSuccess("Parent created successfully.");
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
    <DashboardLayout
      role="admin"
      title="Create User"
      description={pageDescription}
    >
      <div className="space-y-5">
        <Card className="p-4 sm:p-5">
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
          <p className="mt-1 text-sm text-text-muted">
            Only collect the fields the admin is responsible for. The rest should be completed through onboarding or later profile updates.
          </p>

          {isLoadingContext ? (
            <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface-muted/40 px-4 py-10 text-center text-sm text-text-muted">
              Loading form options...
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {activeTab === "student" && renderStudentForm()}
              {activeTab === "teacher" && renderTeacherForm()}
              {activeTab === "parent" && renderParentForm()}

              <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
                {isSubmitting ? "Creating..." : `Create ${activeTab}`}
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
                  Student logs in with this admission number and the default password.
                </p>
                <p className="mt-1 text-sm text-text-soft">
                  Default password: <span className="font-semibold text-text">{successPayload.result.default_password || "default"}</span>
                </p>
              </>
            ) : (
              <>
                <h2 className="text-lg font-semibold text-text">
                  {successPayload.type === "teacher" ? "Teacher" : "Parent"} created successfully
                </h2>
                <p className="mt-2 text-sm text-text-soft">
                  Invite sent or pending for <span className="font-semibold text-text">{successPayload.result.email}</span>.
                </p>
                <p className="mt-1 text-sm text-text-soft">
                  Current status: <span className="font-semibold text-text">{successPayload.result.account_status || "pending"}</span>
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
