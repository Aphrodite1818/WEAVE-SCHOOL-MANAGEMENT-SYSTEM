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
  "classes",
  "subjects",
  "class-subjects",
  "assignments",
  "sessions",
  "terms",
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
    defaultTab: "current",
    tabs: [
      { id: "current", label: "Current Mappings" },
      { id: "create", label: "Create Mapping" },
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
    defaultTab: "active",
    tabs: [
      { id: "active", label: "Active Assignments" },
      { id: "history", label: "Assignment History" },
      { id: "assign", label: "Assign Teacher" },
      { id: "reassign", label: "Reassign Teacher" },
      { id: "end", label: "End Assignment" },
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
      { id: "overview", label: "Sessions" },
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
    title: "Grading Scales",
    shortTitle: "Grading",
    description:
      "Create and maintain active grading rules while the backend remains source of truth for range conflicts.",
    icon: Ruler,
    tone: "warning",
    defaultTab: "all",
    tabs: [
      { id: "all", label: "All Scales" },
      { id: "create", label: "Create Rule" },
      { id: "active", label: "Active Rules" },
      { id: "inactive", label: "Inactive Rules" },
    ],
  },
  results: {
    title: "Results Management",
    shortTitle: "Results",
    description:
      "Select an academic context, enter scores, and manage draft or submitted result rows.",
    icon: Pencil,
    tone: "accent",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "draft", label: "Draft" },
      { id: "submitted", label: "Submitted" },
      { id: "approved", label: "Approved" },
      { id: "locked", label: "Locked" },
      { id: "review", label: "Review Queue" },
      { id: "entry", label: "Score Entry" },
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
      { id: "draft", label: "Draft Cards" },
      { id: "published", label: "Published Cards" },
      { id: "outdated", label: "Outdated Cards" },
      { id: "archived", label: "Archived Versions" },
      { id: "generate", label: "Generate" },
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
