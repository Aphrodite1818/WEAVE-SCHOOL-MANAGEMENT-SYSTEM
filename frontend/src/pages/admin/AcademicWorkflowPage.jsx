import { useCallback, useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import AcademicSetupWorkspace from "../../features/academic-admin/AcademicSetupWorkspace";
import AcademicWorkflowShell from "../../features/academic-admin/AcademicWorkflowShell";
import AssessmentConfigWorkspace from "../../features/academic-admin/AssessmentConfigWorkspace";
import { academicWorkflowConfig } from "../../features/academic-admin/academicWorkflowConfig";
import ClassStructureWorkspace from "../../features/academic-admin/ClassStructureWorkspace";
import ProgressionWorkspace from "../../features/academic-admin/ProgressionWorkspace";
import ReportCardsWorkspace from "../../features/academic-admin/ReportCardsWorkspace";
import ResultsWorkspace from "../../features/academic-admin/ResultsWorkspace";
import TeacherAssignmentsWorkspace from "../../features/academic-admin/TeacherAssignmentsWorkspace";
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
      currentTerm: currentTerm === undefined ? current.currentTerm : currentTerm,
    }));
  }, []);

  if (!academicWorkflowConfig[workflow]) {
    return <Navigate to="/admin/academic" replace />;
  }

  const renderWorkspace = (activeTab) => {
    if (workflow === "grading" && activeTab === "assessment-limits") {
      return <AssessmentConfigWorkspace />;
    }
    if (["sessions", "terms", "grading", "subjects"].includes(workflow)) {
      return (
        <AcademicSetupWorkspace
          domain={workflow}
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (["classes", "class-subjects"].includes(workflow)) {
      return <ClassStructureWorkspace domain={workflow} activeTab={activeTab} />;
    }
    if (workflow === "assignments") {
      return <TeacherAssignmentsWorkspace activeTab={activeTab} />;
    }
    if (workflow === "results") {
      return (
        <ResultsWorkspace
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "report-cards") {
      return (
        <ReportCardsWorkspace
          activeTab={activeTab}
          onContextChange={updateContext}
        />
      );
    }
    if (workflow === "progression") {
      return <ProgressionWorkspace activeTab={activeTab} />;
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
