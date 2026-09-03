const asArray = (value) => (Array.isArray(value) ? value : []);

export const categorySupportsDepartments = (categoryOptions, category) =>
  asArray(categoryOptions).some(
    (option) => option?.value === category && Boolean(option?.supports_departments),
  );

export const supportsDepartmentWorkflow = (categoryOptions) =>
  asArray(categoryOptions).some((option) => Boolean(option?.supports_departments));

export const filterDepartmentWorkflow = (workflows, categoryOptions) => {
  const rows = asArray(workflows);
  if (supportsDepartmentWorkflow(categoryOptions)) return rows;
  return rows.filter((workflow) => workflow !== "departments");
};

export const normalizeSpecializationTermPosition = (
  categoryOptions,
  category,
  levelPosition,
  value,
) => {
  if (!categorySupportsDepartments(categoryOptions, category)) return null;
  if (category !== "SENIOR_SECONDARY") return null;

  const numericLevelPosition = Number(levelPosition);
  if (Number.isInteger(numericLevelPosition) && numericLevelPosition > 1) return 1;
  if (value === "" || value === null || value === undefined) return 1;

  const position = Number(value);
  return Number.isInteger(position) && position >= 1 && position <= 3
    ? position
    : null;
};
