import { useCallback, useEffect, useMemo, useState } from "react";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import MediaImageUploader from "../../components/media/MediaImageUploader";
import StudentAccessCodeSlipModal from "../../components/students/StudentAccessCodeSlipModal";
import { classService } from "../../services/academicsService";
import { parseApiError } from "../../services/api";
import { mediaService } from "../../services/mediaService";
import { studentService } from "../../services/studentService";
import { useToast } from "../../hooks/useToast";
import { cn } from "../../utils/cn";
import { displayName, getAvatarSrcFromRecord, getUserInitials } from "../../utils/user";

const STUDENT_STATUSES = ["active", "withdrawn", "suspended", "graduated"];
const GENDER_OPTIONS = ["male", "female"];

const INITIAL_EDIT_FORM = {
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

function StudentIdentityCell({ student }) {
  const avatarSrc = getAvatarSrcFromRecord(student);
  const label = displayName(student);

  return (
    <div className="flex min-w-0 items-center gap-3">
      <span
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-border bg-primary-soft text-sm font-black text-primary",
          avatarSrc ? "bg-surface" : ""
        )}
      >
        {avatarSrc ? <img src={avatarSrc} alt="" className="h-full w-full object-cover" /> : getUserInitials(student)}
      </span>
      <span className="min-w-0 truncate font-semibold text-text">{label}</span>
    </div>
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
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [formData, setFormData] = useState(INITIAL_EDIT_FORM);
  const [editingStudent, setEditingStudent] = useState(null);
  const [accessCodeNotice, setAccessCodeNotice] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

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

  const resetEditForm = () => {
    setEditingStudent(null);
    setFormData(INITIAL_EDIT_FORM);
    setFieldErrors({});
  };

  const patchStudentPhoto = (studentId, nextPhotoUrl) => {
    setStudents((current) =>
      current.map((student) =>
        student.id === studentId ? { ...student, passport_photo_url: nextPhotoUrl || null } : student
      )
    );
    setEditingStudent((current) =>
      current?.id === studentId ? { ...current, passport_photo_url: nextPhotoUrl || null } : current
    );
  };

  const handleStudentPassportUploaded = (response) => {
    if (!editingStudent?.id) return;
    const nextPhotoUrl = mediaService.resolveMediaRenderUrl(response);
    patchStudentPhoto(editingStudent.id, nextPhotoUrl);
    showSuccess("Student passport photo updated successfully.");
  };

  const handleStudentPassportDeleted = () => {
    if (!editingStudent?.id) return;
    patchStudentPhoto(editingStudent.id, null);
    showSuccess("Student passport photo removed successfully.");
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
      class_id: student.class_id || "",
      arm: student.arm || "",
      status: student.status || "active",
      graduation_date: student.graduation_date || "",
    });
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

  const handleDelete = async (student) => {
    const label = displayName(student) || student.admission_number || "this student";
    if (!window.confirm(`Delete ${label}? This cannot be undone.`)) return;

    setBusyId(`delete:${student.id}`);
    try {
      await studentService.deleteStudent(student.id);
      showSuccess("Student deleted successfully.");
      if (editingStudent?.id === student.id) resetEditForm();
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
      <StudentAccessCodeSlipModal
        notice={accessCodeNotice}
        onClose={() => setAccessCodeNotice(null)}
        onCopied={() => showSuccess("Access code details copied.")}
        onCopyFailed={() => showError("Could not copy details automatically. Please copy them manually.")}
        onPrintFailed={() => showError("Could not open the print window. Check your browser popup setting.")}
      />

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
              Update school-managed student details. New students should be created from the Create User page.
            </p>

            <div className="mt-5">
              <MediaImageUploader
                title="Student passport photo"
                description="Upload a clean student passport image for records and profile previews."
                variant="avatar"
                currentImageUrl={getAvatarSrcFromRecord(editingStudent)}
                fallbackLabel={displayName(editingStudent)}
                maxSizeBytes={2 * 1024 * 1024}
                maxSizeLabel="2 MB"
                onUpload={(file) => mediaService.uploadStudentPassport(editingStudent.id, file)}
                onDelete={() => mediaService.deleteStudentPassport(editingStudent.id, { deleteObject: false })}
                onUploaded={handleStudentPassportUploaded}
                onDeleted={handleStudentPassportDeleted}
              />
            </div>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <Input label="First name" name="first_name" value={formData.first_name} onChange={handleFormChange} error={fieldErrors.first_name} required />
              <Input label="Last name" name="last_name" value={formData.last_name} onChange={handleFormChange} error={fieldErrors.last_name} required />
              <SelectControl label="Gender" name="gender" value={formData.gender} options={enumOptions(GENDER_OPTIONS)} onChange={handleFormChange} error={fieldErrors.gender} />
              <Input label="Date of birth" type="date" name="date_of_birth" value={formData.date_of_birth} onChange={handleFormChange} error={fieldErrors.date_of_birth} />
              <Input label="State of origin" name="state_of_origin" value={formData.state_of_origin} onChange={handleFormChange} error={fieldErrors.state_of_origin} />
              <SelectControl label="Class" name="class_id" value={formData.class_id} options={classOptions} placeholder="Select class" onChange={handleFormChange} error={fieldErrors.class_id} />
              <Input label="Arm" name="arm" value={formData.arm} onChange={handleFormChange} error={fieldErrors.arm} placeholder="A" />
              <SelectControl label="Academic status" name="status" value={formData.status} options={enumOptions(STUDENT_STATUSES)} onChange={handleFormChange} error={fieldErrors.status} />
              <Input label="Graduation date" type="date" name="graduation_date" value={formData.graduation_date} onChange={handleFormChange} error={fieldErrors.graduation_date} />

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
                      <EmptyState title="No students found" description="Create students from the Create User page or adjust your filters." />
                    </td>
                  </tr>
                ) : (
                  students.map((student) => (
                    <tr key={student.id}>
                      <td data-label="Full Name"><StudentIdentityCell student={student} /></td>
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
