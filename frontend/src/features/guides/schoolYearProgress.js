export const SCHOOL_YEAR_STEPS = ["session", "term", "calendar", "start_term"];
export const SCHOOL_YEAR_STAGES = [
  { id: "year", label: "School year", steps: ["session", "term"] },
  { id: "calendar", label: "Calendar", steps: ["calendar"] },
  { id: "start_term", label: "Start term", steps: ["start_term"] },
];

export function schoolYearProgress(completion = {}) {
  const completed = SCHOOL_YEAR_STEPS.filter((id) => completion[id] === true);
  return {
    completedCount: completed.length,
    completedStages: SCHOOL_YEAR_STAGES.filter((stage) => stage.steps.every((id) => completion[id] === true)).length,
    complete: completed.length === SCHOOL_YEAR_STEPS.length,
    nextStep: SCHOOL_YEAR_STEPS.find((id) => completion[id] !== true) || null,
    canOpen: (id) => {
      const index = SCHOOL_YEAR_STEPS.indexOf(id);
      return index >= 0 && SCHOOL_YEAR_STEPS.slice(0, index).every((previous) => completion[previous] === true);
    },
  };
}
