import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import AcademicLevelsWorkspace from "../../features/academic-admin/AcademicLevelsWorkspace";
import AcademicPeriodsWorkspace from "../../features/academic-admin/AcademicPeriodsWorkspace";
import AcademicWorkflowShell from "../../features/academic-admin/AcademicWorkflowShell";
import ArmLabelsWorkspace from "../../features/academic-admin/ArmLabelsWorkspace";
import AssessmentConfigWorkspace from "../../features/academic-admin/AssessmentConfigWorkspace";
import BulkAcademicActionsWorkspace from "../../features/academic-admin/BulkAcademicActionsWorkspace";
import ClassesWorkspace from "../../features/academic-admin/ClassesWorkspace";
import CommentTemplatesWorkspace from "../../features/academic-admin/CommentTemplatesWorkspace";
import CurriculumWorkspace from "../../features/academic-admin/CurriculumWorkspace";
import DepartmentsWorkspace from "../../features/academic-admin/DepartmentsWorkspace";
import GradingScalesWorkspace from "../../features/academic-admin/GradingScalesWorkspace";
import ProgressionWorkspace from "../../features/academic-admin/ProgressionWorkspace";
import ReportCardsWorkspace from "../../features/academic-admin/ReportCardsWorkspace";
import ResultsWorkspace from "../../features/academic-admin/ResultsWorkspace";
import SessionLifecycleWorkspace from "../../features/academic-admin/SessionLifecycleWorkspace";
import SubjectsWorkspace from "../../features/academic-admin/SubjectsWorkspace";
import TeacherAssignmentsWorkspace from "../../features/academic-admin/TeacherAssignmentsWorkspace";
import { filterDepartmentWorkflow } from "../../features/academic-admin/academicDepartmentCapability";
import {
  academicWorkflowConfig,
  academicWorkflowOrder,
} from "../../features/academic-admin/academicWorkflowConfig";
import SchoolCalendarEventsWorkspace from "../../features/schoolCalendar/components/SchoolCalendarEventsWorkspace";
import SchoolCalendarWorkspace from "../../features/schoolCalendar/components/SchoolCalendarWorkspace";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";
import { academicLevelService } from "../../services/academicsService";

const workflowAliases = {
  reports: "report-cards",
  manage: "classes",
  setup: "sessions",
  "class-structure": "classes",
};
const asItems = (r) =>
  Array.isArray(r) ? r : Array.isArray(r?.items) ? r.items : [];

export default function AcademicWorkflowPage() {
  const { workflow: routeWorkflow = "sessions" } = useParams();
  const workflow = workflowAliases[routeWorkflow] || routeWorkflow;
  const { entitlements } = useSubscription();
  const bulkAcademicAllowed = Boolean(
    entitlements?.features?.bulk_academic_operations,
  );
  const [context, setContext] = useState({
    currentSession: null,
    currentTerm: null,
  });
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [capabilitiesReady, setCapabilitiesReady] = useState(false);
  const [loadingContext, setLoadingContext] = useState(true);

  const loadContext = useCallback(async () => {
    setLoadingContext(true);
    setCapabilitiesReady(false);
    try {
      const [sessionResult, termResult, categoryResult] = await Promise.allSettled([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        academicLevelService.getCategories(),
      ]);

      const sessions =
        sessionResult.status === "fulfilled" ? asItems(sessionResult.value) : [];
      const terms =
        termResult.status === "fulfilled" ? asItems(termResult.value) : [];
      const categories =
        categoryResult.status === "fulfilled" ? asItems(categoryResult.value) : [];

      setContext({
        currentSession: sessions.find((x) => x.is_current) || null,
        currentTerm: terms.find((x) => x.is_current) || null,
      });
      setCategoryOptions(categories);
    } finally {
      setCapabilitiesReady(true);
      setLoadingContext(false);
    }
  }, []);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  const availableWorkflows = useMemo(
    () => filterDepartmentWorkflow(academicWorkflowOrder, categoryOptions),
    [categoryOptions],
  );

  const updateContext = useCallback(
    ({ currentSession, currentTerm }) =>
      setContext((c) => ({
        currentSession:
          currentSession === undefined ? c.currentSession : currentSession,
        currentTerm: currentTerm === undefined ? c.currentTerm : currentTerm,
      })),
    [],
  );

  if (!academicWorkflowConfig[workflow]) {
    return <Navigate to="/admin/academic" replace />;
  }

  if (workflow === "departments" && !capabilitiesReady) {
    return null;
  }

  if (
    workflow === "departments" &&
    !availableWorkflows.includes("departments")
  ) {
    return <Navigate to="/admin/academic" replace />;
  }

  const renderWorkspace = (activeTab) => {
    const key = `${workflow}:${activeTab}`;
    if (workflow === "grading" && activeTab === "assessment-schemes") {
      return <AssessmentConfigWorkspace key={key} />;
    }
    if (workflow === "grading") {
      return <GradingScalesWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "comment-templates") {
      return <CommentTemplatesWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "sessions" && activeTab === "closing") {
      return (
        <SessionLifecycleWorkspace
          key="session-closing"
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (["sessions", "terms"].includes(workflow)) {
      return (
        <AcademicPeriodsWorkspace
          key={key}
          domain={workflow}
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "subjects") {
      return <SubjectsWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "levels") {
      return <AcademicLevelsWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "arm-labels") {
      return <ArmLabelsWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "classes") {
      return <ClassesWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "departments") {
      return <DepartmentsWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "curriculum") {
      return <CurriculumWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "assignments") {
      return <TeacherAssignmentsWorkspace key={key} activeTab={activeTab} />;
    }
    if (workflow === "progression") {
      return <ProgressionWorkspace key="automatic-progression" />;
    }
    if (
      ["results", "report-cards"].includes(workflow) &&
      activeTab === "bulk-actions"
    ) {
      return (
        <BulkAcademicActionsWorkspace
          key={`${workflow}-bulk`}
          domain={workflow}
          paidAccess={bulkAcademicAllowed}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "results") {
      return (
        <ResultsWorkspace
          key="results"
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "report-cards") {
      return (
        <ReportCardsWorkspace
          key="report-cards"
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "school-calendar") {
      return activeTab === "events" ? (
        <SchoolCalendarEventsWorkspace key="calendar-events" />
      ) : (
        <SchoolCalendarWorkspace
          key={`calendar-${activeTab}`}
          activeTab={activeTab}
        />
      );
    }
    return <Navigate to="/admin/academic" replace />;
  };

  return (
    <AcademicWorkflowShell
      workflow={workflow}
      currentSession={context.currentSession}
      currentTerm={context.currentTerm}
      loading={loadingContext}
      availableWorkflows={availableWorkflows}
    >
      {renderWorkspace}
    </AcademicWorkflowShell>
  );
}
