const TERM_POSITIONS = {
  first_term: 1,
  second_term: 2,
  third_term: 3,
};

export const termLabel = (term) =>
  String(term?.name || "current term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export const currentOpenTerm = (terms) => {
  const rows = Array.isArray(terms) ? terms : terms?.items || [];
  return (
    rows.find(
      (term) =>
        term?.is_current === true &&
        String(term?.status || "").toLowerCase() === "open",
    ) || null
  );
};

export const specializationIsActiveForTerm = (level, term) => {
  if (!level || !term) return false;
  const threshold = Number(level.specialization_required_from_term_position);
  const termPosition = TERM_POSITIONS[String(term.name || "").toLowerCase()];
  return (
    Number.isInteger(threshold) &&
    threshold >= 1 &&
    Number.isInteger(termPosition) &&
    termPosition >= threshold
  );
};

export const activeLevelDepartments = (availability, levelId) => {
  const rows = Array.isArray(availability)
    ? availability
    : availability?.items || [];
  return rows.filter(
    (row) =>
      String(row?.academic_level_id || "") === String(levelId || "") &&
      row?.is_active !== false &&
      !row?.archived_at,
  );
};

export const currentTermDepartmentRequirement = ({
  level,
  term,
  availability,
} = {}) => {
  if (!specializationIsActiveForTerm(level, term)) {
    return {
      required: false,
      term,
      options: [],
      blocked: false,
    };
  }

  const departments = activeLevelDepartments(availability, level?.id);
  return {
    required: true,
    term,
    blocked: departments.length === 0,
    options: departments.map((row) => ({
      value: row.id,
      label: row.department_name || "Department",
    })),
  };
};
