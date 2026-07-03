import { useEffect, useMemo, useRef, useState } from "react";
import { Camera, ImageOff } from "lucide-react";
import Button from "../ui/Button";
import Input from "../ui/Input";
import { parseApiError } from "../../services/api";
import { onboardingService } from "../../services/onboardingService";
import { getAvatarSrcFromRecord } from "../../utils/user";
import { useToast } from "../../hooks/useToast";

const ROLE_FORM_CONFIG = {
  admin: [
    {
      key: "school_identity",
      title: "School identity",
      description: "These values come from registration and stay read-only here.",
      fields: [
        { name: "school_name", label: "School name", readOnly: true },
        { name: "email", label: "School email", type: "email", readOnly: true },
      ],
    },
    {
      key: "school_profile",
      title: "School profile",
      description: "Complete the school profile fields required for onboarding and student admission setup.",
      fields: [
        { name: "admission_number_prefix", label: "Admission prefix", required: true, placeholder: "NHS" },
        { name: "phone", label: "School phone", placeholder: "+2348012345678" },
        { name: "address", label: "Address", type: "textarea", required: true },
        { name: "city", label: "City", required: true },
        { name: "state", label: "State", required: true },
        { name: "country", label: "Country" },
        { name: "timezone", label: "Timezone" },
        { name: "language", label: "Language" },
        { name: "school_bot_whatssap_number", label: "School WhatsApp bot number", placeholder: "+2348012345678" },
        { name: "logo_url", label: "Logo URL", type: "url", placeholder: "https://example.com/logo.png" },
      ],
    },
  ],
  teacher: [
    {
      key: "teacher_profile",
      title: "Teacher profile",
      description: "Complete the teacher profile fields used in your self-service onboarding.",
      fields: [
        { name: "email", label: "Email", type: "email", readOnly: true },
        { name: "first_name", label: "First name", required: true },
        { name: "last_name", label: "Last name", required: true },
        { name: "qualification", label: "Qualification" },
        { name: "specialization", label: "Specialization" },
      ],
    },
  ],
  parent: [
    {
      key: "parent_profile",
      title: "Parent profile",
      description: "Complete the parent profile fields used in your self-service onboarding.",
      fields: [
        { name: "email", label: "Email", type: "email", readOnly: true },
        { name: "first_name", label: "First name", required: true },
        { name: "last_name", label: "Last name", required: true },
        { name: "phone_number", label: "Phone number", placeholder: "+2348012345678" },
        { name: "occupation", label: "Occupation" },
        { name: "address", label: "Address", type: "textarea" },
        { name: "emergency_phone", label: "Emergency phone", placeholder: "+2348012345678" },
      ],
    },
  ],
  student: [
    {
      key: "student_profile",
      title: "Student profile",
      description: "Complete the student profile fields exposed by the backend. School-managed fields stay read-only.",
      fields: [
        { name: "admission_number", label: "Admission number", readOnly: true },
        { name: "first_name", label: "First name", required: true },
        { name: "last_name", label: "Last name", required: true },
        { name: "date_of_birth", label: "Date of birth", type: "date", required: true },
        {
          name: "gender",
          label: "Gender",
          type: "select",
          required: true,
          options: [
            { value: "male", label: "Male" },
            { value: "female", label: "Female" },
          ],
        },
        { name: "passport_photo_url", label: "Passport photo URL", type: "url" },
      ],
    },
  ],
};

const EMPTY_FORM_DATA = {};

const getRoleSections = (role) => ROLE_FORM_CONFIG[onboardingService.normalizeRole(role)] || [];

const buildFormData = (statusData, role) => {
  const currentValues = statusData?.current_values || {};
  const sections = getRoleSections(role);

  return sections.reduce((nextData, section) => {
    section.fields.forEach((field) => {
      const currentValue = currentValues[field.name];
      nextData[field.name] = currentValue ?? "";
    });
    return nextData;
  }, {});
};

function ReadOnlyField({ field, value }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-text-soft">
        {field.label}
      </label>
      <div className="min-h-11 rounded-xl border border-border bg-surface-muted px-3 py-3 text-sm text-text-soft">
        {value || "Not available"}
      </div>
    </div>
  );
}

function EditableField({ field, value, error, onChange }) {
  if (field.type === "select") {
    return (
      <div>
        <label className="mb-1.5 block text-sm font-medium text-text-soft">
          {field.label}
        </label>
        <select
          value={value ?? ""}
          onChange={(event) => onChange(field.name, event.target.value)}
          className="input-base"
          required={field.required}
        >
          <option value="">Select an option</option>
          {(field.options || []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && <p className="mt-1.5 text-xs font-medium text-error">{error}</p>}
      </div>
    );
  }

  if (field.type === "textarea") {
    return (
      <div>
        <label className="mb-1.5 block text-sm font-medium text-text-soft">
          {field.label}
        </label>
        <textarea
          value={value ?? ""}
          onChange={(event) => onChange(field.name, event.target.value)}
          className="input-base min-h-24"
          required={field.required}
          placeholder={field.placeholder}
        />
        {error && <p className="mt-1.5 text-xs font-medium text-error">{error}</p>}
      </div>
    );
  }

  return (
    <Input
      label={field.label}
      type={field.type || "text"}
      value={value ?? ""}
      onChange={(event) => onChange(field.name, event.target.value)}
      error={error}
      required={field.required}
      placeholder={field.placeholder}
    />
  );
}

function PassportPhotoPreview({ data, role }) {
  const imageSrc = getAvatarSrcFromRecord(data);
  const label = role === "admin" ? "Profile image" : "Passport photograph";

  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative h-24 w-24 shrink-0 overflow-hidden rounded-full border border-border-strong bg-surface-muted ring-4 ring-surface">
          {imageSrc ? (
            <img src={imageSrc} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-text-faint">
              <ImageOff className="h-8 w-8" />
            </div>
          )}
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <Camera className="h-4 w-4 text-primary" />
            {label}
          </div>
          <p className="mt-1 text-sm text-text-muted">
            {imageSrc
              ? "Previewing the image URL currently saved for this profile."
              : "A round passport photo will appear here once a valid image URL is saved."}
          </p>
          {imageSrc && (
            <p className="mt-2 truncate text-xs font-medium text-text-faint" title={imageSrc}>
              {imageSrc}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function ProfileCompletionForm({
  role,
  submitLabel = "Save profile",
  onSaved,
  onProfileStateResolved,
  initialStatusData = null,
}) {
  const normalizedRole = onboardingService.normalizeRole(role);
  const callbacksRef = useRef({ onSaved, onProfileStateResolved });
  const [statusData, setStatusData] = useState(initialStatusData);
  const [formData, setFormData] = useState(() => buildFormData(initialStatusData, normalizedRole));
  const [fieldErrors, setFieldErrors] = useState({});
  const [loadError, setLoadError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(!initialStatusData);
  const { showSuccess, showError } = useToast();

  const sections = useMemo(() => getRoleSections(normalizedRole), [normalizedRole]);

  useEffect(() => {
    callbacksRef.current = { onSaved, onProfileStateResolved };
  }, [onSaved, onProfileStateResolved]);

  useEffect(() => {
    if (!initialStatusData) return;

    setStatusData(initialStatusData);
    setFormData(buildFormData(initialStatusData, normalizedRole));
    const nextUser = onboardingService.updateSessionUserFromStatus(normalizedRole, initialStatusData);
    callbacksRef.current.onProfileStateResolved?.({
      completed: !initialStatusData.onboarding_required,
      status: initialStatusData,
      user: nextUser,
    });
    setIsLoading(false);
  }, [initialStatusData, normalizedRole]);

  useEffect(() => {
    let mounted = true;

    async function loadStatus() {
      if (initialStatusData || !onboardingService.supportsRole(normalizedRole)) {
        if (!initialStatusData) {
          setStatusData(null);
          setFormData(EMPTY_FORM_DATA);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      setLoadError(null);

      try {
        const nextStatus = await onboardingService.getOnboardingStatus(normalizedRole);
        if (!mounted) return;

        setStatusData(nextStatus);
        setFormData(buildFormData(nextStatus, normalizedRole));
        const nextUser = onboardingService.updateSessionUserFromStatus(normalizedRole, nextStatus);
        callbacksRef.current.onProfileStateResolved?.({
          completed: !nextStatus?.onboarding_required,
          status: nextStatus,
          user: nextUser,
        });
      } catch (error) {
        if (!mounted) return;
        const parsed = parseApiError(error, "Failed to load your onboarding details.");
        setLoadError(parsed.message);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadStatus();

    return () => {
      mounted = false;
    };
  }, [initialStatusData, normalizedRole]);

  const handleChange = (fieldName, value) => {
    setFormData((current) => ({
      ...current,
      [fieldName]: value,
    }));
    setFieldErrors((current) => ({
      ...current,
      [fieldName]: undefined,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!statusData) return;

    setIsSubmitting(true);
    setFieldErrors({});

    try {
      const payload = sections.reduce((nextPayload, section) => {
        section.fields
          .filter((field) => !field.readOnly)
          .forEach((field) => {
            const rawValue = formData[field.name];
            nextPayload[field.name] = rawValue === "" ? null : rawValue;
          });
        return nextPayload;
      }, {});

      await onboardingService.submitOnboarding(normalizedRole, payload);
      const nextStatus = await onboardingService.getOnboardingStatus(normalizedRole);
      const nextUser = onboardingService.updateSessionUserFromStatus(normalizedRole, nextStatus);

      setStatusData(nextStatus);
      setFormData(buildFormData(nextStatus, normalizedRole));
      showSuccess("Profile updated successfully.");

      callbacksRef.current.onProfileStateResolved?.({
        completed: !nextStatus.onboarding_required,
        status: nextStatus,
        user: nextUser,
      });
      callbacksRef.current.onSaved?.(nextStatus, nextUser);
    } catch (error) {
      const parsed = parseApiError(error, "Failed to update your profile.");
      setFieldErrors(parsed.fieldErrors || {});
      showError(parsed.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!onboardingService.supportsRole(normalizedRole)) {
    return (
      <div className="rounded-2xl border border-border bg-surface-muted/40 px-4 py-3 text-sm text-text-muted">
        Profile editing is not available for this role yet.
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {loadError && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      <PassportPhotoPreview
        role={normalizedRole}
        data={{
          ...(statusData?.current_values || {}),
          ...formData,
        }}
      />

      {sections.map((section) => (
        <div key={section.key} className="space-y-4 rounded-2xl border border-border bg-surface-muted/40 p-4">
          <div>
            <h3 className="text-sm font-semibold text-text">{section.title}</h3>
            {section.description && (
              <p className="mt-1 text-xs text-text-muted">{section.description}</p>
            )}
          </div>

          {isLoading ? (
            <p className="text-sm text-text-muted">Loading profile details...</p>
          ) : (
            section.fields.map((field) => {
              const value = formData[field.name] ?? "";

              return field.readOnly ? (
                <ReadOnlyField
                  key={`${section.key}-${field.name}`}
                  field={field}
                  value={value}
                />
              ) : (
                <EditableField
                  key={`${section.key}-${field.name}`}
                  field={field}
                  value={value}
                  error={fieldErrors[field.name]}
                  onChange={handleChange}
                />
              );
            })
          )}
        </div>
      ))}

      <Button type="submit" className="w-full sm:w-auto" disabled={isSubmitting || isLoading || !statusData}>
        {isSubmitting ? "Saving..." : submitLabel}
      </Button>
    </form>
  );
}

export default ProfileCompletionForm;
