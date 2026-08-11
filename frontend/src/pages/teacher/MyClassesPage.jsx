import ResourceModulePage from "../shared/ResourceModulePage";
import { classService } from "../../services/academicsService";

const teacherClassConfig = {
  singularLabel: "Class",
  pluralLabel: "Classes",
  canCreate: false,
  canUpdate: false,
  canDelete: false,
  filters: [{ name: "search", label: "Search", placeholder: "Class name or arm" }],
  columns: [
    { key: "name", label: "Class" },
    { key: "arm", label: "Arm", render: (item) => item.arm || "-" },
    {
      key: "teacher",
      label: "Class teacher",
      render: (item) => item.teacher_name || item.class_teacher_name || "Assigned to you",
    },
  ],
  fetchItems: (filters) => classService.getClasses({
    search: filters.search,
    limit: 100,
    active_only: true,
  }),
  mapItemToForm: () => ({}),
  getItemLabel: (item) => [item?.academic_level_name, item?.arm].filter(Boolean).join(" ") || "Class",
};

function MyClassesPage() {
  return (
    <ResourceModulePage
      role="teacher"
      title="My Class Teacher Classes"
      description="Classes where you are assigned as the main class teacher. Subject-teaching rosters remain under Teaching Rosters."
      config={teacherClassConfig}
    />
  );
}

export default MyClassesPage;
