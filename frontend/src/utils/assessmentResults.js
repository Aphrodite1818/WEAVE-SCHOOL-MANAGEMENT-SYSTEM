export const hasAssessmentScore = (value) =>
  value !== null && value !== undefined && value !== "";

export const orderedAssessmentComponents = (components = []) =>
  [...components].sort((left, right) => Number(left.position) - Number(right.position));

export const componentScoreTotal = (components = []) =>
  components.reduce(
    (total, component) =>
      total + (hasAssessmentScore(component.score) ? Number(component.score) || 0 : 0),
    0,
  );

export const isAssessmentComplete = (components = []) =>
  components.length > 0 && components.every((component) => hasAssessmentScore(component.score));
