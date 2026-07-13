import { parentService } from "../services/parentService";
import { studentService } from "../services/studentService";
import { teacherService } from "../services/teacherService";
import { tenantService } from "../services/tenant.service";

const COMMON_USER_FIELDS = [
  { source: "user", name: "firstname", label: "First name", required: true },
  { source: "user", name: "lastname", label: "Last name", required: true },
  { source: "user", name: "email", label: "Email", type: "email", required: true },
  {
    source: "user",
    name: "phone_number",
    label: "Phone number",
    placeholder: "+2348012345678",
    required: true,
  },
  {
    source: "user",
    name: "whatsapp_id",
    label: "WhatsApp ID",
    placeholder: "+2348012345678",
  },
];

const STUDENT_USER_FIELDS = COMMON_USER_FIELDS.filter((field) => field.name !== "email");

const hasRequiredValues = (fields, sourceData) =>
  fields
    .filter((field) => field.required)
    .some((field) => {
      const value = sourceData?.[field.name];
      return value === null || value === undefined || value === "";
    });

const STUDENT_GENDER_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
];

const getTenantContext = async (user) => {
  if (!user?.tenant_id) return null;
  if (user?.tenant?.id === user.tenant_id) return user.tenant;
  return tenantService.getTenant(user.tenant_id);
};

const ROLE_PROFILE_CONFIG = {
  admin: {
    sections: [
      {
        key: "user",
        title: "Personal details",
        description: "These fields belong to the core user account.",
        fields: COMMON_USER_FIELDS,
      },
      {
        key: "tenant",
        title: "School details",
        description: "These fields are stored on the tenant record and managed by administrators.",
        fields: [
          { source: "tenant", name: "school_name", label: "School name", required: true },
          { source: "tenant", name: "email", label: "School email", type: "email", required: true },
          { source: "tenant", name: "phone", label: "School phone" },
          {
            source: "tenant",
            name: "admission_number_prefix",
            label: "Admission prefix",
            required: true,
            placeholder: "WVS",
            helperText:
              "This prefix will be used to generate student admission numbers, e.g. WVS-2026-48291.",
          },
          { source: "tenant", name: "address", label: "Address", type: "textarea" },
          { source: "tenant", name: "city", label: "City" },
          { source: "tenant", name: "state", label: "State" },
          { source: "tenant", name: "country", label: "Country" },
        ],
      },
    ],
    loadContext: async (user) => ({
      tenant: await getTenantContext(user),
      roleProfile: null,
    }),
    saveRoleProfile: null,
    isRoleIncomplete: ({ tenant }) =>
      !tenant ||
      hasRequiredValues(ROLE_PROFILE_CONFIG.admin.sections[1].fields, tenant) ||
      tenant.onboarding_completed !== true,
  },
  teacher: {
    sections: [
      {
        key: "user",
        title: "Personal details",
        description: "These fields belong to the core user account.",
        fields: COMMON_USER_FIELDS,
      },
      {
        key: "roleProfile",
        title: "Teacher profile",
        description: "Teacher-specific fields come from the teacher profile endpoint.",
        fields: [
          { source: "roleProfile", name: "staff_id", label: "Staff ID" },
          { source: "roleProfile", name: "qualification", label: "Qualification" },
          { source: "roleProfile", name: "specialization", label: "Specialization" },
        ],
      },
    ],
    loadContext: async () => ({
      tenant: null,
      roleProfile: await teacherService.getMyTeacher(),
    }),
    saveRoleProfile: (payload) => teacherService.updateMyTeacherProfile(payload),
    isRoleIncomplete: () => false,
  },
  student: {
    sections: [
      {
        key: "user",
        title: "Personal details",
        description: "Student identity is tied to the admission number.",
        fields: STUDENT_USER_FIELDS,
      },
      {
        key: "roleProfile",
        title: "Student profile",
        description:
          "Some student fields are managed by the school. You can only update the self-service fields exposed by the backend.",
        fields: [
          {
            source: "roleProfile",
            name: "admission_number",
            label: "Admission number",
            readOnly: true,
            emptyLabel: "Pending school assignment",
          },
          {
            source: "roleProfile",
            name: "class_id",
            label: "Assigned class",
            readOnly: true,
            emptyLabel: "Pending school assignment",
          },
          {
            source: "roleProfile",
            name: "date_of_birth",
            label: "Date of birth",
            readOnly: true,
            emptyLabel: "Managed by school admin",
          },
          {
            source: "roleProfile",
            name: "profile_status",
            label: "Profile status",
            readOnly: true,
            emptyLabel: "incomplete",
          },
          {
            source: "roleProfile",
            name: "gender",
            label: "Gender",
            type: "select",
            required: true,
            options: STUDENT_GENDER_OPTIONS,
          },
        ],
      },
    ],
    loadContext: async () => ({
      tenant: null,
      roleProfile: await studentService.getMyStudent(),
    }),
    saveRoleProfile: (payload) => studentService.updateMyStudentProfile(payload),
    isRoleIncomplete: ({ roleProfile }) => roleProfile?.profile_status !== "complete",
  },
  parent: {
    sections: [
      {
        key: "user",
        title: "Personal details",
        description: "These fields belong to the core user account.",
        fields: COMMON_USER_FIELDS,
      },
      {
        key: "roleProfile",
        title: "Parent profile",
        description: "Parent-specific fields come from the parent profile endpoint.",
        fields: [
          { source: "roleProfile", name: "occupation", label: "Occupation" },
          { source: "roleProfile", name: "address", label: "Address", type: "textarea" },
          { source: "roleProfile", name: "emergency_phone", label: "Emergency phone" },
        ],
      },
    ],
    loadContext: async () => ({
      tenant: null,
      roleProfile: await parentService.getMyParent(),
    }),
    saveRoleProfile: (payload) => parentService.updateMyParentProfile(payload),
    isRoleIncomplete: () => false,
  },
  superadmin: {
    sections: [
      {
        key: "user",
        title: "Personal details",
        description: "These fields belong to the core platform administrator account.",
        fields: COMMON_USER_FIELDS,
      },
    ],
    loadContext: async () => ({
      tenant: null,
      roleProfile: null,
    }),
    saveRoleProfile: null,
    isRoleIncomplete: () => false,
  },
};

export default ROLE_PROFILE_CONFIG;
