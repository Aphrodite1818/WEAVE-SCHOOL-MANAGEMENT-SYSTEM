export const dayTypeLabels = {
  instructional_day: "Instructional day",
  examination_day: "Examination day",
  weekend: "Weekend",
  public_holiday: "Public holiday",
  school_holiday: "School holiday",
  mid_term_break: "Mid-term break",
  staff_training_day: "Staff training",
  special_school_day: "Special school day",
  emergency_closure: "Emergency closure",
};

export const audienceLabels = {
  all: "Everyone",
  tenant_admins: "Admins",
  teachers: "Teachers",
  parents: "Parents",
  students: "Students",
};

export const eventTypeLabels = {
  academic: "Academic",
  holiday: "Holiday",
  examination: "Examination",
  meeting: "Meeting",
  activity: "Activity",
  emergency: "Emergency",
  other: "Other",
};

export const formatCalendarDate = (value, options = {}) => {
  if (!value) return "-";
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    ...options,
  }).format(date);
};

export const formatCalendarTime = (value) => {
  if (!value) return "-";
  const [hour, minute] = String(value).split(":");
  const date = new Date();
  date.setHours(Number(hour || 0), Number(minute || 0), 0, 0);
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
};

export const dayTypeLabel = (value) => dayTypeLabels[value] || "Unclassified day";

export const calendarStatusTone = (status) => {
  const value = String(status || "").toLowerCase();
  if (["active", "open", "published"].includes(value)) return "success";
  if (["draft", "closing", "pending"].includes(value)) return "warning";
  if (["archived", "closed", "cancelled"].includes(value)) return "error";
  return "default";
};

export const schoolOpenLabel = (today) => {
  if (!today || today.code !== "ok") return "Calendar not active";
  return today.school_open ? "School open" : "School closed";
};

export const passiveAttendanceText = (today, role = "student") => {
  if (!today || today.code !== "ok") return "Calendar setup is required.";
  if (!today.school_open) return "Attendance is not required today.";
  if (role === "teacher") {
    return today.workforce_attendance_required
      ? "Staff are expected on campus today."
      : "Staff attendance is not expected today.";
  }
  return today.student_attendance_required
    ? "Attendance is expected today."
    : "Attendance is not expected today.";
};
