import {
  BarChart3,
  BookOpen,
  CalendarDays,
  FileText,
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
  "school-calendar",
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
    description:
      "Audit readiness, pause writes, run background progression, and finalize closure from one controlled workflow.",
    icon: CalendarDays,
    tone: "primary",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "create", label: "Create Session" },
      { id: "draft", label: "Draft Sessions" },
      { id: "open", label: "Open Session" },
      { id: "closing", label: "Closing" },
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
      { id: "closing", label: "Closing Terms" },
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
      { id: "ready", label: "Student Readiness" },
      { id: "generate", label: "Generate" },
      { id: "draft", label: "Draft Cards" },
      { id: "published", label: "Published Cards" },
      { id: "outdated", label: "Outdated Cards" },
      { id: "archived", label: "Archived Versions" },
    ],
  },
  "school-calendar": {
    title: "School Calendar",
    shortTitle: "Calendar",
    description:
      "Configure term calendars, operating days, events, holidays, closures, and lifecycle readiness.",
    icon: CalendarDays,
    tone: "success",
    defaultTab: "manage",
    tabs: [
      { id: "manage", label: "Manage Calendar" },
      { id: "setup", label: "Setup" },
      { id: "events", label: "Events" },
      { id: "closures", label: "Closures" },
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
  {
    label: "Calendar",
    description: "Term days and school events",
    to: "/admin/academic/school-calendar",
    icon: CalendarDays,
  },
];
