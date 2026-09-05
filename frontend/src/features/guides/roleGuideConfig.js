import {
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  ClipboardCheck,
  CheckCircle2,
  FileText,
  ImageIcon,
  Layers3,
  Route,
  School,
  Users,
} from "lucide-react";

export const ROLE_GUIDES = {
  admin: {
    key: "tenant_admin_academic_setup_v2",
    route: "/admin/getting-started",
    dashboardRoute: "/admin/dashboard",
    eyebrow: "Academic setup",
    title: "Set up your school workspace",
    description:
      "Configure one responsibility per page and return whenever you need to continue.",
    steps: [
      {
        id: "school_basics", shortLabel: "School basics", label: "Review school basics",
        description: "Check the school name and institution type before configuring academic work.", scope: "Check the school name and institution type before configuring academic work.", actionLabel: "Review school basics",
        to: "/admin/settings", icon: School,
      },
      {
        id: "session",
        shortLabel: "Session",
        label: "Create an academic session",
        description:
          "Define the dated school year that terms and results belong to.",
        scope: "Academic-session identity and dates.",
        actionLabel: "Configure sessions",
        to: "/admin/academic/sessions",
        icon: CalendarDays,
      },
      {
        id: "term",
        shortLabel: "Term",
        label: "Create an academic term",
        description: "Create the term inside its academic session.",
        scope: "Term identity and dates only.",
        actionLabel: "Configure terms",
        to: "/admin/academic/terms",
        icon: CalendarCheck2,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Configure the school calendar",
        description:
          "Define operating days, holidays and closures for the selected term.",
        scope: "Calendar configuration and day generation.",
        actionLabel: "Configure calendar",
        to: "/admin/academic/school-calendar",
        icon: CalendarDays,
      },
      {
        id: "levels",
        shortLabel: "Levels",
        label: "Create academic levels",
        description:
          "Define levels such as Nursery 1, Primary 4, JSS1 or SS2 using the categories allowed for this institution.",
        detail:
          "Levels own curriculum and determine progression order. Class arms do not define curriculum.",
        scope: "Level name, category and progression position.",
        actionLabel: "Configure levels",
        to: "/admin/academic/levels",
        icon: Layers3,
      },
      {
        id: "arms",
        shortLabel: "Arms",
        label: "Create arm labels",
        description:
          "Create reusable labels such as A, B and C before forming concrete classes.",
        scope: "Reusable class-arm labels only.",
        actionLabel: "Configure arm labels",
        to: "/admin/academic/arm-labels",
        icon: School,
      },
      {
        id: "classes",
        shortLabel: "Classes",
        label: "Create class arms",
        description:
          "Combine a level with an arm label, for example JSS1 A. Departments are not permanently attached to classes.",
        scope: "Class arm and optional class teacher only.",
        actionLabel: "Configure classes",
        to: "/admin/academic/classes",
        icon: School,
      },
      {
        id: "subjects",
        shortLabel: "Subjects",
        label: "Create the subject pool",
        description:
          "Create each subject once for the school before attaching it to curricula.",
        scope: "Tenant-wide subject catalogue only.",
        actionLabel: "Configure subjects",
        to: "/admin/academic/subjects",
        icon: BookOpen,
      },
      {
        id: "curriculum",
        shortLabel: "Curriculum",
        label: "Build level curricula",
        description:
          "Attach subjects to levels and mark only optional subjects as elective.",
        scope:
          "Curriculum subjects, elective status and department applicability.",
        actionLabel: "Configure curriculum",
        to: "/admin/academic/curriculum",
        icon: BookOpen,
      },
      {
        id: "departments",
        shortLabel: "Departments",
        label: "Configure level departments",
        description:
          "Add specializations only to levels whose category supports them, such as Senior Secondary.",
        scope: "School-wide departments, level availability and exact-term class specialization.",
        actionLabel: "Configure departments",
        to: "/admin/academic/departments",
        icon: Users,
      },
      {
        id: "teachers", shortLabel: "Teachers", label: "Add teachers",
        description: "Create active teacher memberships before assigning teaching work.", scope: "Create active teacher memberships before assigning teaching work.", actionLabel: "Add teachers",
        to: "/admin/teachers", icon: Users,
      },
      {
        id: "assignments",
        shortLabel: "Teachers",
        label: "Assign subject teachers",
        description:
          "Authorize teachers for a curriculum subject in a concrete class arm.",
        scope: "Teacher, class arm and curriculum-subject assignment.",
        actionLabel: "Configure teacher assignments",
        to: "/admin/academic/assignments",
        icon: Users,
      },
      {
        id: "students", shortLabel: "Students", label: "Add students and enrolments",
        description: "Place students in classes for the selected school session.", scope: "Place students in classes for the selected school session.", actionLabel: "Add students and enrolments",
        to: "/admin/students", icon: Users,
      },
      {
        id: "grading", shortLabel: "Assessment", label: "Configure grading and assessment",
        description: "Activate assessment components and a grading scale covering the full score range.", scope: "Activate assessment components and a grading scale covering the full score range.", actionLabel: "Configure grading and assessment",
        to: "/admin/academic/grading", icon: ClipboardCheck,
      },
      {
        id: "readiness", shortLabel: "Readiness", label: "Review academic readiness",
        description: "Resolve backend readiness blockers before opening the term.", scope: "Resolve backend readiness blockers before opening the term.", actionLabel: "Review academic readiness",
        to: "/admin/academic/terms", icon: CheckCircle2,
      },
      {
        id: "school_logo",
        optional: true,
        feature: "tenant_branding",
        shortLabel: "Branding",
        label: "Set school branding",
        description:
          "Add the school identity used across the workspace and printable records.",
        detail: "Branding is intentionally separate from academic structure.",
        scope: "School logo and visual identity only.",
        actionLabel: "Open branding",
        to: "/admin/settings/branding",
        icon: ImageIcon,
      },
      {
        id: "progression",
        optional: true,
        shortLabel: "Progression",
        label: "Review progression order",
        description:
          "Confirm the level sequence before opening normal academic work. Final-level graduation always requires explicit closure confirmation.",
        scope: "Level ordering and terminal-level review.",
        actionLabel: "Review progression",
        to: "/admin/academic/progression",
        icon: Route,
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
