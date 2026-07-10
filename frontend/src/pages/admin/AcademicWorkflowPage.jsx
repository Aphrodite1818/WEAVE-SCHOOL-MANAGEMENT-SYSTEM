import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  ClipboardList,
  FileSearch,
  FileText,
  GraduationCap,
  Layers3,
  Library,
  Pencil,
  Search,
  Settings2,
  Users,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { cn } from "../../utils/cn";

const workflowSections = {
  setup: {
    title: "Academic setup",
    description: "Create the school academic structure without scrolling through every operation at once.",
    icon: BookOpen,
    tone: "primary",
    workbenchLabel: "Open setup workbench",
    workbenchPath: "/admin/academic/manage?tab=setup",
    tabs: [
      { id: "sessions", label: "Sessions", icon: Library, description: "Create and activate academic years like 2026/2027.", workbenchHint: "Start here when a new school year begins. Keep only one current session active." },
      { id: "terms", label: "Terms", icon: ClipboardList, description: "Attach first, second, and third terms to the active session.", workbenchHint: "Set the current term before results and report cards are processed." },
      { id: "grading", label: "Grading scale", icon: BarChart3, description: "Define score bands, grades, and remarks for report cards.", workbenchHint: "Use this before publishing results so report cards show correct grades and remarks." },
      { id: "subjects", label: "Subjects", icon: BookOpen, description: "Maintain the subject catalogue used across classes.", workbenchHint: "Subjects are reusable; create them once, then attach them to classes later." },
    ],
  },
  "class-subjects": {
    title: "Classes & subjects",
    description: "Keep classes, subjects, and class-subject relationships easier to understand.",
    icon: Layers3,
    tone: "success",
    workbenchLabel: "Open class-subject workbench",
    workbenchPath: "/admin/academic/manage?tab=assignments",
    tabs: [
      { id: "classes", label: "Classes", icon: Library, description: "Review class structure and arms before attaching subjects.", workbenchHint: "Class creation still lives on the Classes page, but academic linking starts here." },
      { id: "subjects", label: "Subjects", icon: BookOpen, description: "Review the tenant subject catalogue available for assignment.", workbenchHint: "Create missing subjects before attaching them to classes." },
      { id: "class-subjects", label: "Class subjects", icon: Layers3, description: "Attach subjects to a selected class as class-subject records.", workbenchHint: "This creates the base record that teacher assignments and results depend on." },
      { id: "review", label: "Review setup", icon: FileSearch, description: "Check what each class already has before assigning teachers.", workbenchHint: "Use review before assigning teachers so duplicate subject-class records are avoided." },
    ],
  },
  assignments: {
    title: "Teacher assignments",
    description: "Assign teachers to class subjects and review active or inactive assignments.",
    icon: Users,
    tone: "warning",
    workbenchLabel: "Open assignment workbench",
    workbenchPath: "/admin/academic/manage?tab=assignments",
    tabs: [
      { id: "select-class", label: "Select class", icon: Library, description: "Choose the class whose subjects need teachers.", workbenchHint: "Filtering by class keeps the assignment workflow short and prevents confusion." },
      { id: "assign-subject", label: "Assign subject", icon: Users, description: "Attach a teacher to a class-subject record.", workbenchHint: "Use this when a teacher becomes responsible for a subject in a class." },
      { id: "view-assigned", label: "View assigned", icon: ClipboardList, description: "Review active subject-teacher assignments.", workbenchHint: "Admins can confirm who teaches what without entering score pages." },
      { id: "change-teacher", label: "Change teacher", icon: Settings2, description: "Deactivate or replace older assignments safely.", workbenchHint: "This keeps history while allowing teacher changes during the session." },
    ],
  },
  results: {
    title: "Results",
    description: "Separate result filtering, score entry, correction, and submission into clearer steps.",
    icon: Pencil,
    tone: "accent",
    workbenchLabel: "Open results workbench",
    workbenchPath: "/admin/academic/manage?tab=results",
    tabs: [
      { id: "filters", label: "Select records", icon: FileSearch, description: "Pick session, term, class, and subject first.", workbenchHint: "This reduces score-entry mistakes before the form opens." },
      { id: "entry", label: "Score entry", icon: Pencil, description: "Record test, assessment, and exam scores.", workbenchHint: "Blank score components can stay draft until all marks are ready." },
      { id: "drafts", label: "Drafts", icon: ClipboardList, description: "Review incomplete or editable result rows.", workbenchHint: "Draft rows are not final; submit them only after all components are complete." },
      { id: "submitted", label: "Submitted", icon: GraduationCap, description: "Review final rows or reopen when correction is needed.", workbenchHint: "Submitted results power analytics and report-card generation." },
    ],
  },
  "report-cards": {
    title: "Report cards",
    description: "Manage generation, review, publishing, and lookup without mixing it with score entry.",
    icon: FileText,
    tone: "primary",
    workbenchLabel: "Open report-card workbench",
    workbenchPath: "/admin/academic/manage?tab=reportCards",
    tabs: [
      { id: "overview", label: "Overview", icon: BarChart3, description: "Check generation and publishing status for a class.", workbenchHint: "Use overview before generating so missing results are easier to spot." },
      { id: "generate", label: "Generate", icon: FileText, description: "Generate report cards from submitted results.", workbenchHint: "Use class, session, and term filters before generation." },
      { id: "review", label: "Review", icon: FileSearch, description: "Check generated report cards before publishing.", workbenchHint: "Review helps catch missing, incomplete, or outdated reports." },
      { id: "publish", label: "Publish", icon: ArrowRight, description: "Release report cards to students and parents.", workbenchHint: "Only publish when school leadership is ready for visibility." },
    ],
  },
  search: {
    title: "Academic search",
    description: "Find academic records without browsing through every class or report table.",
    icon: Search,
    tone: "success",
    workbenchLabel: "Open search workbench",
    workbenchPath: "/admin/academic/manage?tab=search",
    tabs: [
      { id: "student-search", label: "Students", icon: GraduationCap, description: "Search students by name or admission number.", workbenchHint: "Use this when an admin needs to quickly locate a learner." },
      { id: "report-search", label: "Report cards", icon: FileText, description: "Find generated or published report cards.", workbenchHint: "Useful after report cards have been generated for many classes." },
      { id: "result-search", label: "Results", icon: BarChart3, description: "Look up academic result records by context.", workbenchHint: "Use filters to narrow down by session, term, class, or subject." },
      { id: "global-search", label: "Global search", icon: FileSearch, description: "Use the tenant search endpoint for quick cross-record lookup.", workbenchHint: "This is best when you know part of the name, admission number, or record label." },
    ],
  },
};

const workflowAliases = {
  reports: "report-cards",
};

const sectionOrder = ["setup", "class-subjects", "assignments", "results", "report-cards", "search"];

const toneStyles = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-amber-950",
  accent: "bg-accent-soft text-accent",
  neutral: "bg-surface-muted text-text-muted",
};

function getResolvedWorkflow(workflow) {
  return workflowAliases[workflow] || workflow || "setup";
}

function AcademicWorkflowPage() {
  const { workflow = "setup" } = useParams();
  const resolvedWorkflow = getResolvedWorkflow(workflow);
  const section = workflowSections[resolvedWorkflow] || workflowSections.setup;
  const SectionIcon = section.icon;
  const [activeStepId, setActiveStepId] = useState(section.tabs[0]?.id);
  const activeStep = section.tabs.find((tab) => tab.id === activeStepId) || section.tabs[0];
  const ActiveStepIcon = activeStep.icon;

  useEffect(() => {
    setActiveStepId(section.tabs[0]?.id);
  }, [resolvedWorkflow, section.tabs]);

  return (
    <DashboardLayout role="admin" title={section.title} description={section.description}>
      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <div className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl", toneStyles[section.tone] || toneStyles.primary)}>
              <SectionIcon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <Link to="/admin/academic" className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to academic hub
              </Link>
              <h2 className="mt-2 text-xl font-semibold text-text sm:text-2xl">{section.title}</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">{section.description}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:grid-cols-3 xl:w-[44rem]">
            {sectionOrder.map((key) => {
              const item = workflowSections[key];
              const Icon = item.icon;
              const active = key === resolvedWorkflow;
              return (
                <Link
                  key={key}
                  to={`/admin/academic/${key}`}
                  className={cn(
                    "flex min-h-11 items-center justify-center gap-2 rounded-xl px-2 py-2 text-center text-[11px] font-semibold transition sm:px-3 sm:text-xs",
                    active ? "bg-surface text-primary shadow-sm" : "text-text-muted hover:bg-surface/60 hover:text-text",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="line-clamp-1">{item.title}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:grid-cols-4">
          {section.tabs.map((tab) => {
            const Icon = tab.icon;
            const active = tab.id === activeStep.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveStepId(tab.id)}
                className={cn(
                  "flex min-h-12 items-center justify-center gap-2 rounded-xl px-3 py-2 text-center text-xs font-semibold transition sm:text-sm",
                  active ? "bg-surface text-primary shadow-sm" : "text-text-muted hover:bg-surface/60 hover:text-text",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="line-clamp-1">{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)]">
          <div className="rounded-2xl border border-border/70 bg-surface-muted/20 p-4">
            <div className={cn("flex h-12 w-12 items-center justify-center rounded-2xl", toneStyles[section.tone] || toneStyles.primary)}>
              <ActiveStepIcon className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-text">{activeStep.label}</h3>
            <p className="mt-2 text-sm leading-6 text-text-muted">{activeStep.description}</p>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-text-muted">Recommended flow</p>
            <p className="mt-3 text-sm leading-6 text-text-soft">{activeStep.workbenchHint}</p>
            <p className="mt-3 text-sm leading-6 text-text-muted">
              This page keeps the workflow simple. Use the workbench button only when you are ready to create, update, review, or publish records.
            </p>
            <div className="mt-5 flex flex-col gap-3 sm:flex-row">
              <Link to={section.workbenchPath} className="block">
                <Button className="w-full sm:w-auto">
                  <Pencil className="h-4 w-4" />
                  {section.workbenchLabel}
                </Button>
              </Link>
              <Link to="/admin/academic" className="block">
                <Button variant="outline" className="w-full sm:w-auto">
                  <ArrowLeft className="h-4 w-4" />
                  Main hub
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </Card>

      <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        {section.tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeStep.id === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveStepId(tab.id)}
              className={cn(
                "min-h-[10rem] rounded-2xl border bg-surface p-4 text-left shadow-sm transition hover:border-primary/30 hover:bg-primary-subtle/25 hover:shadow-premium",
                active ? "border-primary/50 ring-2 ring-primary/10" : "border-border/70",
              )}
            >
              <div className={cn("flex h-11 w-11 items-center justify-center rounded-2xl", toneStyles[section.tone] || toneStyles.primary)}>
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-sm font-semibold leading-5 text-text sm:text-base">{tab.label}</h3>
              <p className="mt-2 line-clamp-3 text-xs leading-5 text-text-muted sm:text-sm sm:leading-6">{tab.description}</p>
            </button>
          );
        })}
      </section>
    </DashboardLayout>
  );
}

export default AcademicWorkflowPage;
