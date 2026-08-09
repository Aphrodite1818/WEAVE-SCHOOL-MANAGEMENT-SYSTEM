import { ArrowLeft, MailPlus } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import AdminStudentLookup from "../../components/students/AdminStudentLookup";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { useToast } from "../../hooks/useToast";
import { parseApiError } from "../../services/api";
import { parentService } from "../../services/parentService";
import { teacherService } from "../../services/teacherService";

const RELATIONSHIP_OPTIONS = ["father", "mother", "guardian", "sponsor", "other"];

const roleConfig = {
  teacher: {
    title: "Invite Teacher",
    description: "Send an invitation to a teacher to join your school on Weave.",
    directoryPath: "/admin/teachers",
  },
  parent: {
    title: "Invite Parent",
    description: "Invite a parent or guardian to connect with a student in your school.",
    directoryPath: "/admin/parents",
  },
};

const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

function SelectControl({ label, value, onChange, options, error, required = false }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-text-soft">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="input-base" required={required}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      {error ? <span className="mt-1 block text-xs text-error">{error}</span> : null}
    </label>
  );
}

function AdminInvitationPage() {
  const { role = "" } = useParams();
  const config = roleConfig[role];
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [result, setResult] = useState(null);
  const [teacherForm, setTeacherForm] = useState({
    email: "",
    job_title: "",
    department: "",
    employment_type: "",
  });
  const [parentForm, setParentForm] = useState({
    student_id: "",
    email: "",
    relationship_type: "guardian",
  });
  const { showSuccess, showError } = useToast();

  if (!config) return <Navigate to="/admin/dashboard" replace />;

  const resetErrors = () => {
    setError("");
    setFieldErrors({});
    setResult(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    resetErrors();
    try {
      const response = role === "teacher"
        ? await teacherService.createInvitation({
            email: teacherForm.email.trim().toLowerCase(),
            job_title: teacherForm.job_title.trim() || null,
            department: teacherForm.department.trim() || null,
            employment_type: teacherForm.employment_type.trim() || null,
          })
        : await parentService.createInvitation({
            student_id: parentForm.student_id,
            email: parentForm.email.trim().toLowerCase(),
            relationship_type: parentForm.relationship_type,
          });
      setResult(response);
      if (role === "teacher") {
        setTeacherForm({ email: "", job_title: "", department: "", employment_type: "" });
      } else {
        setParentForm({ student_id: "", email: "", relationship_type: "guardian" });
      }
      showSuccess(`${titleCase(role)} invitation is on its way.`);
    } catch (requestError) {
      const parsed = parseApiError(requestError, `Could not send ${role} invitation.`);
      setFieldErrors(parsed.fieldErrors || {});
      setError(parsed.message);
      showError(parsed.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DashboardLayout
      role="admin"
      title={config.title}
      description={config.description}
      actions={
        <Link to={config.directoryPath}>
          <Button type="button" variant="outline"><ArrowLeft className="h-4 w-4" />Back to directory</Button>
        </Link>
      }
    >
      <section className="mx-auto grid w-full max-w-5xl gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary"><MailPlus className="h-5 w-5" /></span>
            <div>
              <h2 className="text-lg font-semibold text-text">{config.title}</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                {role === "teacher"
                  ? "They can sign in or create an account, then accept your school invitation."
                  : "Choose the student and enter the parent or guardian's email. Weave includes the student automatically."}
              </p>
            </div>
          </div>

          {error ? <div className="mt-5 rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">{error}</div> : null}

          <form
            onSubmit={handleSubmit}
            onTouchStartCapture={(event) => event.stopPropagation()}
            className="mt-6 space-y-4"
          >
            {role === "teacher" ? (
              <>
                <Input label="Teacher email" type="email" value={teacherForm.email} onChange={(event) => { setTeacherForm((current) => ({ ...current, email: event.target.value })); resetErrors(); }} error={fieldErrors.email} required />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Job title" value={teacherForm.job_title} onChange={(event) => setTeacherForm((current) => ({ ...current, job_title: event.target.value }))} error={fieldErrors.job_title} placeholder="Mathematics Teacher" />
                  <Input label="Department" value={teacherForm.department} onChange={(event) => setTeacherForm((current) => ({ ...current, department: event.target.value }))} error={fieldErrors.department} placeholder="Science" />
                </div>
                <Input label="Employment type" value={teacherForm.employment_type} onChange={(event) => setTeacherForm((current) => ({ ...current, employment_type: event.target.value }))} error={fieldErrors.employment_type} placeholder="Full-time" />
              </>
            ) : (
              <>
                <AdminStudentLookup
                  value={parentForm.student_id}
                  onChange={(studentId) => { setParentForm((current) => ({ ...current, student_id: studentId })); resetErrors(); }}
                  error={fieldErrors.student_id}
                  disabled={isSubmitting}
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Parent email" type="email" value={parentForm.email} onChange={(event) => { setParentForm((current) => ({ ...current, email: event.target.value })); resetErrors(); }} error={fieldErrors.email} required />
                  <SelectControl
                    label="Relationship"
                    value={parentForm.relationship_type}
                    onChange={(value) => setParentForm((current) => ({ ...current, relationship_type: value }))}
                    options={RELATIONSHIP_OPTIONS.map((value) => ({ value, label: titleCase(value) }))}
                    error={fieldErrors.relationship_type}
                    required
                  />
                </div>
              </>
            )}

            <Button type="submit" disabled={isSubmitting || (role === "parent" && !parentForm.student_id)}>
              <MailPlus className="h-4 w-4" />
              {isSubmitting ? "Sending invitation..." : `Send ${role} invitation`}
            </Button>
          </form>
        </Card>

        <Card className="h-fit p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Invitation details</h2>
          {result ? (
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-success/30 bg-success-soft px-4 py-3 text-sm text-emerald-800">Invitation created and ready for delivery.</div>
              <div className="space-y-2 text-sm text-text-muted">
                <p>Email: <span className="font-semibold text-text">{result.invited_email || result.email}</span></p>
                <p>Status: <span className="font-semibold text-text">{titleCase(result.status || "pending")}</span></p>
                {result.expires_at ? <p>Expires: <span className="font-semibold text-text">{new Date(result.expires_at).toLocaleString()}</span></p> : null}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-text-muted">After you send an invitation, you can track it from the Invitations tab.</p>
          )}
        </Card>
      </section>
    </DashboardLayout>
  );
}

export default AdminInvitationPage;
