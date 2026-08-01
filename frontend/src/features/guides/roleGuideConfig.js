import {
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  ClipboardCheck,
  FileText,
  GraduationCap,
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
      "Build the minimum academic foundation in the correct order. Every stage is verified against your live school data.",
    steps: [
      {
        id: "session",
        shortLabel: "Session",
        label: "Create an academic session",
        description:
          "Define the academic year that terms, calendars, classes, and student records will belong to.",
        icon: CalendarDays,
      },
      {
        id: "term",
        shortLabel: "Term",
        label: "Create a term in the session",
        description:
          "Add the first term to the session and define its operating dates.",
        icon: CalendarCheck2,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Generate the school calendar",
        description:
          "Set the school timetable defaults and generate operational days for the selected term.",
        icon: CalendarDays,
      },
      {
        id: "structure",
        shortLabel: "Structure",
        label: "Create classes and subjects",
        description:
          "Create at least one class and one subject so the academic workspace has a usable structure.",
        icon: School,
      },
      {
        id: "activation",
        shortLabel: "Activate",
        label: "Activate the calendar, session, and term",
        description:
          "Complete the launch sequence so teachers and administrators can begin academic operations.",
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
