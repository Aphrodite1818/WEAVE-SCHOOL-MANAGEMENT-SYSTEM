import {
  BarChart3,
  BookOpen,
  FileSearch,
  FileText,
  Layers3,
  Pencil,
  Users,
} from "lucide-react";

export const academicWorkflowOrder = [
  "setup",
  "class-subjects",
  "assignments",
  "results",
  "report-cards",
  "search",
];

export const academicWorkflowConfig = {
  setup: {
    title: "Academic Setup",
    shortTitle: "Setup",
    description:
      "Configure academic sessions, terms, grading scales, and the subject catalog.",
    icon: BookOpen,
    tone: "primary",
    defaultTab: "periods",
    tabs: [
      { id: "periods", label: "Sessions & Terms" },
      { id: "grading", label: "Grading Scales" },
      { id: "subjects", label: "Subject Catalog" },
    ],
  },
  "class-subjects": {
    title: "Class Structure",
    shortTitle: "Classes",
    description:
      "Create classes, assign class teachers, and configure the subjects offered by each class.",
    icon: Layers3,
    tone: "success",
    defaultTab: "classes",
    tabs: [
      { id: "classes", label: "Classes" },
      { id: "offerings", label: "Class Subjects" },
      { id: "review", label: "Structure Review" },
    ],
  },
  assignments: {
    title: "Teacher Assignments",
    shortTitle: "Assignments",
    description:
      "Assign active teacher memberships to class-subject records and manage assignment status.",
    icon: Users,
    tone: "warning",
    defaultTab: "assign",
    tabs: [
      { id: "assign", label: "Assign Teacher" },
      { id: "review", label: "Review Assignments" },
    ],
  },
  results: {
    title: "Results Management",
    shortTitle: "Results",
    description:
      "Select an academic context, enter scores, and manage draft or submitted result rows.",
    icon: Pencil,
    tone: "accent",
    defaultTab: "entry",
    tabs: [
      { id: "entry", label: "Score Entry" },
      { id: "drafts", label: "Draft Results" },
      { id: "submitted", label: "Submitted Results" },
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
      { id: "overview", label: "Class Overview" },
      { id: "generate", label: "Generate" },
      { id: "publish", label: "Review & Publish" },
    ],
  },
  search: {
    title: "Academic Search",
    shortTitle: "Search",
    description:
      "Find students, academic records, report cards, and related school data.",
    icon: FileSearch,
    tone: "success",
    defaultTab: "search",
    tabs: [{ id: "search", label: "Search Records" }],
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
    label: "Academic setup",
    description: "Sessions, terms, grading, and subjects",
    to: "/admin/academic/setup",
    icon: BookOpen,
  },
  {
    label: "Class structure",
    description: "Classes and offered subjects",
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
