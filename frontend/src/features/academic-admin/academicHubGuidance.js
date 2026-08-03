const metricNumber = (value, fallback = 0) => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

export function chooseAcademicHubNextAction(stats = {}, hasMetrics = false) {
  if (!hasMetrics) {
    return {
      action: "Load the current academic picture",
      description: "The hub is getting the latest school data before recommending work.",
      buttonLabel: "Refresh overview",
      to: "/admin/academic",
    };
  }

  if (!stats.active_academic_session) {
    return {
      action: "Create or open the current academic session",
      description: "Academic work needs an open school year before terms, results, calendars, and report cards can move cleanly.",
      buttonLabel: "Manage sessions",
      to: "/admin/academic/sessions",
    };
  }

  if (!stats.active_academic_term) {
    return {
      action: "Create or open the current term",
      description: "The current term tells teachers, results, calendars, and report cards which period they are working in.",
      buttonLabel: "Manage terms",
      to: "/admin/academic/terms",
    };
  }

  if (metricNumber(stats.total_classes) === 0) {
    return {
      action: "Create the first class",
      description: "Classes are needed before students, subjects, teacher assignments, and results can be organized.",
      buttonLabel: "Create class",
      to: "/admin/academic/classes?view=create",
    };
  }

  if (metricNumber(stats.total_subjects) === 0) {
    return {
      action: "Add the subjects taught by the school",
      description: "Subjects must exist before they can be attached to classes or assigned to teachers.",
      buttonLabel: "Add subject",
      to: "/admin/academic/subjects?view=create",
    };
  }

  if (metricNumber(stats.result_rows_submitted) > 0) {
    return {
      action: "Review submitted results",
      description: "Submitted results are waiting for administrative approval before they can be locked for report cards.",
      buttonLabel: "Review results",
      to: "/admin/academic/results?view=submitted",
    };
  }

  if (metricNumber(stats.report_cards_generated) > metricNumber(stats.report_cards_published)) {
    return {
      action: "Publish ready report cards",
      description: "Generated report cards that are not yet published are not visible as final records.",
      buttonLabel: "Open report cards",
      to: "/admin/academic/report-cards?view=draft",
    };
  }

  return {
    action: "Review the session closure checklist",
    description: "When sessions, terms, results, report cards, and calendars are ready, progression can be prepared safely.",
    buttonLabel: "Check progression",
    to: "/admin/academic/sessions?view=closing",
  };
}
