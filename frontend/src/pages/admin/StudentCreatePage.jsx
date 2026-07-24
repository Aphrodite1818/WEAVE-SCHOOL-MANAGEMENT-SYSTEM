import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import StudentAccessCodeSlipModal from "../../components/students/StudentAccessCodeSlipModal";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { parseApiError } from "../../services/api";
import { studentService } from "../../services/studentService";
import { displayName } from "../../utils/user";

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

const titleCase = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

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
      <label className="mb-1.5 block text-sm font-medium text-text-soft">
        {label}
      </label>
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
      {error ? <p className="mt-1 text-sm text-error">{error}</p> : null}
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

function StudentCreatePage() {
  const [classOptions, setClassOptions] = useState([]);
  const [formData, setFormData] = useState(INITIAL_STUDENT_FORM);
  const [isLoadingContext, setIsLoadingContext] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [successPayload, setSuccessPayload] = useState(null);
  const [accessCodeNotice, setAccessCodeNotice] = useState(null);
  const { showSuccess, showError } = useToast();
  const { getResourceGuard, refreshSubscriptionState } = useSubscription();
  const studentGuard = getResourceGuard("students", {
    featureCode: FEATURE_CODES.STUDENT_MANAGEMENT,
  });

  useEffect(() => {
    let mounted = true;

    async function loadContext() {
      setIsLoadingContext(true);
      try {
        const classesResponse = await classService.getClasses({ limit: 100 });
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
      } catch (err) {
        if (mounted) {
          const parsed = parseApiError(err, "Failed to load class options.");
          setError(parsed.message);
          showError(parsed.message);
        }
      } finally {
        if (mounted) setIsLoadingContext(false);
      }
    }

    loadContext();

    return () => {
      mounted = false;
    };
  }, [showError]);

  const resetErrors = () => {
    setError(null);
    setFieldErrors({});
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
    resetErrors();
  };

  const handleParentChange = (index, field, value) => {
    setFormData((current) => ({
      ...current,
      parents: current.parents.map((parent, parentIndex) =>
        parentIndex === index ? { ...parent, [field]: value } : parent,
      ),
    }));
    resetErrors();
  };

  const addParent = () => {
    setFormData((current) => {
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

  const removeParent = (index) => {
    setFormData((current) => ({
      ...current,
      parents:
        current.parents.length === 1
          ? [{ email: "", relationship_type: "guardian" }]
          : current.parents.filter((_, parentIndex) => parentIndex !== index),
    }));
    resetErrors();
  };

  const buildParents = () => {
    const parents = formData.parents
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
      const parents = buildParents();
      const result = await studentService.createStudent({
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        gender: cleanOptional(formData.gender),
        date_of_birth: formData.date_of_birth,
        state_of_origin: cleanOptional(formData.state_of_origin),
        class_id: formData.class_id,
        parents,
      });

      setFormData(INITIAL_STUDENT_FORM);
      setSuccessPayload({ result, invitationCount: parents.length });
      setAccessCodeNotice(buildStudentAccessNotice(result));
      showSuccess(
        parents.length > 0
          ? "Student created and parent invitations queued."
          : "Student created successfully.",
      );
      await refreshSubscriptionState({ silent: true });
    } catch (err) {
      if (!err?.response && err instanceof Error) {
        setError(err.message);
        showError(err.message);
      } else {
        const parsed = parseApiError(err, "Failed to create student.");
        setFieldErrors(parsed.fieldErrors || {});
        setError(parsed.message);
        showError(parsed.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DashboardLayout
      role="admin"
      title="Create Student"
      description="Add a student record, class placement, first-login access code, and optional parent invitations."
      actions={
        <Link to="/admin/students">
          <Button type="button" variant="outline">
            <ArrowLeft className="h-4 w-4" />
            Back to students
          </Button>
        </Link>
      }
    >
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

      <section className="mx-auto grid w-full max-w-5xl gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="p-5 sm:p-6">
          {error ? (
            <div className="mb-5 rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
              {error}
            </div>
          ) : null}

          {!studentGuard.allowed && studentGuard.reason ? (
            <div className="mb-5 rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-700">
              {studentGuard.reason}
            </div>
          ) : null}

          {isLoadingContext ? (
            <LoadingState label="Loading class options..." />
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <section className="space-y-4">
                <div>
                  <h2 className="text-lg font-semibold text-text">Student identity</h2>
                  <p className="mt-1 text-sm text-text-muted">
                    Admission number and access code are generated by the backend.
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="First name"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleChange}
                    error={fieldErrors.first_name}
                    required
                  />
                  <Input
                    label="Last name"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleChange}
                    error={fieldErrors.last_name}
                    required
                  />
                  <SelectControl
                    label="Gender"
                    name="gender"
                    value={formData.gender}
                    options={enumOptions(GENDER_OPTIONS)}
                    onChange={handleChange}
                    error={fieldErrors.gender}
                  />
                  <Input
                    label="Date of birth"
                    type="date"
                    name="date_of_birth"
                    value={formData.date_of_birth}
                    onChange={handleChange}
                    error={fieldErrors.date_of_birth}
                    required
                  />
                  <Input
                    label="State of origin"
                    name="state_of_origin"
                    value={formData.state_of_origin}
                    onChange={handleChange}
                    error={fieldErrors.state_of_origin}
                  />
                </div>
              </section>

              <section className="border-t border-border/70 pt-5">
                <h2 className="text-sm font-semibold text-text">Academic placement</h2>
                <div className="mt-4">
                  <SelectControl
                    label="Class"
                    name="class_id"
                    value={formData.class_id}
                    options={classOptions}
                    placeholder="Select class"
                    onChange={handleChange}
                    error={fieldErrors.class_id}
                    required
                  />
                </div>
              </section>

              <section className="border-t border-border/70 pt-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-text">Parent invitations</h2>
                    <p className="mt-1 text-xs leading-5 text-text-muted">
                      Add up to two parent emails while creating the student.
                    </p>
                  </div>
                  {formData.parents.length < 2 ? (
                    <Button type="button" variant="outline" size="small" onClick={addParent}>
                      <Plus className="h-4 w-4" />
                      Add parent
                    </Button>
                  ) : null}
                </div>

                <div className="mt-4 space-y-3">
                  {formData.parents.map((parent, index) => (
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
                          onClick={() => removeParent(index)}
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
                            handleParentChange(index, "email", event.target.value)
                          }
                          error={
                            fieldErrors[`parents.${index}.email`] ||
                            fieldErrors.parents
                          }
                          placeholder="parent@example.com"
                        />
                        <SelectControl
                          label="Relationship"
                          value={parent.relationship_type}
                          options={enumOptions(RELATIONSHIP_OPTIONS)}
                          onChange={(event) =>
                            handleParentChange(
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

              <Button
                type="submit"
                disabled={isSubmitting || !studentGuard.allowed}
                className="w-full sm:w-auto"
              >
                {isSubmitting
                  ? "Creating student..."
                  : !studentGuard.allowed
                    ? "Upgrade required"
                    : "Create student"}
              </Button>
            </form>
          )}
        </Card>

        <Card className="h-fit p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
            Creation result
          </h2>
          {successPayload ? (
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-success/30 bg-success-soft px-4 py-3 text-sm text-emerald-800">
                Student record accepted by the API.
              </div>
              <div className="space-y-2 text-sm text-text-muted">
                <p>
                  Admission number:{" "}
                  <span className="font-semibold text-text">
                    {successPayload.result.admission_number}
                  </span>
                </p>
                <p>
                  Parent invitations queued:{" "}
                  <span className="font-semibold text-text">
                    {successPayload.invitationCount}
                  </span>
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() =>
                  setAccessCodeNotice(
                    buildStudentAccessNotice(successPayload.result),
                  )
                }
              >
                View / print slip
              </Button>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-text-muted">
              After creation, give the generated access slip only to the
              correct student. Parent invitations appear under the parent
              directory.
            </p>
          )}
        </Card>
      </section>
    </DashboardLayout>
  );
}

export default StudentCreatePage;
