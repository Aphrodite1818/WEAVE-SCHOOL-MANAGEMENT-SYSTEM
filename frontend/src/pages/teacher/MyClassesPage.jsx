import ResourceModulePage from "../shared/ResourceModulePage";
import { displayClass } from "../../components/academic/academicDisplay";
import { classService } from "../../services/academicsService";

const teacherClassConfig = {
  singularLabel: "Class",
  pluralLabel: "Classes",
  canCreate: false,
  canUpdate: false,
  canDelete: false,
  filters: [{ name: "search", label: "Search", placeholder: "Class name or arm" }],
  columns: [
    { key: "academic_level_name", label: "Class", render: (item) => displayClass(item) },
    { key: "arm_label", label: "Arm", render: (item) => item.arm_label || "-" },
    {
      key: "teacher",
      label: "Class teacher",
      render: (item) => item.teacher_name || item.class_teacher_name || "Assigned to you",
    },
  ],
  fetchItems: (filters) => classService.getClasses({
    search: filters.search,
    limit: 100,
    activeOnly: true,
  }),
  mapItemToForm: () => ({}),
  getItemLabel: (item) => displayClass(item),
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
