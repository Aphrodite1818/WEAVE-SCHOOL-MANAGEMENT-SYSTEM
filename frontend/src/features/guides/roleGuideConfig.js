import {
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  ClipboardCheck,
  FileText,
  GraduationCap,
  Route,
  School,
  Users,
} from "lucide-react";

export const ROLE_GUIDES = {
  admin: {
    key: "tenant_admin_academic_setup",
    route: "/admin/getting-started",
    dashboardRoute: "/admin/dashboard",
    eyebrow: "Academic setup",
    title: "Set up your school workspace",
    description:
      "Follow the backend-safe setup order. Every stage is verified against your live school data before the next lifecycle transition.",
    steps: [
      {
        id: "session",
        shortLabel: "Session",
        label: "Create an academic session",
        description:
          "Define the dated academic year that the term and school calendar will belong to.",
        icon: CalendarDays,
      },
      {
        id: "term",
        shortLabel: "Term",
        label: "Create a term in the session",
        description:
          "Create the first draft term and keep its dates inside the academic session date range.",
        icon: CalendarCheck2,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Configure and generate the calendar",
        description:
          "Save the school calendar defaults and generate complete operational days for the draft term.",
        icon: CalendarDays,
      },
      {
        id: "structure",
        shortLabel: "Structure",
        label: "Create classes and subjects",
        description:
          "Create at least one active class and one active subject before launching normal academic work.",
        icon: School,
      },
      {
        id: "progression",
        shortLabel: "Progression",
        label: "Configure class progression",
        description:
          "Choose the next class for every non-terminal class and mark final classes as terminal.",
        icon: Route,
      },
      {
        id: "session_open",
        shortLabel: "Open session",
        label: "Open the academic session",
        description:
          "The backend requires a dated draft session, at least one term, and saved calendar configuration before the session can become current.",
        icon: GraduationCap,
      },
      {
        id: "calendar_active",
        shortLabel: "Activate calendar",
        label: "Activate the school calendar",
        description:
          "Calendar activation happens only after the session is open and while the selected term is still draft.",
        icon: CalendarCheck2,
      },
      {
        id: "term_open",
        shortLabel: "Open term",
        label: "Open the academic term",
        description:
          "Open the term last. The backend requires both the current open session and an active, complete calendar.",
        icon: GraduationCap,
      },
    ],
  },
  teacher: {
    key: "teacher_workspace_intro",
    route: "/teacher/getting-started",
    dashboardRoute: "/teacher/dashboard",
    eyebrow: "Teacher workspace",
    title: "Learn your teaching workspace",
    description:
      "A short, practical introduction to the areas you will use during normal school operations.",
    steps: [
      {
        id: "classes",
        shortLabel: "Classes",
        label: "Review your assigned classes",
        description:
          "Confirm your class and subject assignments before entering attendance or scores.",
        actionLabel: "Open my classes",
        to: "/teacher/classes",
        icon: School,
      },
      {
        id: "results",
        shortLabel: "Results",
        label: "Understand score entry",
        description:
          "Choose an assignment, search students by name or admission number, save drafts, and submit complete results.",
        actionLabel: "Open score entry",
        to: "/teacher/score-entry",
        icon: ClipboardCheck,
      },
      {
        id: "attendance",
        shortLabel: "Attendance",
        label: "Review the attendance workflow",
        description:
          "Choose the correct roster, review every learner, and submit the completed register.",
        actionLabel: "Open attendance",
        to: "/teacher/attendance",
        icon: Users,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Follow the school calendar",
        description:
          "Use the calendar to understand active school days, events, closures, and upcoming work.",
        actionLabel: "View calendar",
        to: "/teacher/calendar",
        icon: CalendarDays,
      },
    ],
  },
  parent: {
    key: "parent_workspace_intro",
    route: "/parent/getting-started",
    dashboardRoute: "/parent/dashboard",
    eyebrow: "Parent workspace",
    title: "Follow your child’s school progress",
    description:
      "Learn where to find linked children, attendance, report cards, and school dates.",
    steps: [
      {
        id: "children",
        shortLabel: "Children",
        label: "Review linked children",
        description:
          "Confirm the learners connected to your account and complete any pending linking request.",
        actionLabel: "Review linked children",
        to: "/parent/student-linking",
        icon: Users,
      },
      {
        id: "attendance",
        shortLabel: "Attendance",
        label: "Check attendance",
        description:
          "Review daily attendance and the attendance summary available for each linked child.",
        actionLabel: "View attendance",
        to: "/parent/attendance",
        icon: ClipboardCheck,
      },
      {
        id: "reports",
        shortLabel: "Reports",
        label: "Open published report cards",
        description:
          "View and print report cards after the school publishes them.",
        actionLabel: "View report cards",
        to: "/parent/report-cards",
        icon: FileText,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Keep up with school dates",
        description:
          "See term dates, events, holidays, and closures shared by the school.",
        actionLabel: "View calendar",
        to: "/parent/calendar",
        icon: CalendarDays,
      },
    ],
  },
  student: {
    key: "student_workspace_intro",
    route: "/student/getting-started",
    dashboardRoute: "/student/dashboard",
    eyebrow: "Student workspace",
    title: "Find your academic information quickly",
    description:
      "A short introduction to subjects, attendance, report cards, and school dates.",
    steps: [
      {
        id: "subjects",
        shortLabel: "Subjects",
        label: "Explore your subjects",
        description:
          "Open your subject list and review the academic information available for each subject.",
        actionLabel: "View subjects",
        to: "/student/subjects",
        icon: BookOpen,
      },
      {
        id: "attendance",
        shortLabel: "Attendance",
        label: "Track your attendance",
        description:
          "Review your attendance history and understand the summary shown by the school.",
        actionLabel: "View attendance",
        to: "/student/attendance",
        icon: ClipboardCheck,
      },
      {
        id: "reports",
        shortLabel: "Reports",
        label: "View published report cards",
        description:
          "Open report cards after the school publishes them and use the print view when needed.",
        actionLabel: "View report cards",
        to: "/student/report-cards",
        icon: FileText,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Know what is happening next",
        description:
          "Use the school calendar to see events, closures, holidays, and important dates.",
        actionLabel: "View calendar",
        to: "/student/calendar",
        icon: CalendarDays,
      },
    ],
  },
};

export const guideForRole = (role) =>
  ROLE_GUIDES[String(role || "").toLowerCase()] || null;
