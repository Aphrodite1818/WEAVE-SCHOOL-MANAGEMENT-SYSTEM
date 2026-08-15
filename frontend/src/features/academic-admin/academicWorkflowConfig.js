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
  "levels",
  "progression",
  "classes",
  "subjects",
  "level-subjects",
  "assignments",
  "grading",
  "results",
  "report-cards",
  "school-calendar",
];

export const academicWorkflowConfig = {
  levels: {
    title: "Academic Levels",
    shortTitle: "Levels",
    description: "Create curriculum levels with explicit categories and ordered positions.",
    icon: Layers3,
    tone: "primary",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "create", label: "Create Level" },
      { id: "manage", label: "Manage Levels" },
    ],
  },
  progression: {
    title: "Automatic Progression",
    shortTitle: "Progression",
    description:
      "Review the level-only transitions derived from category and position.",
    icon: Layers3,
    tone: "success",
    defaultTab: "transitions",
    tabs: [{ id: "transitions", label: "Level Transitions" }],
  },
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
  "level-subjects": {
    title: "Subjects by Level",
    shortTitle: "Level Subjects",
    description:
      "Configure the curriculum once for an academic level instead of duplicating it for every arm.",
    icon: Layers3,
    tone: "accent",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "assign", label: "Assign Subjects" },
      { id: "offerings", label: "Term Offerings" },
      { id: "active", label: "Active" },
      { id: "inactive", label: "Inactive" },
      { id: "archived", label: "Archived" },
    ],
  },
  assignments: {
    title: "Teacher Assignments",
    shortTitle: "Assignments",
    description:
      "Assign teachers to the subjects they teach, change teachers when needed, and keep history clear.",
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
      "Create school years, open the current year, and close a completed year with clear readiness checks.",
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
      "Set score limits and grading rules before teachers and admins process results.",
    icon: Ruler,
    tone: "warning",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "assessment-schemes", label: "Assessment Scheme" },
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
      { id: "bulk-actions", label: "Bulk Actions" },
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
      { id: "bulk-actions", label: "Bulk Actions" },
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
      "Set school days, holidays, events, and closures for the selected term calendar.",
    icon: CalendarDays,
    tone: "success",
    defaultTab: "overview",
    tabs: [
      { id: "overview", label: "Overview" },
      { id: "setup", label: "Setup" },
      { id: "calendar", label: "Calendar" },
      { id: "events", label: "Events" },
      { id: "closures", label: "Closures" },
      { id: "history", label: "History" },
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
    label: "Levels",
    description: "Curriculum category and position",
    to: "/admin/academic/levels",
    icon: Layers3,
  },
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
    label: "Level Subjects",
    description: "Subjects taught at each level",
    to: "/admin/academic/level-subjects",
    icon: Layers3,
  },
  {
    label: "Assignments",
    description: "Who teaches each class subject",
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
