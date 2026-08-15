import { useCallback, useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import AcademicSetupWorkspace from "../../features/academic-admin/AcademicSetupWorkspace";
import AcademicWorkflowShell from "../../features/academic-admin/AcademicWorkflowShell";
import AssessmentConfigWorkspace from "../../features/academic-admin/AssessmentConfigWorkspace";
import BulkAcademicActionsWorkspace from "../../features/academic-admin/BulkAcademicActionsWorkspace";
import ClassStructureWorkspace from "../../features/academic-admin/ClassStructureWorkspace";
import GradingScalesWorkspace from "../../features/academic-admin/GradingScalesWorkspace";
import ProgressionWorkspace from "../../features/academic-admin/ProgressionWorkspace";
import ReportCardsWorkspace from "../../features/academic-admin/ReportCardsWorkspace";
import ResultsWorkspace from "../../features/academic-admin/ResultsWorkspace";
import SessionLifecycleWorkspace from "../../features/academic-admin/SessionLifecycleWorkspace";
import TeacherAssignmentsWorkspace from "../../features/academic-admin/TeacherAssignmentsWorkspace";
import { academicWorkflowConfig } from "../../features/academic-admin/academicWorkflowConfig";
import SchoolCalendarEventsWorkspace from "../../features/schoolCalendar/components/SchoolCalendarEventsWorkspace";
import SchoolCalendarGuide from "../../features/schoolCalendar/components/SchoolCalendarGuide";
import SchoolCalendarWorkspace from "../../features/schoolCalendar/components/SchoolCalendarWorkspace";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { academicService } from "../../services/academicService";

const workflowAliases = {
  reports: "report-cards",
  manage: "classes",
  setup: "sessions",
  "class-structure": "classes",
};

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

function AcademicWorkflowPage() {
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
  const [loadingContext, setLoadingContext] = useState(true);

  const loadContext = useCallback(async () => {
    setLoadingContext(true);
    try {
      const [sessionResponse, termResponse] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
      ]);
      const sessions = asItems(sessionResponse);
      const terms = asItems(termResponse);
      setContext({
        currentSession: sessions.find((item) => item.is_current) || null,
        currentTerm: terms.find((item) => item.is_current) || null,
      });
    } catch {
      setContext({ currentSession: null, currentTerm: null });
    } finally {
      setLoadingContext(false);
    }
  }, []);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  const updateContext = useCallback(({ currentSession, currentTerm }) => {
    setContext((current) => ({
      currentSession:
        currentSession === undefined ? current.currentSession : currentSession,
      currentTerm:
        currentTerm === undefined ? current.currentTerm : currentTerm,
    }));
  }, []);

  if (!academicWorkflowConfig[workflow]) {
    return <Navigate to="/admin/academic" replace />;
  }

  const renderWorkspace = (activeTab) => {
    const pageKey = `${workflow}:${activeTab}`;

    if (workflow === "grading" && activeTab === "assessment-schemes") {
      return <AssessmentConfigWorkspace key={pageKey} />;
    }
    if (workflow === "grading") {
      return <GradingScalesWorkspace key={pageKey} activeTab={activeTab} />;
    }
    if (
      workflow === "sessions" &&
      ["overview", "open", "closing"].includes(activeTab)
    ) {
      return (
        <SessionLifecycleWorkspace
          key="session-lifecycle-workflow"
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (["sessions", "terms", "subjects"].includes(workflow)) {
      return (
        <AcademicSetupWorkspace
          key={pageKey}
          domain={workflow}
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (["levels", "classes", "level-subjects"].includes(workflow)) {
      return (
        <ClassStructureWorkspace
          key={pageKey}
          domain={workflow}
          activeTab={activeTab}
        />
      );
    }
    if (workflow === "assignments") {
      return (
        <TeacherAssignmentsWorkspace key={pageKey} activeTab={activeTab} />
      );
    }
    if (workflow === "progression") {
      return <ProgressionWorkspace key="automatic-progression-workflow" />;
    }
    if (
      ["results", "report-cards"].includes(workflow) &&
      activeTab === "bulk-actions"
    ) {
      return (
        <BulkAcademicActionsWorkspace
          key={`${workflow}-bulk-actions`}
          domain={workflow}
          paidAccess={bulkAcademicAllowed}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "results") {
      return (
        <ResultsWorkspace
          key="results-workflow"
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "report-cards") {
      return (
        <ReportCardsWorkspace
          key="report-cards-workflow"
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "school-calendar") {
      return (
        <div key="school-calendar-workflow" className="space-y-4">
          <SchoolCalendarGuide activeTab={activeTab} />
          {activeTab === "events" ? (
            <SchoolCalendarEventsWorkspace />
          ) : (
            <SchoolCalendarWorkspace activeTab={activeTab} />
          )}
        </div>
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
    >
      {renderWorkspace}
    </AcademicWorkflowShell>
  );
}

export default AcademicWorkflowPage;
