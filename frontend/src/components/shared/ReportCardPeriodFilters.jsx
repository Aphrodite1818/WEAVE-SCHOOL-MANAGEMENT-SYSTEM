import { useEffect, useMemo } from "react";

function uniqueOptions(cards, idKey, labelKey) {
  const seen = new Set();
  return (cards || []).reduce((options, card) => {
    const value = card?.[idKey];
    if (!value || seen.has(value)) return options;
    seen.add(value);
    options.push({ value, label: card?.[labelKey] || "Unknown" });
    return options;
  }, []);
}

export function filterReportCardsByPeriod(cards, sessionId, termId) {
  return (cards || []).filter(
    (card) =>
      (!sessionId || card.academic_session_id === sessionId) &&
      (!termId || card.academic_term_id === termId),
  );
}

function ReportCardPeriodFilters({
  cards,
  sessionId,
  termId,
  onSessionChange,
  onTermChange,
}) {
  const sessions = useMemo(
    () => uniqueOptions(cards, "academic_session_id", "academic_session_name"),
    [cards],
  );
  const terms = useMemo(
    () =>
      uniqueOptions(
        (cards || []).filter(
          (card) => !sessionId || card.academic_session_id === sessionId,
        ),
        "academic_term_id",
        "academic_term_name",
      ),
    [cards, sessionId],
  );

  useEffect(() => {
    if (termId && !terms.some((term) => term.value === termId)) {
      onTermChange("");
    }
  }, [onTermChange, termId, terms]);

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="block text-sm font-semibold text-text-soft">
        <span className="mb-1.5 block">Academic session</span>
        <select
          className="input-base"
          value={sessionId}
          onChange={(event) => {
            onSessionChange(event.target.value);
            onTermChange("");
          }}
        >
          <option value="">All sessions</option>
          {sessions.map((session) => (
            <option key={session.value} value={session.value}>
              {session.label}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-semibold text-text-soft">
        <span className="mb-1.5 block">Academic term</span>
        <select
          className="input-base"
          value={termId}
          onChange={(event) => onTermChange(event.target.value)}
        >
          <option value="">All terms</option>
          {terms.map((term) => (
            <option key={term.value} value={term.value}>
              {term.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

export default ReportCardPeriodFilters;
