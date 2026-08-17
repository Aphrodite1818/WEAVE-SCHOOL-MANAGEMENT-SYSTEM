import AcademicLevelsWorkspace from "../academic-admin/AcademicLevelsWorkspace";
import AcademicSetupWorkspace from "../academic-admin/AcademicSetupWorkspace";
import ArmLabelsWorkspace from "../academic-admin/ArmLabelsWorkspace";
import ClassesWorkspace from "../academic-admin/ClassesWorkspace";
import CurriculumWorkspace from "../academic-admin/CurriculumWorkspace";
import DepartmentsWorkspace from "../academic-admin/DepartmentsWorkspace";
import ProgressionWorkspace from "../academic-admin/ProgressionWorkspace";
import TeacherAssignmentsWorkspace from "../academic-admin/TeacherAssignmentsWorkspace";
import SchoolCalendarGuide from "../schoolCalendar/components/SchoolCalendarGuide";
import SchoolCalendarWorkspace from "../schoolCalendar/components/SchoolCalendarWorkspace";
import TenantBrandingPage from "../../pages/admin/TenantBrandingPage";

const ADMIN_GUIDE_WORKSPACE_CONFIG = Object.freeze({
  school_logo: { kind: "branding" },
  levels: { kind: "levels", activeTab: "create" },
  arms: { kind: "arm-labels", activeTab: "create" },
  classes: { kind: "classes", activeTab: "create" },
  departments: { kind: "departments" },
  subjects: { kind: "academic", domain: "subjects", activeTab: "create" },
  curriculum: { kind: "curriculum" },
  session: { kind: "academic", domain: "sessions", activeTab: "create" },
  term: { kind: "academic", domain: "terms", activeTab: "create" },
  calendar: { kind: "calendar", activeTab: "setup" },
  assignments: { kind: "assignments", activeTab: "assign" },
  progression: { kind: "progression" },
});

function AdminGuideTaskWorkspace({ stepId }) {
  const config = ADMIN_GUIDE_WORKSPACE_CONFIG[stepId];
  if (!config) return null;

  if (config.kind === "branding") return <TenantBrandingPage embedded />;
  if (config.kind === "levels") return <AcademicLevelsWorkspace activeTab={config.activeTab} />;
  if (config.kind === "arm-labels") return <ArmLabelsWorkspace activeTab={config.activeTab} />;
  if (config.kind === "classes") return <ClassesWorkspace activeTab={config.activeTab} />;
  if (config.kind === "departments") return <DepartmentsWorkspace />;
  if (config.kind === "academic") {
    return <AcademicSetupWorkspace domain={config.domain} activeTab={config.activeTab} />;
  }
  if (config.kind === "curriculum") return <CurriculumWorkspace />;
  if (config.kind === "assignments") {
    return <TeacherAssignmentsWorkspace activeTab={config.activeTab} />;
  }
  if (config.kind === "progression") return <ProgressionWorkspace />;
  if (config.kind === "calendar") {
    return (
      <div className="space-y-4">
        <SchoolCalendarGuide activeTab={config.activeTab} />
        <SchoolCalendarWorkspace activeTab={config.activeTab} />
      </div>
    );
  }

  return null;
}

export default AdminGuideTaskWorkspace;
