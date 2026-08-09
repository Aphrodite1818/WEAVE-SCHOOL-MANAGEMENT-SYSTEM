import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import StudentAccessCodeSlipModal from "../../components/students/StudentAccessCodeSlipModal";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { useToast } from "../../hooks/useToast";
import academicService from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { parseApiError } from "../../services/api";
import { studentService } from "../../services/studentService";
import { displayName } from "../../utils/user";

const GENDER_OPTIONS = ["male", "female"];
const RELATIONSHIP_OPTIONS = ["father", "mother", "guardian", "sponsor", "other"];

const INITIAL_FORM = {
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
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);
const cleanOptional = (value) => String(value || "").trim() || null;

const formatDate = (value) => {
  if (!value) return "Not set";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
};

function SelectField({ label, value, onChange, options, placeholder, error, required }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-text-soft">{label}</span>
      <select className="input-base" value={value} onChange={onChange} required={required}>
        <option value="">{placeholder || "Select"}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error ? <span className="mt-1 block text-xs text-error">{error}</span> : null}
    </label>
  );
}

function buildAccessNotice(student) {
  const code = student?.setup_code || student?.access_code;
  if (!code) return null;
  return {
    title: "Student created successfully",
    description: "Give these first-login details to the student.",
    fields: [
      { label: "Student", value: student.full_name || displayName(student) },
      { label: "Admission number", value: student.admission_number },
      { label: "Access code", value: code },
      { label: "Expires", value: formatDate(student.access_code_expires_at || student.expires_at) },
    ],
  };
}

function StudentCreatePage() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [classes, setClasses] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [loadingContext, setLoadingContext] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [accessNotice, setAccessNotice] = useState(null);
  const { showSuccess, showError } = useToast();
  const { getResourceGuard, refreshSubscriptionState } = useSubscription();
  const studentGuard = getResourceGuard("students", {
    featureCode: FEATURE_CODES.STUDENT_MANAGEMENT,
  });

  const classOptions = useMemo(
    () =>
      classes.map((item) => ({
        value: item.id,
        label: [item.name, item.arm].filter(Boolean).join(" ") || "Unnamed class",
      })),
    [classes],
  );

  useEffect(() => {
    let mounted = true;
    async function loadContext() {
      setLoadingContext(true);
      setError("");
      try {
        const [classResponse, sessionResponse] = await Promise.all([
          classService.getClasses({ limit: 100 }),
          academicService.listSessions({ limit: 100 }),
        ]);
        if (!mounted) return;
        const activeClasses = asItems(classResponse).filter((item) => item.is_active !== false);
        const sessions = asItems(sessionResponse);
        const openCurrent =
          sessions.find(
            (item) =>
              item.is_current &&
              item.is_active !== false &&
              String(item.status || "").toLowerCase() === "open",
          ) || null;
        setClasses(activeClasses);
        setCurrentSession(openCurrent);
      } catch (requestError) {
        if (!mounted) return;
        const parsed = parseApiError(requestError, "We couldn't load the student setup details.");
        setError(parsed.message);
        showError(parsed.message);
      } finally {
        if (mounted) setLoadingContext(false);
      }
    }
    loadContext();
    return () => {
      mounted = false;
    };
  }, [showError]);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setError("");
  };

  const updateParent = (index, field, value) => {
    setForm((current) => ({
      ...current,
      parents: current.parents.map((parent, parentIndex) =>
        parentIndex === index ? { ...parent, [field]: value } : parent,
      ),
    }));
    setError("");
  };

  const addParent = () => {
    setForm((current) =>
      current.parents.length >= 2
        ? current
        : {
            ...current,
            parents: [...current.parents, { email: "", relationship_type: "guardian" }],
          },
    );
  };

  const removeParent = (index) => {
    setForm((current) => ({
      ...current,
      parents:
        current.parents.length === 1
          ? [{ email: "", relationship_type: "guardian" }]
          : current.parents.filter((_, parentIndex) => parentIndex !== index),
    }));
  };

  const buildParents = () => {
    const parents = form.parents
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

  const submit = async (event) => {
    event.preventDefault();
    if (!currentSession) {
      setError("Open a current academic session before creating students.");
      return;
    }
    if (!studentGuard.allowed) {
      setError(studentGuard.reason || "The current plan does not allow another student.");
      return;
    }

    setSubmitting(true);
    setError("");
    setFieldErrors({});
    try {
      const parents = buildParents();
      const result = await studentService.createStudent({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        gender: cleanOptional(form.gender),
        date_of_birth: form.date_of_birth,
        state_of_origin: cleanOptional(form.state_of_origin),
        class_id: form.class_id,
        parents,
      });
      setForm(INITIAL_FORM);
      setAccessNotice(buildAccessNotice(result));
      showSuccess(
        parents.length > 0
          ? "Student created. Parent invitations are on their way."
          : "Student created successfully.",
      );
      await refreshSubscriptionState({ silent: true });
    } catch (requestError) {
      if (!requestError?.response && requestError instanceof Error) {
        setError(requestError.message);
        showError(requestError.message);
      } else {
        const parsed = parseApiError(requestError, "We couldn't create the student.");
        setFieldErrors(parsed.fieldErrors || {});
        setError(parsed.message);
        showError(parsed.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const creationBlocked =
    loadingContext ||
    !currentSession ||
    classOptions.length === 0 ||
    !studentGuard.allowed;

  return (
    <DashboardLayout
      role="admin"
      title="Create Student"
      description="Add the student, place them in a class, create their first-login details, and optionally invite parents."
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
        notice={accessNotice}
        onClose={() => setAccessNotice(null)}
        onCopied={() => showSuccess("Access details copied.")}
        onCopyFailed={() => showError("Could not copy access details.")}
        onPrintFailed={() => showError("Could not open the print window.")}
      />

      <section className="mx-auto grid w-full max-w-5xl gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="p-5 sm:p-6">
          {error ? (
            <div className="mb-5 rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
              {error}
            </div>
          ) : null}

          {!currentSession && !loadingContext ? (
            <div className="mb-5 rounded-2xl border border-warning/30 bg-warning-soft px-4 py-4 text-sm text-amber-800">
              <p className="font-semibold">No open current academic session</p>
              <p className="mt-1 leading-6">
                Open the current academic session before creating students so Weave can place them correctly.
              </p>
              <Link to="/admin/academic/sessions" className="mt-3 inline-flex font-semibold text-primary">
                Open Academic Sessions
              </Link>
            </div>
          ) : null}

          {classOptions.length === 0 && !loadingContext ? (
            <div className="mb-5 rounded-2xl border border-warning/30 bg-warning-soft px-4 py-4 text-sm text-amber-800">
              Create at least one active class before admitting students.
            </div>
          ) : null}

          {!studentGuard.allowed && studentGuard.reason ? (
            <div className="mb-5 rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-800">
              {studentGuard.reason}
            </div>
          ) : null}

          {loadingContext ? (
            <LoadingState label="Checking school setup..." />
          ) : (
            <form onSubmit={submit} className="space-y-6">
              <section className="space-y-4">
                <div>
                  <h2 className="text-lg font-semibold text-text">Student identity</h2>
                  <p className="mt-1 text-sm text-text-muted">
                    The admission number and first-login code are created automatically.
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="First name" value={form.first_name} required error={fieldErrors.first_name} onChange={(event) => updateField("first_name", event.target.value)} />
                  <Input label="Last name" value={form.last_name} required error={fieldErrors.last_name} onChange={(event) => updateField("last_name", event.target.value)} />
                  <SelectField label="Gender" value={form.gender} options={GENDER_OPTIONS.map((value) => ({ value, label: titleCase(value) }))} error={fieldErrors.gender} onChange={(event) => updateField("gender", event.target.value)} />
                  <Input label="Date of birth" type="date" value={form.date_of_birth} required error={fieldErrors.date_of_birth} onChange={(event) => updateField("date_of_birth", event.target.value)} />
                  <Input label="State of origin" value={form.state_of_origin} error={fieldErrors.state_of_origin} onChange={(event) => updateField("state_of_origin", event.target.value)} />
                </div>
              </section>

              <section className="border-t border-border/70 pt-5">
                <h2 className="text-sm font-semibold text-text">Initial placement</h2>
                <p className="mt-1 text-xs text-text-muted">
                  Session: {currentSession?.name || "Unavailable"}
                </p>
                <div className="mt-4">
                  <SelectField label="Class" value={form.class_id} options={classOptions} placeholder="Select class" required error={fieldErrors.class_id} onChange={(event) => updateField("class_id", event.target.value)} />
                </div>
              </section>

              <section className="border-t border-border/70 pt-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-text">Parent invitations</h2>
                    <p className="mt-1 text-xs text-text-muted">Add up to two parent emails. Each parent can accept the connection to this student.</p>
                  </div>
                  {form.parents.length < 2 ? (
                    <Button type="button" variant="outline" size="small" onClick={addParent}>
                      <Plus className="h-4 w-4" />
                      Add parent
                    </Button>
                  ) : null}
                </div>

                <div className="mt-4 space-y-3">
                  {form.parents.map((parent, index) => (
                    <div key={`parent-${index}`} className="grid gap-3 rounded-2xl border border-border/70 p-4 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end">
                      <Input label={`Parent ${index + 1} email`} type="email" value={parent.email} error={fieldErrors[`parents.${index}.email`]} onChange={(event) => updateParent(index, "email", event.target.value)} />
                      <SelectField label="Relationship" value={parent.relationship_type} options={RELATIONSHIP_OPTIONS.map((value) => ({ value, label: titleCase(value) }))} onChange={(event) => updateParent(index, "relationship_type", event.target.value)} />
                      <Button type="button" variant="outline" size="icon" aria-label="Remove parent" onClick={() => removeParent(index)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </section>

              <Button type="submit" disabled={submitting || creationBlocked} className="w-full sm:w-auto">
                {submitting ? "Creating student..." : "Create student"}
              </Button>
            </form>
          )}
        </Card>

        <Card className="h-fit p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Creation requirements</h2>
          <div className="mt-4 space-y-3 text-sm text-text-muted">
            <p>Academic session: <span className="font-semibold text-text">{currentSession?.name || "Missing"}</span></p>
            <p>Active classes: <span className="font-semibold text-text">{classOptions.length}</span></p>
            <p>Plan capacity: <span className="font-semibold text-text">{studentGuard.allowed ? "Available" : "Blocked"}</span></p>
          </div>
        </Card>
      </section>
    </DashboardLayout>
  );
}

export default StudentCreatePage;
