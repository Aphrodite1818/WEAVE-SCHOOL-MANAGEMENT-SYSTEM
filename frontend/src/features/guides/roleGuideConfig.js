import {
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  ClipboardCheck,
  FileText,
  School,
  Users,
} from "lucide-react";

export const ROLE_GUIDES = {
  admin: {
    key: "tenant_admin_academic_setup_v3",
    route: "/admin/getting-started",
    dashboardRoute: "/admin/dashboard",
    eyebrow: "School year setup",
    title: "Set up your school year",
    description:
      "Prepare the session, first term, and calendar in the lifecycle order Weave requires.",
    steps: [
      {
        id: "session",
        shortLabel: "Session",
        label: "Create your school year",
        description: "Give your academic session a name and set its start and end dates. It stays draft until your first term exists.",
        actionLabel: "Set up session",
        to: "/admin/academic/sessions",
        icon: CalendarDays,
      },
      {
        id: "term",
        shortLabel: "Term",
        label: "Add your first term and open the session",
        description: "Create the first term inside the session. Then Weave will help you open the session before calendar activation.",
        actionLabel: "Set up term",
        to: "/admin/academic/terms",
        icon: CalendarCheck2,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Prepare your term calendar",
        description: "Configure the school week, generate the first-term calendar, resolve any lifecycle blockers, and activate it while the term is still draft.",
        actionLabel: "Set up calendar",
        to: "/admin/academic/school-calendar",
        icon: CalendarDays,
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
      "A short, practical introduction to the areas currently available during normal school operations.",
    steps: [
      {
        id: "classes",
        shortLabel: "Classes",
        label: "Review your assigned classes",
        description:
          "Confirm your class and subject assignments before entering scores or reviewing academic work.",
        actionLabel: "Open my classes",
        to: "/teacher/classes",
        icon: School,
      },
      {
        id: "comments",
        shortLabel: "Comments",
        label: "Complete class-teacher comments",
        description:
          "If you are the explicit class teacher, review finalized academic performance, save drafts, and submit term comments when results are ready.",
        actionLabel: "Open student comments",
        to: "/teacher/student-comments",
        icon: FileText,
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
        runtimeFeature: "attendance",
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
      "Learn where to find linked children, published reports, and school dates in the workspace available to you.",
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
        runtimeFeature: "attendance",
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
      "A short introduction to the academic information and school dates currently available to you.",
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
        runtimeFeature: "attendance",
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
