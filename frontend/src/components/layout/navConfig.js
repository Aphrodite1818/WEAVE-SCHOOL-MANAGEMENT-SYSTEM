import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  CalendarDays,
  CheckSquare,
  ClipboardList,
  CreditCard,
  FileText,
  GraduationCap,
  Home,
  Library,
  Link2,
  MessageSquare,
  Receipt,
  Settings,
  Shield,
  UploadCloud,
  UserPlus,
  Users,
} from "lucide-react";

import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";

export const roleLabels = {
  admin: "Administrator",
  teacher: "Teacher",
  student: "Student",
  parent: "Parent",
  superadmin: "Platform admin",
};

export const workspaceSearchRoles = new Set(["admin", "teacher", "superadmin"]);
export const tenantNameFallbackRoles = new Set(["admin", "teacher"]);

export const announcementPaths = {
  admin: "/admin/announcements",
  teacher: "/teacher/notices",
  student: "/student/notices",
  parent: "/parent/notices",
  superadmin: "/superadmin/announcements",
};

export const onboardingModalCopy = {
  admin: {
    onboardingTitle: "Complete School Profile",
    editTitle: "Edit School Profile",
    onboardingDescription:
      "Finish the school profile fields required for onboarding. School-managed settings stay here, not in a personal profile form.",
    editDescription: "Update your school profile details.",
  },
  teacher: {
    onboardingTitle: "Complete Teacher Profile",
    editTitle: "Edit Teacher Profile",
    onboardingDescription:
      "Complete the teacher profile fields required by the backend before continuing.",
    editDescription: "Update your teacher profile details.",
  },
  parent: {
    onboardingTitle: "Complete Parent Profile",
    editTitle: "Edit Parent Profile",
    onboardingDescription:
      "Complete the parent profile fields required by the backend before continuing.",
    editDescription: "Update your parent profile details.",
  },
  student: {
    onboardingTitle: "Complete Student Profile",
    editTitle: "Edit Student Profile",
    onboardingDescription:
      "Complete the student profile fields required by the backend before continuing.",
    editDescription: "Update your student profile details.",
  },
};

export const navGroups = {
  admin: [
    {
      label: "Overview",
      items: [
        { label: "Dashboard", to: "/admin/dashboard", icon: Home },
        { label: "Analytics", to: "/admin/analytics", icon: BarChart3 },
        { label: "Create User", to: "/admin/create-user", icon: UserPlus },
        { label: "Calendar", to: "/admin/timetable", icon: CalendarDays },
      ],
    },
    {
      label: "Academics",
      items: [
        { label: "Academic Hub", to: "/admin/academic", icon: ClipboardList },
        { label: "Students", to: "/admin/students", icon: GraduationCap },
        { label: "Teachers", to: "/admin/teachers", icon: Users },
        { label: "Parents", to: "/admin/parents", icon: Users },
        { label: "Bulk Imports", to: "/admin/imports", icon: UploadCloud, featureCode: FEATURE_CODES.BULK_IMPORT },
        { label: "Classes", to: "/admin/classes", icon: Library },
        { label: "Subjects", to: "/admin/subjects", icon: BookOpen },
        { label: "Timetable", to: "/admin/timetable", icon: CalendarDays },
        { label: "Attendance", to: "/admin/attendance", icon: CheckSquare },
      ],
    },
    {
      label: "Communication",
      items: [
        { label: "Notices", to: "/admin/announcements", icon: FileText },
        { label: "Messages", to: "/admin/messages", icon: MessageSquare },
      ],
    },
    {
      label: "Operations",
      items: [
        { label: "Reports", to: "/admin/reports", icon: BarChart3 },
        { label: "Fees", to: "/admin/fees", icon: Receipt },
        { label: "Payments", to: "/admin/payments", icon: CreditCard },
        { label: "Billing", to: "/admin/billing", icon: CreditCard },
        { label: "Usage", to: "/admin/usage", icon: Activity },
        { label: "Settings", to: "/admin/settings", icon: Settings },
      ],
    },
  ],
  teacher: [
    {
      label: "Subject teaching",
      items: [
        { label: "Dashboard", to: "/teacher/dashboard", icon: Home },
        { label: "Analytics", to: "/teacher/analytics", icon: BarChart3 },
        { label: "Teaching Rosters", to: "/teacher/students", icon: GraduationCap },
        { label: "Assigned Subjects", to: "/teacher/subjects", icon: BookOpen },
        { label: "Score Entry", to: "/teacher/score-entry", icon: BarChart3 },
        { label: "Timetable", to: "/teacher/timetable", icon: CalendarDays },
        { label: "Assignments", to: "/teacher/assignments", icon: ClipboardList },
        { label: "Notices", to: "/teacher/notices", icon: Bell },
      ],
    },
    {
      label: "Class teacher duties",
      items: [
        { label: "My Class", to: "/teacher/classes", icon: Library },
        { label: "Class Attendance", to: "/teacher/attendance", icon: CheckSquare },
        { label: "Class Notices", to: "/teacher/announcements", icon: FileText },
        { label: "Settings", to: "/teacher/settings", icon: Settings },
      ],
    },
  ],
  student: [
    {
      label: "Learning",
      items: [
        { label: "Dashboard", to: "/student/dashboard", icon: Home },
        { label: "Performance", to: "/student/analytics", icon: BarChart3 },
        { label: "Subjects", to: "/student/subjects", icon: BookOpen },
        { label: "Parent Linking", to: "/student/parent-linking", icon: Link2 },
        { label: "Report Cards", to: "/student/report-cards", icon: FileText },
        { label: "Timetable", to: "/student/timetable", icon: CalendarDays },
        { label: "Assignments", to: "/student/assignments", icon: ClipboardList },
        { label: "Results", to: "/student/results", icon: BarChart3 },
        { label: "Notices", to: "/student/notices", icon: FileText },
        { label: "Settings", to: "/student/settings", icon: Settings },
      ],
    },
  ],
  parent: [
    {
      label: "Family",
      items: [
        { label: "Dashboard", to: "/parent/dashboard", icon: Home },
        { label: "Student Linking", to: "/parent/student-linking", icon: Link2 },
        { label: "Report Cards", to: "/parent/report-cards", icon: FileText },
        { label: "Results", to: "/parent/results", icon: BarChart3 },
        { label: "Attendance", to: "/parent/attendance", icon: CheckSquare },
        { label: "Notices", to: "/parent/notices", icon: FileText },
        { label: "Fees", to: "/parent/fees", icon: CreditCard },
        { label: "Settings", to: "/parent/settings", icon: Settings },
      ],
    },
  ],
  superadmin: [
    {
      label: "Command",
      items: [
        { label: "Mission Control", to: "/superadmin/dashboard", icon: Home },
        { label: "Security Analytics", to: "/superadmin/analytics", icon: BarChart3 },
        { label: "Verification", to: "/superadmin/verification", icon: Shield },
        { label: "Activity", to: "/superadmin/activity", icon: Activity },
      ],
    },
    {
      label: "Platform",
      items: [
        { label: "Announcements", to: "/superadmin/announcements", icon: FileText },
        { label: "Settings", to: "/superadmin/settings", icon: Settings },
      ],
    },
  ],
};
