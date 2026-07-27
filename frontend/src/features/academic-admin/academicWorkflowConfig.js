import {
  BarChart3,
  BookOpen,
  CalendarDays,
  FileText,
  GitBranch,
  Layers3,
  Pencil,
  Ruler,
  School,
  Users,
} from "lucide-react";

export const academicWorkflowOrder = [
  "sessions",
  "terms",
  "classes",
  "subjects",
  "class-subjects",
  "assignments",
  "grading",
  "results",
  "report-cards",
  "progression",
];

export const academicWorkflowConfig = {
  classes: {
    title: "Classes",
    shortTitle: "Classes",
    description:
      "Create class arms, assign class teachers, and manage active, inactive, and archived class records.",
    icon: School,
    tone: "primary",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "create", label: "Create Class" },
      { id: "active", label: "Active Classes" },
      { id: "inactive", label: "Inactive Classes" },
      { id: "archived", label: "Archived Classes" },
      { id: "progression", label: "Progression" },
    ],
  },
  subjects: {
    title: "Subjects",
    shortTitle: "Subjects",
    description:
      "Manage the tenant subject catalog and keep archived subjects out of normal workflows.",
    icon: BookOpen,
    tone: "success",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "create", label: "Create Subject" },
      { id: "active", label: "Active Subjects" },
      { id: "inactive", label: "Inactive Subjects" },
      { id: "archived", label: "Archived Subjects" },
    ],
  },
  "class-subjects": {
    title: "Class-Subject Mappings",
    shortTitle: "Mappings",
    description:
      "Attach subjects to classes and manage mapping lifecycle with dependency-aware actions.",
    icon: Layers3,
    tone: "accent",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "create", label: "Create Mapping" },
      { id: "current", label: "Current Mappings" },
      { id: "inactive", label: "Inactive Mappings" },
      { id: "archived", label: "Archived Mappings" },
      { id: "review", label: "Mapping Details" },
    ],
  },
  assignments: {
    title: "Teacher Assignments",
    shortTitle: "Assignments",
    description:
      "Treat teacher assignments as historical timeline records: assign, reassign, or end them without archiving.",
    icon: Users,
    tone: "warning",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "assign", label: "Assign Teacher" },
      { id: "reassign", label: "Reassign Teacher" },
      { id: "end", label: "End Assignment" },
      { id: "history", label: "Assignment History" },
    ],
  },
  sessions: {
    title: "Academic Sessions",
    shortTitle: "Sessions",
    description: "Create, edit, open, and close academic sessions with progression.",
    icon: CalendarDays,
    tone: "primary",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "create", label: "Create Session" },
      { id: "draft", label: "Draft Sessions" },
      { id: "open", label: "Open Session" },
      { id: "closed", label: "Closed Sessions" },
    ],
  },
  terms: {
    title: "Academic Terms",
    shortTitle: "Terms",
    description: "Create, edit, open, and close academic terms.",
    icon: CalendarDays,
    tone: "success",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "create", label: "Create Term" },
      { id: "draft", label: "Draft Terms" },
      { id: "open", label: "Open Term" },
      { id: "closed", label: "Closed Terms" },
    ],
  },
  grading: {
    title: "Grading Configuration",
    shortTitle: "Grading",
    description:
      "Configure assessment score limits and maintain grading rules used when results are calculated.",
    icon: Ruler,
    tone: "warning",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "assessment-limits", label: "Assessment Limits" },
      { id: "create", label: "Create Rule" },
      { id: "active", label: "Active Rules" },
      { id: "inactive", label: "Inactive Rules" },
    ],
  },
  results: {
    title: "Results Management",
    shortTitle: "Results",
    description:
      "Enter scores and move result records through draft, submission, approval, and final locking.",
    icon: Pencil,
    tone: "accent",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "entry", label: "Score Entry" },
      { id: "draft", label: "Draft" },
      { id: "submitted", label: "Submitted" },
      { id: "approved", label: "Approved" },
      { id: "locked", label: "Locked" },
    ],
  },
  "report-cards": {
    title: "Report Cards",
    shortTitle: "Reports",
    description:
      "Review class readiness, generate student report cards, and publish completed records.",
    icon: FileText,
    tone: "primary",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "ready", label: "Ready to Generate" },
      { id: "generate", label: "Generate" },
      { id: "draft", label: "Draft Cards" },
      { id: "published", label: "Published Cards" },
      { id: "outdated", label: "Outdated Cards" },
      { id: "archived", label: "Archived Versions" },
    ],
  },
  progression: {
    title: "Student Progression",
    shortTitle: "Progression",
    description:
      "Plan and review session progression using PROMOTE, REPEAT, GRADUATE, and SKIP outcomes.",
    icon: GitBranch,
    tone: "accent",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "plan", label: "Plan Progression" },
      { id: "completed", label: "Completed Runs" },
      { id: "failed", label: "Failed Runs" },
      { id: "outcomes", label: "Student Outcomes" },
    ],
  },
};

export const academicToneStyles = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-amber-900",
  accent: "bg-accent-soft text-accent",
  neutral: "bg-surface-muted text-text-muted",
};

export const academicWorkflowSummaryCards = [
  {
    label: "Classes",
    description: "Class arms and lifecycle",
    to: "/admin/academic/classes",
    icon: School,
  },
  {
    label: "Subjects",
    description: "Subject catalog lifecycle",
    to: "/admin/academic/subjects",
    icon: BookOpen,
  },
  {
    label: "Mappings",
    description: "Class-subject offerings",
    to: "/admin/academic/class-subjects",
    icon: Layers3,
  },
  {
    label: "Assignments",
    description: "Teacher and class-subject mapping",
    to: "/admin/academic/assignments",
    icon: Users,
  },
  {
    label: "Results",
    description: "Scores and submission status",
    to: "/admin/academic/results",
    icon: BarChart3,
  },
];
