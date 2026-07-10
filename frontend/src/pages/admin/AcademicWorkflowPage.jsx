import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  ClipboardList,
  FileSearch,
  FileText,
  GraduationCap,
  Library,
  Pencil,
  Settings2,
  Users,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { cn } from "../../utils/cn";

const workflowSections = {
  setup: {
    title: "Academic Setup",
    description: "Create the school academic structure without scrolling through every operation at once.",
    icon: BookOpen,
    workbenchLabel: "Open setup workbench",
    tabs: [
      { id: "sessions", label: "Sessions", icon: Library, description: "Create academic years like 2026/2027.", workbenchHint: "Use this when a new school year starts." },
      { id: "terms", label: "Terms", icon: ClipboardList, description: "Attach first, second, and third terms to a session.", workbenchHint: "Set the current term before results are entered." },
      { id: "grading", label: "Grading scale", icon: BarChart3, description: "Define grade bands and remarks for report cards.", workbenchHint: "Example: A = 70-100, Excellent." },
      { id: "subjects", label: "Subjects", icon: BookOpen, description: "Maintain the subject catalogue used across classes.", workbenchHint: "Subjects are reused in class setup and results." },
    ],
  },
  assignments: {
    title: "Teacher Assignments",
    description: "Keep subject ownership and class-teacher responsibilities easier to reason about.",
    icon: Users,
    workbenchLabel: "Open assignment workbench",
    tabs: [
      { id: "class-subjects", label: "Class subjects", icon: BookOpen, description: "Choose which subjects belong to each class.", workbenchHint: "This is the base before assigning a teacher." },
      { id: "teacher-links", label: "Teacher links", icon: Users, description: "Attach teachers to class-subject records.", workbenchHint: "One teacher can own a subject for a class." },
      { id: "active-history", label: "Active/history", icon: Settings2, description: "Deactivate old assignments without losing history.", workbenchHint: "Useful when teachers change mid-session." },
    ],
  },
  results: {
    title: "Results Workflow",
    description: "Separate result setup, entry, correction, and submission into clearer steps.",
    icon: Pencil,
    workbenchLabel: "Open results workbench",
    tabs: [
      { id: "filters", label: "Select class", icon: FileSearch, description: "Pick session, term, class, and subject first.", workbenchHint: "This reduces mistakes before scores are entered." },
      { id: "entry", label: "Score entry", icon: Pencil, description: "Record test, assessment, and exam scores.", workbenchHint: "Blank score components can stay empty until ready." },
      { id: "corrections", label: "Corrections", icon: Settings2, description: "Reopen drafts or correct saved result rows.", workbenchHint: "Use this before final submission." },
      { id: "submission", label: "Submit/reopen", icon: GraduationCap, description: "Submit completed results or reopen them when needed.", workbenchHint: "Submitted results become visible in reporting flows." },
    ],
  },
  reports: {
    title: "Report Cards",
    description: "Manage generation, review, and publishing without mixing it with score entry.",
    icon: FileText,
    workbenchLabel: "Open report workbench",
    tabs: [
      { id: "generate", label: "Generate", icon: FileText, description: "Generate report cards from submitted results.", workbenchHint: "Use class, session, and term filters first." },
      { id: "review", label: "Review", icon: FileSearch, description: "Check generated report cards before publishing.", workbenchHint: "Review helps catch missing or incomplete data." },
      { id: "publish", label: "Publish", icon: ArrowRight, description: "Release report cards to students and parents.", workbenchHint: "Only publish when the school is ready." },
    ],
  },
};

const sectionOrder = ["setup", "assignments", "results", "reports"];

function AcademicWorkflowPage() {
  const { workflow = "setup" } = useParams();
  const section = workflowSections[workflow] || workflowSections.setup;
  const SectionIcon = section.icon;
  const [activeStepId, setActiveStepId] = useState(section.tabs[0]?.id);
  const activeStep = section.tabs.find((tab) => tab.id === activeStepId) || section.tabs[0];
  const ActiveStepIcon = activeStep.icon;

  useEffect(() => {
    setActiveStepId(section.tabs[0]?.id);
  }, [workflow, section.tabs]);

  return (
    <DashboardLayout role="admin" title={section.title} description={section.description}>
      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <SectionIcon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h2 className="section-title">{section.title}</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">{section.description}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:grid-cols-4 xl:w-[34rem]">
            {sectionOrder.map((key) => {
              const item = workflowSections[key];
              const Icon = item.icon;
              const active = key === workflow;
              return (
                <Link
                  key={key}
                  to={`/admin/academic/${key}`}
                  className={cn(
                    "flex min-h-11 items-center justify-center gap-2 rounded-xl px-3 py-2 text-center text-xs font-semibold transition sm:text-sm",
                    active ? "bg-surface text-primary shadow-sm" : "text-text-muted hover:bg-surface/60 hover:text-text",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.title.replace("Academic ", "")}
                </Link>
              );
            })}
          </div>
        </div>
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="relative grid gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:grid-cols-2 xl:grid-cols-4">
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
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)]">
          <div className="rounded-2xl border border-border/70 bg-surface-muted/20 p-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <ActiveStepIcon className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-text">{activeStep.label}</h3>
            <p className="mt-2 text-sm leading-6 text-text-muted">{activeStep.description}</p>
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-text-muted">How to use this step</p>
            <p className="mt-3 text-sm leading-6 text-text-soft">{activeStep.workbenchHint}</p>
            <p className="mt-3 text-sm leading-6 text-text-muted">
              Open the full workbench when you are ready to create, update, or review records for this step.
            </p>
            <Link to="/admin/academic/manage" className="mt-5 inline-flex">
              <Button>
                <Pencil className="h-4 w-4" />
                {section.workbenchLabel}
              </Button>
            </Link>
          </div>
        </div>
      </Card>

      <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        {section.tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveStepId(tab.id)}
              className={cn(
                "rounded-2xl border bg-surface p-4 text-left transition hover:border-primary/30 hover:bg-primary-subtle/25",
                activeStep.id === tab.id ? "border-primary/50 ring-2 ring-primary/10" : "border-border/70",
              )}
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-text sm:text-base">{tab.label}</h3>
              <p className="mt-2 text-xs leading-5 text-text-muted sm:text-sm">{tab.description}</p>
            </button>
          );
        })}
      </section>
    </DashboardLayout>
  );
}

export default AcademicWorkflowPage;
