export const EMPTY_TEXT = "-";

const TERM_ALIASES = [
  { order: 1, shortLabel: "T1", matches: ["first", "1st", "one", "t1", "term 1", "1"] },
  { order: 2, shortLabel: "T2", matches: ["second", "2nd", "two", "t2", "term 2", "2"] },
  { order: 3, shortLabel: "T3", matches: ["third", "3rd", "three", "t3", "term 3", "3"] },
];

export const cleanText = (value, fallback = EMPTY_TEXT) => {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value).replace(/_/g, " ");
};

export const formatChartLabel = (value, fallback = "Unknown") => {
  const normalized = cleanText(value, fallback);
  return normalized
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      if (word === word.toUpperCase()) return word;
      if (word === word.toLowerCase()) return word.charAt(0).toUpperCase() + word.slice(1);
      return word;
    })
    .join(" ");
};

export const asItems = (response) => response?.items || [];

export const averageScore = (items, key = "total_score") => {
  const scores = (Array.isArray(items) ? items : [])
    .map((item) => Number(item?.[key]))
    .filter((value) => Number.isFinite(value));
  if (scores.length === 0) return 0;
  return Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length);
};

export const chartFromCounts = (items, key, fallbackLabel = "unknown") => {
  const counts = (Array.isArray(items) ? items : []).reduce((groups, item) => {
    const label = cleanText(item?.[key], fallbackLabel);
    groups[label] = (groups[label] || 0) + 1;
    return groups;
  }, {});
  return Object.entries(counts).map(([label, value]) => ({ label, value }));
};

export const subjectPerformanceChart = (results) =>
  (Array.isArray(results) ? results : []).map((item) => ({
    label: item.subject_code || item.subject_name || "Subject",
    value: Number(item.total_score || 0),
  }));

export const averageBy = (items, labelGetter, valueKey = "total_score") => {
  const groups = {};
  (Array.isArray(items) ? items : []).forEach((item) => {
    const label = labelGetter(item) || "Unknown";
    const value = Number(item?.[valueKey]);
    if (!Number.isFinite(value)) return;
    if (!groups[label]) groups[label] = { total: 0, count: 0 };
    groups[label].total += value;
    groups[label].count += 1;
  });
  return Object.entries(groups).map(([label, group]) => ({
    label,
    value: Math.round(group.total / group.count),
  }));
};

export const reportCardStatusChart = (cards) => chartFromCounts(cards, "status", "not generated");

function parseSessionOrder(value) {
  const source = cleanText(value, "");
  const matches = source.match(/\d{4}/g);
  if (!matches?.length) return Number.MAX_SAFE_INTEGER;
  return Number(matches[0]);
}

function resolveTermMeta(value) {
  const normalized = cleanText(value, "").toLowerCase();

  for (const alias of TERM_ALIASES) {
    if (alias.matches.some((token) => normalized.includes(token))) {
      return alias;
    }
  }

  return {
    order: Number.MAX_SAFE_INTEGER,
    shortLabel: formatChartLabel(value, "Term"),
  };
}

function compactSessionLabel(value) {
  const source = cleanText(value, "");
  const matches = source.match(/\d{4}/g);
  if (matches?.length >= 2) {
    return `${matches[0]}/${matches[1].slice(-2)}`;
  }
  if (matches?.length === 1) {
    return matches[0];
  }
  return formatChartLabel(source, "Session");
}

export const averageByAcademicPeriod = (items, valueKey = "total_score") => {
  const groups = {};

  (Array.isArray(items) ? items : []).forEach((item) => {
    const value = Number(item?.[valueKey]);
    if (!Number.isFinite(value)) return;

    const session = cleanText(item?.academic_session_name, "Session");
    const term = cleanText(item?.academic_term_name, "Term");
    const key = `${session}__${term}`;

    if (!groups[key]) {
      groups[key] = {
        session,
        term,
        total: 0,
        count: 0,
      };
    }

    groups[key].total += value;
    groups[key].count += 1;
  });

  return Object.values(groups)
    .sort((left, right) => {
      const sessionOrder = parseSessionOrder(left.session) - parseSessionOrder(right.session);
      if (sessionOrder !== 0) return sessionOrder;
      return resolveTermMeta(left.term).order - resolveTermMeta(right.term).order;
    })
    .map((group) => {
      const termMeta = resolveTermMeta(group.term);
      return {
        label: `${compactSessionLabel(group.session)} ${termMeta.shortLabel}`.trim(),
        fullLabel: `${formatChartLabel(group.session, "Session")} / ${formatChartLabel(group.term, "Term")}`,
        value: Math.round(group.total / group.count),
      };
    });
};

export const bestAndWeakestSubject = (results) => {
  const scored = (Array.isArray(results) ? results : [])
    .map((item) => ({
      label: item.subject_name || item.subject_code || "Subject",
      value: Number(item.total_score),
    }))
    .filter((item) => Number.isFinite(item.value));
  if (scored.length === 0) return { best: null, weakest: null };
  const sorted = [...scored].sort((a, b) => b.value - a.value);
  return { best: sorted[0], weakest: sorted[sorted.length - 1] };
};

export const completionPercent = (completed, total) => {
  const safeTotal = Number(total) || 0;
  if (safeTotal <= 0) return 0;
  return Math.round((Number(completed || 0) / safeTotal) * 100);
};
