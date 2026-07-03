import ResourceModulePage from "../shared/ResourceModulePage";
import { academicService } from "../../services/academicService";

const titleCase = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const subjectLabel = (item) => item?.subject_name || item?.name || item?.subject_code || item?.code || "Subject";
const subjectCode = (item) => item?.subject_code || item?.code || "-";
const classLabel = (item) => [item?.class_name || item?.name, item?.class_arm || item?.arm].filter(Boolean).join(" ") || "Class";

const buildAssignedSubjectRows = (assignments = []) => {
  const rowsBySubject = new Map();

  assignments.forEach((assignment) => {
    const subjectId = assignment.subject_id || assignment.id;
    const current = rowsBySubject.get(subjectId) || {
      id: subjectId,
      name: subjectLabel(assignment),
      code: subjectCode(assignment),
      is_active: false,
      classes: [],
      assignment_count: 0,
    };

    current.is_active = current.is_active || assignment.is_active !== false;
    current.assignment_count += 1;
    current.classes.push(classLabel(assignment));
    rowsBySubject.set(subjectId, current);
  });

  return Array.from(rowsBySubject.values()).map((row) => ({
    ...row,
    classes: Array.from(new Set(row.classes)).filter(Boolean),
  }));
};

const teacherAssignedSubjectConfig = {
  singularLabel: "Assigned subject",
  pluralLabel: "Assigned subjects",
  canCreate: false,
  canUpdate: false,
  canDelete: false,
  filters: [
    { name: "search", label: "Search", placeholder: "Subject or class name" },
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
      key: "classes",
      label: "Classes",
      render: (item) => item.classes?.join(", ") || "No class attached",
    },
    {
      key: "assignment_count",
      label: "Assignments",
      render: (item) => `${item.assignment_count || 0} class${item.assignment_count === 1 ? "" : "es"}`,
    },
    {
      key: "is_active",
      label: "Status",
      render: (item) => titleCase(item.is_active ? "active" : "inactive"),
    },
  ],
  fetchItems: async (filters = {}) => {
    const response = await academicService.listMyTeacherAssignments();
    let rows = buildAssignedSubjectRows(response?.items || []);

    if (filters.search) {
      const query = filters.search.trim().toLowerCase();
      rows = rows.filter((row) =>
        [row.name, row.code, ...(row.classes || [])]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query))
      );
    }

    if (filters.isActive === "true") rows = rows.filter((row) => row.is_active);
    if (filters.isActive === "false") rows = rows.filter((row) => !row.is_active);

    return { items: rows, total: rows.length };
  },
  mapItemToForm: () => ({}),
};

function SubjectsPage() {
  return (
    <ResourceModulePage
      role="teacher"
      title="Assigned Subjects"
      description="Browse the subjects and class groups currently assigned to you."
      config={teacherAssignedSubjectConfig}
    />
  );
}

export default SubjectsPage;
