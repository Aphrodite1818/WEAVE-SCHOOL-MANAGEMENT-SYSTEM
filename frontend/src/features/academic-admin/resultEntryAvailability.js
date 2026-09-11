const sameSubjectScope = (result, assignment) => {
  if (result?.curriculum_subject_id && assignment?.curriculum_subject_id) {
    return result.curriculum_subject_id === assignment.curriculum_subject_id;
  }
  return Boolean(result?.subject_id && result.subject_id === assignment?.subject_id);
};

export const resultForAssignment = (results, assignment) =>
  (results || []).find((result) => sameSubjectScope(result, assignment)) || null;

export const resultHasAllComponentScores = (result) => {
  const components = Array.isArray(result?.components) ? result.components : [];
  return (
    components.length > 0 &&
    components.every(
      (component) =>
        component.score !== null &&
        component.score !== undefined &&
        component.score !== "",
    )
  );
};

export const assignmentsAvailableForEntry = (assignments, results, classId) =>
  (assignments || []).filter(
    (assignment) =>
      (!classId || assignment.class_id === classId) &&
      !resultHasAllComponentScores(resultForAssignment(results, assignment)),
  );

export const componentScoresForAssignment = (results, assignment) => {
  const result = resultForAssignment(results, assignment);
  return Object.fromEntries(
    (result?.components || []).map((component) => [
      component.assessment_component_id,
      component.score ?? "",
    ]),
  );
};
