import {
  BookOpen,
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
    eyebrow: "School setup assistant",
    title: "Prepare your school for academic work",
    description:
      "Complete the foundation in a sensible order. Weave checks your live school data and resumes from the first unfinished stage.",
    steps: [
      {
        id: "foundation",
        shortLabel: "Foundation",
        label: "Create the academic foundation",
        description:
          "Create an academic session and its terms, then make the active period clear for the rest of the school.",
        actionLabel: "Create academic session",
        to: "/admin/academic/sessions?view=create",
        icon: CalendarDays,
      },
      {
        id: "structure",
        shortLabel: "Structure",
        label: "Build classes and subjects",
        description:
          "Create the classes learners belong to, add subjects, and map each subject to the right classes.",
        actionLabel: "Set up classes",
        to: "/admin/academic/classes?view=create",
        icon: School,
      },
      {
        id: "staff",
        shortLabel: "Staff",
        label: "Invite and assign teachers",
        description:
          "Add teachers, then connect them to their class and subject responsibilities before result entry begins.",
        actionLabel: "Manage teachers",
        to: "/admin/teachers",
        icon: Users,
      },
      {
        id: "students",
        shortLabel: "Launch",
        label: "Add students and start school work",
        description:
          "Create or import students, review readiness, and continue into attendance, results, and report cards.",
        actionLabel: "Add students",
        to: "/admin/students/create",
        icon: GraduationCap,
      },
    ],
  },
  teacher: {
    key: "teacher_workspace_intro",
    eyebrow: "Teacher quick guide",
    title: "Get comfortable with your teaching workspace",
    description:
      "A short tour of the workflows you will use most often. You can leave and continue later.",
    steps: [
      {
        id: "classes",
        shortLabel: "Classes",
        label: "Review your assigned classes",
        description:
          "Confirm the classes and subjects assigned to you before entering attendance or scores.",
        actionLabel: "Open my classes",
        to: "/teacher/classes",
        icon: School,
      },
      {
        id: "results",
        shortLabel: "Results",
        label: "Enter and save student results",
        description:
          "Choose an assignment, search the roster by name or admission number, save drafts, and submit complete rows.",
        actionLabel: "Open score entry",
        to: "/teacher/score-entry",
        icon: ClipboardCheck,
      },
      {
        id: "attendance",
        shortLabel: "Attendance",
        label: "Mark attendance accurately",
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
    eyebrow: "Parent quick guide",
    title: "Follow your child’s school progress",
    description:
      "Learn where to find linked children, attendance, report cards, and school updates.",
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
          "Review daily attendance and the available attendance summary for each linked child.",
        actionLabel: "View attendance",
        to: "/parent/attendance",
        icon: ClipboardCheck,
      },
      {
        id: "reports",
        shortLabel: "Reports",
        label: "Open published report cards",
        description:
          "View and print report cards that the school has published for your child.",
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
    eyebrow: "Student quick guide",
    title: "Find your academic information quickly",
    description:
      "A short introduction to subjects, attendance, report cards, and school updates.",
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
          "Use the school calendar to see term events, closures, holidays, and important dates.",
        actionLabel: "View calendar",
        to: "/student/calendar",
        icon: CalendarDays,
      },
    ],
  },
};

export const guideForRole = (role) => ROLE_GUIDES[String(role || "").toLowerCase()] || null;
