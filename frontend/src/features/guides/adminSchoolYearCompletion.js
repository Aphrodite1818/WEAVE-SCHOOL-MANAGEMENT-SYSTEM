export function adminSchoolYearCompletion(setupData) {
  const completion = setupData?.completion || {};
  const sessionOpen =
    setupData?.session_status === "open" && setupData?.session_is_current === true;

  return {
    ...completion,
    session: completion.session === true,
    // The Term milestone owns both term creation and opening the parent session.
    // Calendar must not become available until that lifecycle boundary succeeds.
    term: completion.term === true && sessionOpen,
    calendar: completion.calendar === true,
  };
}
