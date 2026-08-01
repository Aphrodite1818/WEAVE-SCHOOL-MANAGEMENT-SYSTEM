from __future__ import annotations

import re
from pathlib import Path


def replace_regex(path: str, pattern: str, replacement: str, *, flags: int = 0) -> None:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}, found {count}: {pattern[:120]!r}")
    file_path.write_text(updated, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:140]!r}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")


config_path = "frontend/src/features/guides/roleGuideConfig.js"
admin_config = '''  admin: {
    key: "tenant_admin_academic_setup",
    route: "/admin/getting-started",
    dashboardRoute: "/admin/dashboard",
    eyebrow: "Academic setup",
    title: "Set up your school workspace",
    description:
      "Follow the backend-safe setup order. Every stage is verified against your live school data before the next lifecycle transition.",
    steps: [
      {
        id: "session",
        shortLabel: "Session",
        label: "Create an academic session",
        description:
          "Define the dated academic year that the term and school calendar will belong to.",
        icon: CalendarDays,
      },
      {
        id: "term",
        shortLabel: "Term",
        label: "Create a term in the session",
        description:
          "Create the first draft term and keep its dates inside the academic session date range.",
        icon: CalendarCheck2,
      },
      {
        id: "calendar",
        shortLabel: "Calendar",
        label: "Configure and generate the calendar",
        description:
          "Save the school calendar defaults and generate complete operational days for the draft term.",
        icon: CalendarDays,
      },
      {
        id: "structure",
        shortLabel: "Structure",
        label: "Create classes and subjects",
        description:
          "Create at least one active class and one active subject before launching normal academic work.",
        icon: School,
      },
      {
        id: "session_open",
        shortLabel: "Open session",
        label: "Open the academic session",
        description:
          "The backend requires a dated draft session, at least one term, and saved calendar configuration before the session can become current.",
        icon: GraduationCap,
      },
      {
        id: "calendar_active",
        shortLabel: "Activate calendar",
        label: "Activate the school calendar",
        description:
          "Calendar activation happens only after the session is open and while the selected term is still draft.",
        icon: CalendarCheck2,
      },
      {
        id: "term_open",
        shortLabel: "Open term",
        label: "Open the academic term",
        description:
          "Open the term last. The backend requires both the current open session and an active, complete calendar.",
        icon: GraduationCap,
      },
    ],
  },
  teacher: {'''
replace_regex(
    config_path,
    r'  admin: \{\n.*?\n  \},\n  teacher: \{',
    admin_config,
    flags=re.DOTALL,
)

page_path = "frontend/src/pages/admin/AdminGettingStartedPage.jsx"
completion_block = '''  const sessionActive = Boolean(
    selectedSession &&
      statusValue(selectedSession) === "open" &&
      selectedSession.is_current,
  );
  const termActive = Boolean(
    selectedTerm && statusValue(selectedTerm) === "open" && selectedTerm.is_current,
  );
  const calendarActive = statusValue(selectedCalendar) === "active";
  const sessionDraft = statusValue(selectedSession) === "draft";
  const termDraft = statusValue(selectedTerm) === "draft";
  const sessionDatesComplete = Boolean(
    selectedSession?.start_date && selectedSession?.end_date,
  );
  const termDatesComplete = Boolean(selectedTerm?.start_date && selectedTerm?.end_date);
  const calendarPrepared = Boolean(
    calendarConfiguration &&
      selectedCalendar &&
      !selectedCalendar.configuration_outdated &&
      Number(selectedCalendar.missing_dates || 0) === 0 &&
      Number(selectedCalendar.extra_dates || 0) === 0 &&
      Number(selectedCalendar.duplicate_dates || 0) === 0 &&
      Number(selectedCalendar.invalid_days || 0) === 0 &&
      Number(selectedCalendar.dependency_counts?.unresolved_days || 0) === 0,
  );
  const calendarBlockers = Array.isArray(selectedCalendar?.blocker_messages)
    ? selectedCalendar.blocker_messages
    : [];
  const anotherOpenTerm = terms.find(
    (item) =>
      item.id !== selectedTerm?.id &&
      statusValue(item) === "open" &&
      item.is_current,
  );
  const sessionOpenReady = Boolean(
    selectedSession &&
      sessionDraft &&
      sessionDatesComplete &&
      selectedTerm &&
      calendarConfiguration,
  );
  const calendarActivationReady = Boolean(
    selectedCalendar &&
      calendarPrepared &&
      sessionActive &&
      termDraft &&
      selectedCalendar.can_activate !== false,
  );
  const termOpenReady = Boolean(
    selectedTerm &&
      termDraft &&
      termDatesComplete &&
      sessionActive &&
      calendarActive &&
      !anotherOpenTerm,
  );
  const completionMap = useMemo(
    () => ({
      session: Boolean(selectedSession),
      term: Boolean(selectedSession && selectedTerm),
      calendar: calendarPrepared,
      structure: classes.length > 0 && subjects.length > 0,
      session_open: sessionActive,
      calendar_active: calendarActive,
      term_open: termActive,
    }),
    [
      calendarActive,
      calendarPrepared,
      classes.length,
      selectedSession,
      selectedTerm,
      sessionActive,
      subjects.length,
      termActive,
    ],
  );
  const guide = useRoleGuide({ role: "admin", completionMap });'''
replace_regex(
    page_path,
    r'  const sessionActive = Boolean\(\n.*?  const guide = useRoleGuide\(\{ role: "admin", completionMap \}\);',
    completion_block,
    flags=re.DOTALL,
)

replace_once(
    page_path,
    "          overwrite_generated_days: false,",
    "          overwrite_generated_days: Boolean(selectedCalendar),",
)
replace_once(
    page_path,
    "      ) : calendarsForTerm.length ? (",
    "      ) : calendarPrepared ? (",
)
replace_once(
    page_path,
    "    if (subjects.length > 0) await guide.moveTo(\"activation\");",
    "    if (subjects.length > 0) await guide.moveTo(\"session_open\");",
)
replace_once(
    page_path,
    "    if (classes.length > 0) await guide.moveTo(\"activation\");",
    "    if (classes.length > 0) await guide.moveTo(\"session_open\");",
)

handlers = '''  const openSession = async () => {
    if (!selectedSession?.id) return;
    const result = await runAction(
      "open-session",
      () => academicService.openSession(selectedSession.id),
      "Academic session opened.",
    );
    if (result) await guide.moveTo("calendar_active");
  };

  const activateCalendar = async () => {
    if (!selectedCalendar?.id) return;
    const result = await runAction(
      "activate-calendar",
      () => schoolCalendarService.activateCalendar(selectedCalendar.id),
      "School calendar activated.",
    );
    if (result) await guide.moveTo("term_open");
  };

  const openTerm = async () => {
    if (!selectedTerm?.id) return;
    const result = await runAction(
      "open-term",
      () => academicService.openTerm(selectedTerm.id),
      "Academic term opened.",
    );
    if (result) await guide.finish();
  };'''
replace_regex(
    page_path,
    r'  const activateCalendar = async \(\) => \{.*?\n  const openTerm = async \(\) => \{.*?\n  \};',
    handlers,
    flags=re.DOTALL,
)
replace_once(
    page_path,
    "      if (completionMap.activation) {",
    "      if (completionMap.term_open) {",
)

launch_steps = '''  const renderSessionOpenStep = () => (
    <div className="space-y-4">
      <div className="rounded-2xl border border-primary/20 bg-primary-soft/35 p-4 sm:p-5">
        <p className="font-semibold text-text">Why the session opens first</p>
        <p className="mt-1 text-sm leading-6 text-text-muted">
          The backend requires the session to be open and current before it will allow calendar activation. Opening the session requires complete dates, at least one term, and saved calendar defaults.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SetupCheck
          label="Draft session selected"
          complete={sessionDraft || sessionActive}
          detail={selectedSession ? `${sessionLabel(selectedSession)} · ${titleCase(selectedSession.status)}` : "No session selected"}
        />
        <SetupCheck
          label="Session dates complete"
          complete={sessionDatesComplete}
          detail={sessionDatesComplete ? `${selectedSession.start_date} to ${selectedSession.end_date}` : "Start and end dates are required"}
        />
        <SetupCheck
          label="At least one term exists"
          complete={Boolean(selectedTerm)}
          detail={selectedTerm ? termLabel(selectedTerm) : "Create a term in this session"}
        />
        <SetupCheck
          label="Calendar defaults saved"
          complete={Boolean(calendarConfiguration)}
          detail={calendarConfiguration ? "Configuration is available" : "Save calendar defaults first"}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-text">Open {sessionLabel(selectedSession)}</p>
          <p className="mt-1 text-sm text-text-muted">
            This makes the session current. The term remains draft until the calendar is activated.
          </p>
        </div>
        <Button
          type="button"
          variant={sessionActive ? "outline" : "primary"}
          disabled={!sessionOpenReady || sessionActive || saving === "open-session"}
          onClick={openSession}
          className="w-full sm:w-auto"
        >
          {saving === "open-session" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}
          {sessionActive ? "Session open" : "Open session"}
        </Button>
      </div>
    </div>
  );

  const renderCalendarActivationStep = () => (
    <div className="space-y-4">
      <div className="rounded-2xl border border-primary/20 bg-primary-soft/35 p-4 sm:p-5">
        <p className="font-semibold text-text">Activate the calendar while the term is draft</p>
        <p className="mt-1 text-sm leading-6 text-text-muted">
          Calendar activation requires the selected session to be open and current, the term to remain draft, and every calendar date to pass the backend readiness checks.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SetupCheck
          label="Session open and current"
          complete={sessionActive}
          detail={selectedSession ? `${sessionLabel(selectedSession)} · ${titleCase(selectedSession.status)}` : "Open the session first"}
        />
        <SetupCheck
          label="Term still draft"
          complete={termDraft || termActive}
          detail={selectedTerm ? `${termLabel(selectedTerm)} · ${titleCase(selectedTerm.status)}` : "No term selected"}
        />
        <SetupCheck
          label="Calendar generated and current"
          complete={calendarPrepared || calendarActive}
          detail={selectedCalendar ? `${titleCase(selectedCalendar.status)} calendar` : "Generate the calendar first"}
        />
        <SetupCheck
          label="Backend readiness passed"
          complete={calendarActive || (calendarPrepared && selectedCalendar?.can_activate !== false)}
          detail={calendarActive ? "Calendar is active" : calendarBlockers.length ? `${calendarBlockers.length} blocker${calendarBlockers.length === 1 ? "" : "s"} remain` : "No activation blockers"}
        />
      </div>

      {!calendarActive && calendarBlockers.length ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4">
          <p className="text-sm font-semibold text-text">Resolve these backend blockers</p>
          <ul className="mt-2 space-y-1.5 text-sm leading-6 text-text-muted">
            {calendarBlockers.map((blocker) => (
              <li key={blocker} className="flex gap-2">
                <span aria-hidden="true">•</span>
                <span>{blocker}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-text">Activate {termLabel(selectedTerm)} calendar</p>
          <p className="mt-1 text-sm text-text-muted">
            Activation locks in the operational calendar required by term opening.
          </p>
        </div>
        <Button
          type="button"
          variant={calendarActive ? "outline" : "primary"}
          disabled={!calendarActivationReady || calendarActive || saving === "activate-calendar"}
          onClick={activateCalendar}
          className="w-full sm:w-auto"
        >
          {saving === "activate-calendar" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
          {calendarActive ? "Calendar active" : "Activate calendar"}
        </Button>
      </div>
    </div>
  );

  const renderTermOpenStep = () => (
    <div className="space-y-4">
      <div className="rounded-2xl border border-primary/20 bg-primary-soft/35 p-4 sm:p-5">
        <p className="font-semibold text-text">Open the term last</p>
        <p className="mt-1 text-sm leading-6 text-text-muted">
          The backend will open a draft term only when its parent session is open and current and its generated school calendar is active and complete.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SetupCheck
          label="Session open and current"
          complete={sessionActive}
          detail={selectedSession ? sessionLabel(selectedSession) : "No session selected"}
        />
        <SetupCheck
          label="Calendar active"
          complete={calendarActive}
          detail={selectedCalendar ? titleCase(selectedCalendar.status) : "No calendar selected"}
        />
        <SetupCheck
          label="Term ready to open"
          complete={termDraft || termActive}
          detail={selectedTerm ? `${termLabel(selectedTerm)} · ${titleCase(selectedTerm.status)}` : "No term selected"}
        />
        <SetupCheck
          label="No other current term"
          complete={!anotherOpenTerm}
          detail={anotherOpenTerm ? `${termLabel(anotherOpenTerm)} is already open` : "No conflicting open term"}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-text">Open {termLabel(selectedTerm)}</p>
          <p className="mt-1 text-sm text-text-muted">
            This is the final academic lifecycle transition in the setup assistant.
          </p>
        </div>
        <Button
          type="button"
          variant={termActive ? "outline" : "primary"}
          disabled={!termOpenReady || termActive || saving === "open-term"}
          onClick={openTerm}
          className="w-full sm:w-auto"
        >
          {saving === "open-term" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clock3 className="h-4 w-4" />}
          {termActive ? "Term open" : "Open term"}
        </Button>
      </div>

      {termActive ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Academic setup is active</p>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                The session is current, the school calendar is active, and the term is open. The tenant can now continue from the Academic Hub.
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );'''
replace_regex(
    page_path,
    r'  const renderActivationStep = \(\) => \(.*?\n  \);\n\n  const renderCurrentStep = \(\) => \{',
    launch_steps + '\n\n  const renderCurrentStep = () => {',
    flags=re.DOTALL,
)

render_mapping = '''  const renderCurrentStep = () => {
    if (current.id === "session") return renderSessionStep();
    if (current.id === "term") return renderTermStep();
    if (current.id === "calendar") return renderCalendarStep();
    if (current.id === "structure") return renderStructureStep();
    if (current.id === "session_open") return renderSessionOpenStep();
    if (current.id === "calendar_active") return renderCalendarActivationStep();
    return renderTermOpenStep();
  };

  return ('''
replace_regex(
    page_path,
    r'  const renderCurrentStep = \(\) => \{.*?\n  \};\n\n  return \(',
    render_mapping,
    flags=re.DOTALL,
)

replace_once(
    page_path,
    '      description="Complete the minimum academic foundation without leaving the guided workspace."',
    '      description="Follow the backend-safe setup sequence without leaving the guided workspace."',
)

live_status = '''                <SetupCheck
                  label="Session created"
                  complete={completionMap.session}
                  detail={selectedSession ? sessionLabel(selectedSession) : "Waiting for a session"}
                />
                <SetupCheck
                  label="Term created"
                  complete={completionMap.term}
                  detail={selectedTerm ? termLabel(selectedTerm) : "Waiting for a term"}
                />
                <SetupCheck
                  label="Calendar prepared"
                  complete={completionMap.calendar}
                  detail={selectedCalendar ? titleCase(selectedCalendar.status) : "Waiting for a calendar"}
                />
                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${classes.length} classes · ${subjects.length} subjects`}
                />
                <SetupCheck
                  label="Session open"
                  complete={completionMap.session_open}
                  detail={sessionActive ? "Current academic session" : "Waiting for session opening"}
                />
                <SetupCheck
                  label="Calendar active"
                  complete={completionMap.calendar_active}
                  detail={calendarActive ? "Operational calendar active" : "Waiting for calendar activation"}
                />
                <SetupCheck
                  label="Term open"
                  complete={completionMap.term_open}
                  detail={termActive ? "Current academic term" : "Waiting for term opening"}
                />'''
replace_regex(
    page_path,
    r'                <SetupCheck\n                  label="Session created".*?                <SetupCheck\n                  label="Academic period active".*?                />',
    live_status,
    flags=re.DOTALL,
)

replace_once(
    page_path,
    '                The calendar for {termLabel(selectedTerm)} is {titleCase(selectedCalendar?.status || "draft")}.',
    '                The calendar for {termLabel(selectedTerm)} matches the current saved configuration and is ready for lifecycle checks.',
)
replace_once(
    page_path,
    '{saving === "calendar" ? "Generating calendar..." : "Save defaults and generate calendar"}',
    '{saving === "calendar" ? "Preparing calendar..." : selectedCalendar ? "Save defaults and regenerate calendar" : "Save defaults and generate calendar"}',
)

# Rewrite the small guide configuration regression test around the new backend-safe order.
test_path = Path("frontend/src/features/guides/roleGuideConfig.test.js")
test_path.write_text(
    '''import assert from "node:assert/strict";\nimport test from "node:test";\n\nimport { ROLE_GUIDES, guideForRole } from "./roleGuideConfig.js";\n\nconst expectedRoles = ["admin", "teacher", "parent", "student"];\n\ntest("every supported dashboard role has a valid page guide", () => {\n  assert.deepEqual(Object.keys(ROLE_GUIDES).sort(), expectedRoles.sort());\n\n  for (const role of expectedRoles) {\n    const guide = guideForRole(role);\n    assert.ok(guide);\n    assert.match(guide.key, /^[a-z0-9][a-z0-9_-]+$/);\n    const expectedStepCount = role === "admin" ? 7 : 4;\n    assert.equal(guide.steps.length, expectedStepCount);\n    assert.equal(new Set(guide.steps.map((step) => step.id)).size, expectedStepCount);\n\n    for (const step of guide.steps) {\n      assert.ok(step.label);\n      assert.ok(step.description);\n      if (role !== "admin") {\n        assert.ok(step.actionLabel);\n        assert.ok(step.to.startsWith(`/${role}/`));\n      }\n    }\n  }\n});\n\ntest("unknown roles do not receive a guide", () => {\n  assert.equal(guideForRole("superadmin"), null);\n  assert.equal(guideForRole(""), null);\n});\n\ntest("tenant admin guide follows the backend lifecycle dependency order", () => {\n  assert.deepEqual(\n    ROLE_GUIDES.admin.steps.map((step) => step.id),\n    [\n      "session",\n      "term",\n      "calendar",\n      "structure",\n      "session_open",\n      "calendar_active",\n      "term_open",\n    ],\n  );\n});\n''',
    encoding="utf-8",
)
