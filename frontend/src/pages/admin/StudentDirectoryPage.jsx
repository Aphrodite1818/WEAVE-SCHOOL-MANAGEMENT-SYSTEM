import { useCallback, useEffect, useMemo, useState } from "react";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { classService } from "../../services/academicsService";
import { parseApiError } from "../../services/api";
import { studentService } from "../../services/studentService";
import { useToast } from "../../hooks/useToast";
import { displayName } from "../../utils/user";

const STUDENT_STATUSES = ["active", "withdrawn", "suspended", "graduated"];
const GENDER_OPTIONS = ["male", "female"];

const INITIAL_FORM = {
  first_name: "",
  last_name: "",
  gender: "",
  date_of_birth: "",
  state_of_origin: "",
  class_id: "",
  arm: "",
  status: "active",
  graduation_date: "",
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

const enumOptions = (values) =>
  values.map((value) => ({ value, label: titleCase(value) }));

const optionsFrom = (items, labelFn) =>
  (items || []).map((item) => ({ value: item.id, label: labelFn(item) }));

const compactPayload = (payload) =>
  Object.entries(payload).reduce((nextPayload, [key, value]) => {
    nextPayload[key] = value === "" ? null : value;
    return nextPayload;
  }, {});

const buildAccessCodeText = (notice) => {
  const lines = [
    notice.title,
    "",
    ...notice.fields.map((field) => `${field.label}: ${field.value || "-"}`),
    "",
    "Use this access code once to create your student password.",
  ];

  return lines.join("\n");
};

const escapeHtml = (value) =>
  String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

const getNoticeValue = (notice, label) =>
  notice?.fields.find((field) => field.label === label)?.value || "-";

const buildPrintableSlipHtml = (notice) => {
  const student = getNoticeValue(notice, "Student");
  const admissionNumber = getNoticeValue(notice, "Admission number");
  const accessCode = getNoticeValue(notice, "Access code");
  const expires = getNoticeValue(notice, "Expires");

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Student Access Slip</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f5f7fb;
      color: #111827;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 24px;
    }
    .page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .slip {
      width: min(100%, 520px);
      border: 1px solid #d1d5db;
      border-radius: 24px;
      background: #ffffff;
      padding: 28px;
      box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12);
    }
    .eyebrow {
      margin: 0 0 8px;
      color: #6b7280;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
    }
    .subtitle {
      margin: 10px 0 0;
      color: #4b5563;
      font-size: 14px;
      line-height: 1.6;
    }
    .grid {
      display: grid;
      gap: 12px;
      margin-top: 24px;
    }
    .field {
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px 16px;
      background: #f9fafb;
    }
    .label {
      color: #6b7280;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .value {
      margin-top: 6px;
      word-break: break-word;
      font-size: 16px;
      font-weight: 700;
    }
    .code .value {
      font-size: clamp(28px, 9vw, 44px);
      letter-spacing: 0.16em;
      text-align: center;
    }
    .note {
      margin-top: 22px;
      border-radius: 16px;
      background: #eff6ff;
      color: #1e3a8a;
      padding: 14px 16px;
      font-size: 13px;
      line-height: 1.6;
    }
    .footer {
      margin-top: 20px;
      color: #6b7280;
      font-size: 12px;
      text-align: center;
    }
    .actions {
      margin-top: 18px;
      display: flex;
      gap: 10px;
      justify-content: center;
    }
    button {
      border: 0;
      border-radius: 999px;
      background: #111827;
      color: #ffffff;
      cursor: pointer;
      font-size: 14px;
      font-weight: 700;
      padding: 12px 18px;
    }
    @media (max-width: 520px) {
      body { padding: 12px; }
      .page { align-items: flex-start; padding-top: 16px; }
      .slip { border-radius: 20px; padding: 20px; }
      h1 { font-size: 21px; }
    }
    @media print {
      body { background: #fff; padding: 0; }
      .page { min-height: auto; display: block; }
      .slip { width: 100%; box-shadow: none; border-color: #111827; border-radius: 18px; }
      .actions { display: none; }
    }
  </style>
</head>
<body>
  <main class="page">
    <section class="slip" aria-label="Student access slip">
      <p class="eyebrow">Student access slip</p>
      <h1>${escapeHtml(notice.title)}</h1>
      <p class="subtitle">${escapeHtml(notice.description)}</p>
      <div class="grid">
        <div class="field"><div class="label">Student</div><div class="value">${escapeHtml(student)}</div></div>
        <div class="field"><div class="label">Admission number</div><div class="value">${escapeHtml(admissionNumber)}</div></div>
        <div class="field code"><div class="label">Access code</div><div class="value">${escapeHtml(accessCode)}</div></div>
        <div class="field"><div class="label">Expires</div><div class="value">${escapeHtml(expires)}</div></div>
      </div>
      <div class="note">Use the admission number and access code to log in once. The student must create a new private password immediately after login.</div>
      <p class="footer">Give this slip only to the correct student.</p>
      <div class="actions"><button type="button" onclick="window.print()">Print slip</button></div>
    </section>
  </main>
</body>
</html>`;
};

function AccessCodeNotice({ notice, onClose, onCopy, onPrint }) {
  if (!notice) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 px-3 py-4 sm:items-center sm:px-6">
      <Card className="w-full max-w-xl p-5 shadow-xl sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-text">{notice.title}</h2>
            <p className="mt-1 text-sm text-text-muted">{notice.description}</p>
          </div>
          <Button type="button" variant="outline" size="small" onClick={onClose}>
            Close
          </Button>
        </div>

        <div className="mt-5 rounded-2xl border border-border bg-surface-muted/50 p-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            {notice.fields.map((field) => (
              <div key={field.label}>
                <dt className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  {field.label}
                </dt>
                <dd className="mt-1 break-words text-sm font-semibold text-text">
                  {field.value || "-"}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <p className="mt-4 text-sm text-text-muted">
          The access code is shown once. Give it only to the correct student.
        </p>

        <div className="mt-5 grid gap-2 sm:flex sm:flex-wrap">
          <Button type="button" onClick={() => onCopy(buildAccessCodeText(notice))} className="w-full sm:w-auto">
            Copy details
          </Button>
          <Button type="button" variant="outline" onClick={() => onPrint(notice)} className="w-full sm:w-auto">
            Print slip
          </Button>
          <Button type="button" variant="outline" onClick={onClose} className="w-full sm:w-auto">
            Done
          </Button>
        </div>
      </Card>
    </div>
  );
}

function SelectControl({ label, name, value, options, placeholder, onChange }) {
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
    </div>
  );
}

function statusBadge(value, variant = "default") {
  return <Badge variant={variant}>{titleCase(value || "unknown")}</Badge>;
}

function StudentDirectoryPage() {
  const { showSuccess, showError } = useToast();
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [editingStudent, setEditingStudent] = useState(null);
  const [accessCodeNotice, setAccessCodeNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);

  const classOptions = useMemo(() => optionsFrom(classes, className), [classes]);

  const loadPage = useCallback(
    async (activeFilters = filters) => {
      setIsLoading(true);
      setError(null);

      try {
        const [classResult, studentResult] = await Promise.all([
          classService.getClasses({ limit: 100 }),
          studentService.getAdminStudents({
            limit: 100,
            search: activeFilters.search,
            classId: activeFilters.classId,
            status: activeFilters.status,
          }),
        ]);

        setClasses(Array.isArray(classResult?.items) ? classResult.items : []);
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

  const resetForm = () => {
    setEditingStudent(null);
    setFormData(INITIAL_FORM);
  };

  const handleFormChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  };

  const handleFilterChange = (event) => {
    const { name, value } = event.target;
    setFilters((current) => ({ ...current, [name]: value }));
  };

  const buildNotice = (student, action) => {
    const accessCode = student?.setup_code || student?.access_code;
    if (!accessCode) return null;

    return {
      title: action === "reset" ? "Student access code reset" : "Student created successfully",
      description:
        action === "reset"
          ? "Give this code to the student so they can log in and create a new password."
          : "Give these details to the student for first-time login.",
      fields: [
        { label: "Student", value: student.full_name || displayName(student) },
        { label: "Admission number", value: student.admission_number },
        { label: "Access code", value: accessCode },
        { label: "Expires", value: formatDateValue(student.access_code_expires_at || student.expires_at) },
      ],
    };
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      const payload = compactPayload(formData);

      if (editingStudent) {
        await studentService.updateAdminStudent(editingStudent.id, payload);
        showSuccess("Student updated successfully.");
      } else {
        const result = await studentService.createStudent(payload);
        const notice = buildNotice(result, "create");
        if (notice) setAccessCodeNotice(notice);
        showSuccess("Student created successfully.");
      }

      resetForm();
      await loadPage();
    } catch (err) {
      const parsed = parseApiError(
        err,
        editingStudent ? "Failed to update student." : "Failed to create student."
      );
      showError(parsed.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEdit = (student) => {
    setEditingStudent(student);
    setFormData({
      first_name: student.first_name || "",
      last_name: student.last_name || "",
      gender: student.gender || "",
      date_of_birth: student.date_of_birth || "",
      state_of_origin: student.state_of_origin || "",
      class_id: student.class_id || "",
      arm: student.arm || "",
      status: student.status || "active",
      graduation_date: student.graduation_date || "",
    });
  };

  const handleDelete = async (student) => {
    const label = displayName(student) || student.admission_number || "this student";
    if (!window.confirm(`Delete ${label}? This cannot be undone.`)) return;

    setBusyId(`delete:${student.id}`);
    try {
      await studentService.deleteStudent(student.id);
      showSuccess("Student deleted successfully.");
      if (editingStudent?.id === student.id) resetForm();
      await loadPage();
    } catch (err) {
      const parsed = parseApiError(err, "Failed to delete student.");
      showError(parsed.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleResetAccessCode = async (student) => {
    const label = displayName(student) || student.admission_number || "this student";
    if (!window.confirm(`Generate a new access code for ${label}? The old password will stop working.`)) return;

    setBusyId(`reset:${student.id}`);
    try {
      const result = await studentService.resetStudentAccessCode(student.id);
      const notice = buildNotice(result, "reset");
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

  const handleCopyNotice = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      showSuccess("Access code details copied.");
    } catch (_err) {
      showError("Could not copy details automatically. Please copy them manually.");
    }
  };

  const handlePrintNotice = (notice) => {
    const printWindow = window.open("", "_blank", "width=720,height=760");
    if (!printWindow) {
      showError("Could not open the print window. Check your browser popup setting.");
      return;
    }

    printWindow.document.open();
    printWindow.document.write(buildPrintableSlipHtml(notice));
    printWindow.document.close();
    printWindow.focus();

    window.setTimeout(() => {
      printWindow.print();
    }, 300);
  };

  const applyFilters = async (event) => {
    event.preventDefault();
    await loadPage(filters);
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
      <AccessCodeNotice
        notice={accessCodeNotice}
        onClose={() => setAccessCodeNotice(null)}
        onCopy={handleCopyNotice}
        onPrint={handlePrintNotice}
      />

      {error && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      )}

      <div className="resource-page-grid grid w-full min-w-0 gap-5 2xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
        <Card className="resource-page-form-card p-4 sm:p-5 2xl:sticky 2xl:top-28 2xl:self-start">
          <h2 className="text-lg font-semibold">
            {editingStudent ? "Edit student" : "Create student"}
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Create students with generated admission numbers and one-time access codes.
          </p>

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <Input label="First name" name="first_name" value={formData.first_name} onChange={handleFormChange} required />
            <Input label="Last name" name="last_name" value={formData.last_name} onChange={handleFormChange} required />
            <SelectControl
              label="Gender"
              name="gender"
              value={formData.gender}
              options={enumOptions(GENDER_OPTIONS)}
              onChange={handleFormChange}
            />
            <Input label="Date of birth" type="date" name="date_of_birth" value={formData.date_of_birth} onChange={handleFormChange} />
            <Input label="State of origin" name="state_of_origin" value={formData.state_of_origin} onChange={handleFormChange} />
            <SelectControl
              label="Class"
              name="class_id"
              value={formData.class_id}
              options={classOptions}
              placeholder="Select class"
              onChange={handleFormChange}
            />
            <Input label="Arm" name="arm" value={formData.arm} onChange={handleFormChange} placeholder="A" />
            <SelectControl
              label="Academic status"
              name="status"
              value={formData.status}
              options={enumOptions(STUDENT_STATUSES)}
              onChange={handleFormChange}
            />
            <Input label="Graduation date" type="date" name="graduation_date" value={formData.graduation_date} onChange={handleFormChange} />

            <div className="grid gap-2 sm:flex sm:flex-wrap">
              <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
                {isSubmitting ? "Saving..." : editingStudent ? "Save changes" : "Create student"}
              </Button>
              {editingStudent && (
                <Button type="button" variant="outline" onClick={resetForm} className="w-full sm:w-auto">
                  Cancel
                </Button>
              )}
            </div>
          </form>
        </Card>

        <Card className="resource-page-list-card p-4 sm:p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Students</h2>
              <p className="mt-1 text-sm text-text-muted">
                {total} record{total === 1 ? "" : "s"} found.
              </p>
            </div>
            <Button variant="outline" onClick={() => loadPage()} disabled={isLoading} className="w-full md:w-auto">
              Refresh
            </Button>
          </div>

          <form onSubmit={applyFilters} className="resource-page-filters mt-5 grid gap-3 rounded-2xl border border-border bg-surface-muted/40 p-4 md:grid-cols-3 2xl:grid-cols-4">
            <Input label="Search" name="search" placeholder="Name or admission no." value={filters.search} onChange={handleFilterChange} />
            <SelectControl
              label="Class"
              name="classId"
              value={filters.classId}
              options={classOptions}
              placeholder="All classes"
              onChange={handleFilterChange}
            />
            <SelectControl
              label="Status"
              name="status"
              value={filters.status}
              options={enumOptions(STUDENT_STATUSES)}
              placeholder="All statuses"
              onChange={handleFilterChange}
            />
            <div className="grid gap-2 sm:flex sm:items-end">
              <Button type="submit" size="small" className="w-full sm:w-auto">
                Apply
              </Button>
              <Button type="button" variant="outline" size="small" onClick={clearFilters} className="w-full sm:w-auto">
                Clear
              </Button>
            </div>
          </form>

          <div className="mt-5 table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Full Name</th>
                  <th>Admission Number</th>
                  <th>Admission Date</th>
                  <th>Password Reset</th>
                  <th>Profile Status</th>
                  <th>Academic Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {students.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-text-muted">
                      <EmptyState title="No students found" description="Create a student or adjust your filters." />
                    </td>
                  </tr>
                ) : (
                  students.map((student) => (
                    <tr key={student.id}>
                      <td data-label="Full Name"><span>{displayName(student)}</span></td>
                      <td data-label="Admission Number"><span>{optionalValue(student.admission_number, "Pending")}</span></td>
                      <td data-label="Admission Date"><span>{formatDateValue(student.admission_date)}</span></td>
                      <td data-label="Password Reset">
                        <span>{statusBadge(student.password_reset_required ? "required" : "completed", student.password_reset_required ? "warning" : "success")}</span>
                      </td>
                      <td data-label="Profile Status">
                        <span>{statusBadge(student.profile_status, student.profile_status === "incomplete" ? "warning" : "success")}</span>
                      </td>
                      <td data-label="Academic Status">
                        <span>{statusBadge(student.status, student.status === "active" ? "success" : "default")}</span>
                      </td>
                      <td data-label="Actions">
                        <div className="grid w-full gap-2 sm:flex sm:flex-wrap md:w-auto">
                          <Button type="button" variant="outline" size="small" onClick={() => handleEdit(student)} disabled={busyId?.endsWith(student.id)} className="w-full sm:w-auto">
                            Edit
                          </Button>
                          <Button type="button" variant="outline" size="small" onClick={() => handleResetAccessCode(student)} disabled={busyId === `reset:${student.id}`} className="w-full sm:w-auto">
                            {busyId === `reset:${student.id}` ? "Generating..." : "Reset code"}
                          </Button>
                          <Button type="button" variant="danger" size="small" onClick={() => handleDelete(student)} disabled={busyId === `delete:${student.id}`} className="w-full sm:w-auto">
                            {busyId === `delete:${student.id}` ? "Deleting..." : "Delete"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default StudentDirectoryPage;
