import { Link, useSearchParams } from "react-router-dom";
import { ROLE_GUIDES } from "./roleGuideConfig";
import AdminCalendarSetupWorkspace from "./AdminCalendarSetupWorkspace";
import SubjectsWorkspace from "../academic-admin/SubjectsWorkspace";
import AcademicPeriodsWorkspace from "../academic-admin/AcademicPeriodsWorkspace";
import AcademicLevelsWorkspace from "../academic-admin/AcademicLevelsWorkspace";
import ArmLabelsWorkspace from "../academic-admin/ArmLabelsWorkspace";
import ClassesWorkspace from "../academic-admin/ClassesWorkspace";
import CurriculumWorkspace from "../academic-admin/CurriculumWorkspace";
import DepartmentsWorkspace from "../academic-admin/DepartmentsWorkspace";
import ProgressionWorkspace from "../academic-admin/ProgressionWorkspace";
import TeacherAssignmentsWorkspace from "../academic-admin/TeacherAssignmentsWorkspace";
import TenantBrandingPage from "../../pages/admin/TenantBrandingPage";

const ADMIN_GUIDE_WORKSPACE_CONFIG = Object.freeze({
  school_logo: { kind: "branding" },
  levels: { kind: "levels", activeTab: "create" },
  arms: { kind: "arm-labels", activeTab: "create" },
  classes: { kind: "classes", activeTab: "create" },
  departments: { kind: "departments", activeTab: "create" },
  subjects: { kind: "subjects", activeTab: "create" },
  curriculum: { kind: "curriculum" },
  session: { kind: "periods", domain: "sessions", activeTab: "create" },
  term: { kind: "periods", domain: "terms", activeTab: "create" },
  calendar: { kind: "calendar", activeTab: "setup" },
  assignments: { kind: "assignments", activeTab: "assign" },
  progression: { kind: "progression" },
});

function AdminGuideTaskWorkspace({
  stepId,
  onSaved,
  setupTermId,
  setupSessionId,
  setupSessionName,
}) {
  const [searchParams] = useSearchParams();
  const config = ADMIN_GUIDE_WORKSPACE_CONFIG[stepId];
  const activeTab = searchParams.get("view") || config?.activeTab;

  if (!config) {
    const step = ROLE_GUIDES.admin.steps.find((item) => item.id === stepId);
    return step ? (
      <Link
        className="inline-flex rounded-lg bg-primary px-4 py-3 font-semibold text-white"
        to={step.to}
      >
        {step.actionLabel}
      </Link>
    ) : null;
  }

  if (config.kind === "subjects") return <SubjectsWorkspace activeTab={activeTab} />;
  if (config.kind === "periods") {
    return (
      <AcademicPeriodsWorkspace
        key={stepId}
        domain={config.domain}
        activeTab={activeTab}
        guided
        onSaved={onSaved}
        setupSessionName={setupSessionName}
        setupRecordId={stepId === "session" ? setupSessionId : setupTermId}
      />
    );
  }
  if (config.kind === "branding") return <TenantBrandingPage embedded />;
  if (config.kind === "levels") return <AcademicLevelsWorkspace activeTab={activeTab} />;
  if (config.kind === "arm-labels") return <ArmLabelsWorkspace activeTab={activeTab} />;
  if (config.kind === "classes") return <ClassesWorkspace activeTab={activeTab} />;
  if (config.kind === "departments") return <DepartmentsWorkspace activeTab={activeTab} />;
  if (config.kind === "curriculum") return <CurriculumWorkspace />;
  if (config.kind === "assignments") {
    return <TeacherAssignmentsWorkspace activeTab={activeTab} />;
  }
  if (config.kind === "progression") return <ProgressionWorkspace />;
  if (config.kind === "calendar") {
    return (
      <AdminCalendarSetupWorkspace
        setupTermId={setupTermId}
        onSaved={onSaved}
      />
    );
  }

  return null;
}

export default AdminGuideTaskWorkspace;
