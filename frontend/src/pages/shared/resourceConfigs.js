import React from "react";
import Badge from "../../components/ui/Badge";
import { armLabelService, classService } from "../../services/academicsService";
import { parentService } from "../../services/parentService";
import { studentService } from "../../services/studentService";
import { subjectService } from "../../services/subject.service";
import { teacherService } from "../../services/teacherService";
import { displayName, fullName as actorFullName } from "../../utils/user";

const studentStatuses = [
  "active",
  "withdrawn",
  "suspended",
  "graduated",
  "expelled",
];

const titleCase = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const optionsFrom = (items, labelFn) =>
  (items || []).map((item) => ({
    value: item.id,
    label: labelFn(item),
  }));

const listItems = (result) =>
  Array.isArray(result)
    ? result
    : Array.isArray(result?.items)
      ? result.items
      : [];

const enumOptions = (values) =>
  values.map((value) => ({ value, label: titleCase(value) }));

const fullName = (item) => actorFullName(item) || item?.id || "Unknown";

const className = (item) =>
  item?.display_name ||
  [item?.academic_level_name, item?.department_name, item?.arm_label]
    .filter(Boolean)
    .join(" ") ||
  item?.id ||
  "Unknown class";

const subjectName = (item) =>
  [item?.name, item?.code ? `(${item.code})` : ""].filter(Boolean).join(" ");

const byId = (items) =>
  (items || []).reduce((map, item) => {
    map[item.id] = item;
    return map;
  }, {});

const labelFromMap = (map, id, fallback = "-") =>
  id && map[id]
    ? fullName(map[id]) || className(map[id]) || subjectName(map[id])
    : fallback;

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

const statusBadge = (value, variant = "default") =>
  React.createElement(Badge, { variant }, titleCase(value || "unknown"));

const compactPayload = (payload) =>
  Object.entries(payload).reduce((nextPayload, [key, value]) => {
    nextPayload[key] = value === "" ? null : value;
    return nextPayload;
  }, {});

const loadAcademicContext = async ({ role = "admin" } = {}) => {
  const isTeacher = role === "teacher";
  const [classes, subjects, students] = await Promise.all([
    classService.getClasses({ limit: 100 }),
    isTeacher
      ? teacherService.getMySubjects({ limit: 100, isActive: true })
      : subjectService.getSubjects({ limit: 100, isActive: true }),
    isTeacher
      ? studentService.getStudents({ limit: 100 })
      : studentService.getAdminStudents({ limit: 100 }),
  ]);

  const classItems = listItems(classes);
  const subjectItems = listItems(subjects);
  const studentItems = listItems(students);

  return {
    classes: classItems,
    subjects: subjectItems,
    students: studentItems,
    classById: byId(classItems),
    subjectById: byId(subjectItems),
    studentById: byId(studentItems),
  };
};

const loadClassContext = async () => {
  const [teachers, armLabels] = await Promise.all([
    teacherService.getTeachers({ limit: 100 }),
    armLabelService.getArmLabels({ activeOnly: true }),
  ]);
  const teacherItems = teachers?.items || [];
  const armLabelItems = listItems(armLabels);

  return {
    teachers: teacherItems,
    armLabels: armLabelItems,
    teacherById: byId(teacherItems),
  };
};

const loadSubjectContext = async () => {
  const teachers = await teacherService.getTeachers({ limit: 100 });

  const teacherItems = (teachers?.items || []).filter(
    (teacher) => teacher.status === "active",
  );

  return {
    teachers: teacherItems,
    teacherById: byId(teacherItems),
  };
};

const classColumns = [
  { key: "name", label: "Class" },
  { key: "level", label: "Level", render: (item) => item.level || "-" },
  { key: "arm_label", label: "Arm", render: (item) => item.arm_label || "-" },
];

const classFields = (context) => [
  { name: "name", label: "Class name", required: true },
  { name: "level", label: "Level", placeholder: "Junior Secondary 1" },
  {
    name: "arm_label_id",
    label: "Arm",
    type: "select",
    options: optionsFrom(context.armLabels, (item) => item.label),
  },
  {
    name: "teacher_id",
    label: "Class teacher",
    type: "select",
    options: optionsFrom(context.teachers, (teacher) => displayName(teacher)),
  },
];

export const getClassResourceConfig = ({ role, writable }) => ({
  singularLabel: "Class",
  pluralLabel: "Classes",
  formHelp:
    "Classes are created by admins. Teachers can view the classes exposed by the API.",
  canCreate: writable,
  canUpdate: writable,
  canDelete: writable,
  loadContext: writable ? loadClassContext : undefined,
  initialForm: { name: "", level: "", arm_label_id: "", teacher_id: "" },
  fields: classFields,
  filters: [{ name: "search", label: "Search", placeholder: "Class name" }],
  columns: (context) => [
    ...classColumns,
    {
      key: "teacher_id",
      label: "Teacher",
      render: (item) => {
        if (!item.teacher_id) return "Unassigned";
        const teacher = context.teacherById?.[item.teacher_id];
        return teacher ? displayName(teacher) : "Assigned";
      },
    },
  ],
  fetchItems: (filters) => classService.getClasses({ search: filters.search }),
  createItem: (payload) => classService.createClass(payload),
  updateItem: (id, payload) => classService.updateClass(id, payload),
  deleteItem: (id) => classService.deleteClass(id),
  mapItemToForm: (item) => ({
    name: item.name || "",
    level: item.level || "",
    arm_label_id: item.arm_label_id || "",
    teacher_id: item.teacher_id || "",
  }),
  getItemLabel: (item) => className(item),
  role,
});

export const subjectReadOnlyResourceConfig = {
  singularLabel: "Subject",
  pluralLabel: "Subjects",
  canCreate: false,
  canUpdate: false,
  canDelete: false,
  initialFilters: {
    isActive: "true",
  },
  filters: [
    { name: "search", label: "Search", placeholder: "Subject name" },
    {
      name: "isActive",
      label: "Status",
      type: "select",
      options: [
        { value: "true", label: "Active" },
        { value: "false", label: "Inactive" },
      ],
    },
  ],
  columns: [
    { key: "name", label: "Subject" },
    { key: "code", label: "Code", render: (item) => item.code || "-" },
    {
      key: "is_active",
      label: "Status",
      render: (item) => (item.is_active ? "Active" : "Inactive"),
    },
    {
      key: "description",
      label: "Description",
      render: (item) => item.description || "-",
    },
  ],
  fetchItems: (filters) =>
    subjectService.getSubjects({
      search: filters.search,
      isActive:
        filters.isActive === "true"
          ? true
          : filters.isActive === "false"
            ? false
            : undefined,
    }),
  mapItemToForm: () => ({}),
};

export const teacherSubjectResourceConfig = {
  ...subjectReadOnlyResourceConfig,
  fetchItems: (filters) =>
    teacherService.getMySubjects({
      search: filters.search,
      isActive:
        filters.isActive === "true"
          ? true
          : filters.isActive === "false"
            ? false
            : undefined,
    }),
};

export const subjectResourceConfig = {
  singularLabel: "Subject",
  pluralLabel: "Subjects",
  formHelp:
    "Subjects define the academic catalog teachers and classes can be assigned to.",
  canCreate: true,
  canUpdate: true,
  canDelete: true,
  loadContext: loadSubjectContext,
  initialForm: {
    name: "",
    code: "",
    description: "",
    is_active: "true",
  },
  initialFilters: subjectReadOnlyResourceConfig.initialFilters,
  fields: () => [
    { name: "name", label: "Subject name", required: true },
    { name: "code", label: "Subject code" },
    { name: "description", label: "Description", type: "textarea" },
    {
      name: "is_active",
      label: "Status",
      type: "select",
      options: [
        { value: "true", label: "Active" },
        { value: "false", label: "Inactive" },
      ],
    },
  ],
  filters: subjectReadOnlyResourceConfig.filters,
  columns: [...subjectReadOnlyResourceConfig.columns],
  fetchItems: subjectReadOnlyResourceConfig.fetchItems,
  buildPayload: (formData) =>
    compactPayload({
      name: formData.name,
      code: formData.code,
      description: formData.description,
      is_active: formData.is_active,
    }),
  createItem: (payload) =>
    subjectService.createSubject({
      name: payload.name,
      code: payload.code,
      description: payload.description,
    }),
  updateItem: async (id, payload) => {
    await subjectService.updateSubject(id, {
      name: payload.name,
      code: payload.code,
      description: payload.description,
    });

    if (payload.is_active === "true") {
      await subjectService.activateSubject(id);
    } else if (payload.is_active === "false") {
      await subjectService.deactivateSubject(id);
    }
  },
  deleteItem: (id) => subjectService.deleteSubject(id),
  mapItemToForm: (item) => ({
    name: item.name || "",
    code: item.code || "",
    description: item.description || "",
    is_active: item.is_active ? "true" : "false",
  }),
  getItemLabel: (item) => subjectName(item),
};

export const teacherResourceConfig = {
  singularLabel: "Teacher profile",
  pluralLabel: "Teacher profiles",
  formHelp:
    "Review teacher records and update staff details. Subject teaching assignments are managed in Academic Hub.",
  canCreate: false,
  canUpdate: false,
  canDelete: false,
  loadContext: () => loadAcademicContext(),
  initialForm: {
    staff_id: "",
    qualification: "",
    specialization: "",
  },
  fields: () => [
    { name: "staff_id", label: "Staff ID" },
    { name: "qualification", label: "Qualification" },
    { name: "specialization", label: "Specialization" },
  ],
  columns: () => [
    {
      key: "teacher",
      label: "Teacher",
      render: (item) => displayName(item),
    },
    {
      key: "email",
      label: "Email",
      render: (item) => optionalValue(item.email),
    },
    {
      key: "staff_id",
      label: "Staff ID",
      render: (item) => item.staff_id || "-",
    },
    {
      key: "qualification",
      label: "Qualification",
      render: (item) => item.qualification || "-",
    },
    {
      key: "specialization",
      label: "Specialization",
      render: (item) => item.specialization || "-",
    },
  ],
  fetchItems: () => teacherService.getTeachers({ limit: 100 }),
  updateItem: undefined,
  deleteItem: undefined,
  buildPayload: (formData) =>
    compactPayload({
      staff_id: formData.staff_id,
      qualification: formData.qualification,
      specialization: formData.specialization,
    }),
  mapItemToForm: (item) => ({
    staff_id: item.staff_id || "",
    qualification: item.qualification || "",
    specialization: item.specialization || "",
  }),
  getItemLabel: (item) => displayName(item),
};

export const getStudentResourceConfig = ({ writable, role = "admin" }) => ({
  singularLabel: "Student",
  pluralLabel: "Students",
  formHelp:
    "Review student records created by tenant admins, update academic details, and manage first-login readiness safely.",
  canCreate: false,
  canUpdate: writable,
  canDelete: false,
  loadContext: () => loadAcademicContext({ role }),
  initialForm: {
    gender: "",
    date_of_birth: "",
  },
  initialFilters: {
    status: "active",
  },
  fields: () => [
    {
      name: "gender",
      label: "Gender",
      type: "select",
      options: enumOptions(["male", "female"]),
    },
    { name: "date_of_birth", label: "Date of birth", type: "date" },
  ],
  filters: (context) => [
    { name: "search", label: "Search", placeholder: "Name or admission no." },
    {
      name: "classId",
      label: "Class",
      type: "select",
      options: optionsFrom(context.classes, className),
    },
    {
      name: "status",
      label: "Status",
      type: "select",
      options: enumOptions(studentStatuses),
    },
  ],
  columns: () => [
    { key: "name", label: "Full Name", render: (item) => displayName(item) },
    {
      key: "admission_number",
      label: "Admission Number",
      render: (item) => optionalValue(item.admission_number, "Pending"),
    },
    {
      key: "admission_date",
      label: "Admission Date",
      render: (item) => formatDateValue(item.admission_date),
    },
    {
      key: "password_reset_required",
      label: "Password Reset",
      render: (item) =>
        statusBadge(
          item.password_reset_required ? "required" : "completed",
          item.password_reset_required ? "warning" : "success",
        ),
    },
    {
      key: "profile_status",
      label: "Profile Status",
      render: (item) =>
        statusBadge(
          item.profile_status,
          item.profile_status === "incomplete" ? "warning" : "success",
        ),
    },
    {
      key: "status",
      label: "Academic Status",
      render: (item) =>
        statusBadge(
          item.status,
          item.status === "active" ? "success" : "default",
        ),
    },
  ],
  fetchItems: (filters) =>
    (role === "teacher"
      ? studentService.getStudents
      : studentService.getAdminStudents)({
      search: filters.search,
      classId: filters.classId,
      status: filters.status,
    }),
  createItem: undefined,
  updateItem: (id, payload) => studentService.updateAdminStudent(id, payload),
  deleteItem: undefined,
  buildPayload: (formData) => compactPayload(formData),
  mapItemToForm: (item) => ({
    gender: item.gender || "",
    date_of_birth: item.date_of_birth || "",
  }),
  getItemLabel: (item) => displayName(item),
});

export const parentResourceConfig = {
  singularLabel: "Parent profile",
  pluralLabel: "Parent profiles",
  formHelp:
    "Review parent records created by tenant admins and maintain optional contact details after invite acceptance.",
  canCreate: false,
  canUpdate: false,
  canDelete: false,
  initialForm: {
    occupation: "",
    address: "",
    emergency_phone: "",
  },
  fields: [
    { name: "occupation", label: "Occupation" },
    { name: "address", label: "Address", type: "textarea" },
    {
      name: "emergency_phone",
      label: "Emergency phone",
      placeholder: "+2348012345678",
    },
  ],
  columns: [
    { key: "name", label: "Full Name", render: (item) => displayName(item) },
    {
      key: "email",
      label: "Email",
      render: (item) => optionalValue(item.email),
    },
    {
      key: "phone_number",
      label: "Phone Number",
      render: (item) => optionalValue(item.phone_number),
    },
    {
      key: "occupation",
      label: "Occupation",
      render: (item) => optionalValue(item.occupation),
    },
    {
      key: "emergency_phone",
      label: "Emergency Phone",
      render: (item) => optionalValue(item.emergency_phone),
    },
  ],
  fetchItems: () => parentService.getParents({ limit: 100 }),
  updateItem: undefined,
  deleteItem: undefined,
  buildPayload: (formData) => compactPayload(formData),
  mapItemToForm: (item) => ({
    occupation: item.occupation || "",
    address: item.address || "",
    emergency_phone: item.emergency_phone || "",
  }),
  getItemLabel: (item) => displayName(item),
};

export const summaryLoaders = {
  classes: () => classService.getClasses({ limit: 1 }),
  students: () => studentService.getStudents({ limit: 1 }),
  teachers: () => teacherService.getTeachers({ limit: 1 }),
};

export { className, fullName, labelFromMap, loadAcademicContext };
