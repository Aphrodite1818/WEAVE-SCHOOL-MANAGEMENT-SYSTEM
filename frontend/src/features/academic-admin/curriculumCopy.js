export function curriculumCopySources(levels, target) {
  if (!target?.category) return [];
  return levels.filter((level) => level.id !== target.id &&
    level.category === target.category && level.status === "active");
}

export function curriculumCopyPreview(sourceSubjects, targetSubjects, targetDepartments) {
  const existing = new Set(targetSubjects.map((row) => row.subject_id));
  const enabledDepartments = new Set(targetDepartments.map((row) => row.department_id));
  const active = sourceSubjects.filter((row) => row.is_active !== false);
  const missing = active.filter((row) => !existing.has(row.subject_id));
  const unavailableDepartments = [...new Set(missing.flatMap((row) =>
    (row.departments || []).filter((department) => !enabledDepartments.has(department.department_id))
      .map((department) => department.department_name || "Department")))];
  return { missing, existingCount: active.length - missing.length, unavailableDepartments };
}
