import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Card from "../../components/ui/Card";
import { authSession, parseApiError } from "../../services/api";
import { studentService } from "../../services/studentService";
import { displayName } from "../../utils/user";

const INITIAL_FORM = {
  current_password: "",
  new_password: "",
  confirm_password: "",
};

function StudentChangePasswordPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const currentUser = authSession.getUser();

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => ({ ...current, [name]: undefined }));
    setError(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setFieldErrors({});

    try {
      const updatedStudent = await studentService.changeMyPassword(formData);
      authSession.setUser({
        ...(currentUser || {}),
        ...updatedStudent,
        role: currentUser?.role || "student",
        actor_type: currentUser?.actor_type || "student",
        password_reset_required: false,
      });
      navigate("/student/dashboard", { replace: true });
    } catch (err) {
      const apiError = parseApiError(err, "Failed to update your password.");
      setFieldErrors(apiError.fieldErrors);
      setError(apiError.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DashboardLayout
      role="student"
      title="Create Your Password"
      description={`Finish secure access for ${displayName(currentUser)} before entering your dashboard.`}
      onboardingModalEnabled={false}
    >
      <div className="mx-auto max-w-2xl">
        <Card className="p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-text">Password setup required</h2>
              <p className="mt-1 text-sm text-text-muted">
                Use your current password or the access code from your school to create your own password.
              </p>
            </div>
          </div>

          {error && (
            <div className="mt-5 rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <Input
              label="Current password or access code"
              type="password"
              name="current_password"
              value={formData.current_password}
              onChange={handleChange}
              error={fieldErrors.current_password}
              required
            />
            <Input
              label="New password"
              type="password"
              name="new_password"
              value={formData.new_password}
              onChange={handleChange}
              error={fieldErrors.new_password}
              hint="Use at least 8 characters with uppercase, lowercase, and a number."
              required
            />
            <Input
              label="Confirm new password"
              type="password"
              name="confirm_password"
              value={formData.confirm_password}
              onChange={handleChange}
              error={fieldErrors.confirm_password}
              required
            />
            <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
              {isSubmitting ? "Updating password..." : "Save new password"}
            </Button>
          </form>
        </Card>
      </div>
    </DashboardLayout>
  );
}

export default StudentChangePasswordPage;
