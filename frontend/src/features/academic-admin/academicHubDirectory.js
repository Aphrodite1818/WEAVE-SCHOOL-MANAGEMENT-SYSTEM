const numberLabel = (value, noun) => {
  const count = Number(value);
  return Number.isFinite(count) ? `${count.toLocaleString()} ${noun}` : "View records";
};

export const buildAcademicHubDirectory = (stats = {}) => [
  { key: "sessions", scope: stats.active_academic_session || "School years", state: stats.active_academic_session ? "Open" : "Needs setup", lifecycle: "Draft → Open → Closing → Closed" },
  { key: "terms", scope: stats.active_academic_term || "Academic periods", state: stats.active_academic_term ? "Open" : "Needs setup", lifecycle: "Draft → Open → Closing → Closed" },
  { key: "levels", scope: "Ordered progression levels", state: "Lifecycle enabled", lifecycle: "Draft → Active → Inactive → Archived" },
  { key: "arm-labels", scope: "Reusable class labels", state: "Lifecycle enabled", lifecycle: "Active → Inactive → Archived" },
  { key: "classes", scope: numberLabel(stats.total_classes, "classes"), state: Number(stats.total_classes) > 0 ? "Operational" : "Needs setup", lifecycle: "Active → Inactive → Archived" },
  { key: "departments", scope: "Specializations by level", state: "Lifecycle enabled", lifecycle: "Active → Inactive → Archived" },
  { key: "subjects", scope: numberLabel(stats.total_subjects, "subjects"), state: Number(stats.total_subjects) > 0 ? "Operational" : "Needs setup", lifecycle: "Active → Inactive → Archived" },
  { key: "curriculum", scope: "Subjects and offerings by level", state: Number(stats.total_subjects) > 0 ? "Ready to configure" : "Needs subjects", lifecycle: "Compulsory / Elective · Active / Inactive" },
  { key: "assignments", scope: "Class · Subject · Term", state: Number(stats.total_teachers) > 0 ? "Ready to assign" : "Needs teachers", lifecycle: "Scheduled → Active → Ended" },
  { key: "school-calendar", scope: "School days and events by term", state: stats.active_academic_term ? "Ready to configure" : "Needs open term", lifecycle: "Draft → Active → Archived" },
  { key: "grading", scope: "Assessment schemes and scales", state: "Configuration", lifecycle: "Draft → Active → Inactive" },
  { key: "results", scope: numberLabel(stats.result_rows_total, "result rows"), state: Number(stats.result_rows_submitted) > 0 ? "Needs review" : "In progress", lifecycle: "Draft → Submitted → Approved → Locked" },
  { key: "report-cards", scope: numberLabel(stats.report_cards_generated, "generated"), state: Number(stats.report_cards_generated) > Number(stats.report_cards_published) ? "Needs publishing" : "Ready", lifecycle: "Draft → Published → Archived" },
  { key: "progression", scope: numberLabel(stats.total_students, "students tracked"), state: stats.active_academic_session ? "Available" : "Needs open session", lifecycle: "Review → Progress → Graduate" },
];

export const filterAcademicHubDirectory = (rows, query = "") => {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) =>
    [row.title, row.shortTitle, row.description, row.scope, row.state, row.lifecycle]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle)),
  );
};
