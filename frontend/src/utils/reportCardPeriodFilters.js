export function filterReportCardsByPeriod(cards, sessionId, termId) {
  return (cards || []).filter(
    (card) =>
      (!sessionId || card.academic_session_id === sessionId) &&
      (!termId || card.academic_term_id === termId),
  );
}
