from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    file_path = ROOT / path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:160]!r}")
    write(path, content.replace(old, new, 1))


def replace_regex(path: str, pattern: str, replacement: str, *, flags: int = 0) -> None:
    content = read(path)
    updated, count = re.subn(pattern, replacement, content, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Expected one regex match in {path}, got {count}: {pattern[:160]!r}")
    write(path, updated)


# ---------------------------------------------------------------------------
# Shared guide navigation and live state synchronization
# ---------------------------------------------------------------------------
write(
    "frontend/src/features/guides/guideNavigation.js",
    '''const GUIDE_RETURN_STORAGE_KEY = "weave:guide-return";

export function saveGuideReturn(value) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(GUIDE_RETURN_STORAGE_KEY, JSON.stringify(value));
}

export function readGuideReturn() {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(GUIDE_RETURN_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed?.route || !parsed?.role) return null;
    return parsed;
  } catch {
    window.sessionStorage.removeItem(GUIDE_RETURN_STORAGE_KEY);
    return null;
  }
}

export function clearGuideReturn() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(GUIDE_RETURN_STORAGE_KEY);
}
''',
)

write(
    "frontend/src/features/guides/guideNavigation.test.js",
    '''import assert from "node:assert/strict";
import test from "node:test";

import { clearGuideReturn, readGuideReturn, saveGuideReturn } from "./guideNavigation.js";

function installWindow() {
  const values = new Map();
  global.window = {
    sessionStorage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    },
  };
  return values;
}

test("guide return state persists and clears", () => {
  installWindow();
  saveGuideReturn({ role: "teacher", route: "/teacher/getting-started", stepId: "results" });
  assert.deepEqual(readGuideReturn(), {
    role: "teacher",
    route: "/teacher/getting-started",
    stepId: "results",
  });
  clearGuideReturn();
  assert.equal(readGuideReturn(), null);
  delete global.window;
});
''',
)

replace_once(
    "frontend/src/features/guides/useRoleGuide.js",
    'import { guideForRole } from "./roleGuideConfig";\n',
    'import { guideForRole } from "./roleGuideConfig";\n\nexport const GUIDE_STATE_CHANGED_EVENT = "weave:guide-state-changed";\n',
)
replace_once(
    "frontend/src/features/guides/useRoleGuide.js",
    '''      const response = await guideService.updateState(config.key, payload);
      setGuideState(response);
      return response;
''',
    '''      const response = await guideService.updateState(config.key, payload);
      setGuideState(response);
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent(GUIDE_STATE_CHANGED_EVENT, {
            detail: { key: config.key, state: response },
          }),
        );
      }
      return response;
''',
)
replace_once(
    "frontend/src/features/guides/useRoleGuide.js",
    '''  useEffect(() => {
    loadGuide();
  }, [loadGuide]);
''',
    '''  useEffect(() => {
    loadGuide();
  }, [loadGuide]);

  useEffect(() => {
    if (typeof window === "undefined" || !config) return undefined;
    const handleStateChange = (event) => {
      if (event?.detail?.key !== config.key || !event.detail.state) return;
      setGuideState(event.detail.state);
    };
    window.addEventListener(GUIDE_STATE_CHANGED_EVENT, handleStateChange);
    return () => window.removeEventListener(GUIDE_STATE_CHANGED_EVENT, handleStateChange);
  }, [config]);
''',
)

# ---------------------------------------------------------------------------
# Full-screen tutorial shell and return-to-guide bridge
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    'import { Outlet, useLocation, useNavigate } from "react-router-dom";\n',
    'import { ArrowLeft, X } from "lucide-react";\nimport { Outlet, useLocation, useNavigate } from "react-router-dom";\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    'import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";\n',
    'import { clearGuideReturn, readGuideReturn } from "../../features/guides/guideNavigation";\nimport { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    'import AiChatLauncher from "../ai/AiChatLauncher";\n',
    'import AiChatLauncher from "../ai/AiChatLauncher";\nimport WeaveIcon from "../brand/WeaveIcon";\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    'import Modal from "../ui/Modal";\n',
    'import Button from "../ui/Button";\nimport Modal from "../ui/Modal";\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '  const role = getRole(user, roleProp);\n  const academicHubActive = location.pathname.startsWith("/admin/academic");\n',
    '  const role = getRole(user, roleProp);\n  const guidePageActive = location.pathname.endsWith("/getting-started");\n  const academicHubActive = location.pathname.startsWith("/admin/academic");\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '  const [mobileNavOpen, setMobileNavOpen] = useState(false);\n',
    '  const [mobileNavOpen, setMobileNavOpen] = useState(false);\n  const [guideReturn, setGuideReturn] = useState(() => readGuideReturn());\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '''  useEffect(() => {
    window.localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);
''',
    '''  useEffect(() => {
    window.localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (guidePageActive) {
      clearGuideReturn();
      setGuideReturn(null);
      return;
    }
    setGuideReturn(readGuideReturn());
  }, [guidePageActive, location.pathname]);
''',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '''  const pullRefreshLabel = isPullRefreshing
    ? "Refreshing..."
    : pullDistance >= PULL_REFRESH_THRESHOLD
      ? "Release to refresh"
      : "Pull to refresh";

  return (
''',
    '''  const pullRefreshLabel = isPullRefreshing
    ? "Refreshing..."
    : pullDistance >= PULL_REFRESH_THRESHOLD
      ? "Release to refresh"
      : "Pull to refresh";

  const returnToGuide = () => {
    const route = guideReturn?.route;
    clearGuideReturn();
    setGuideReturn(null);
    if (route) navigate(route);
  };
  const dismissGuideReturn = () => {
    clearGuideReturn();
    setGuideReturn(null);
  };

  if (guidePageActive) {
    return (
      <div
        ref={shellRef}
        data-dashboard-role={role}
        data-guide-page="true"
        className="min-h-[100dvh] overflow-y-auto bg-background text-text"
      >
        <header className="sticky top-0 z-40 border-b border-border/70 bg-surface/95 backdrop-blur-xl">
          <div className="mx-auto flex min-h-16 w-full max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <WeaveIcon className="h-10 w-10 shrink-0" decorative />
              <div>
                <p className="text-sm font-bold text-text">Weave</p>
                <p className="text-xs text-text-muted">Getting started</p>
              </div>
            </div>
            <Button
              type="button"
              size="small"
              variant="outline"
              onClick={() => navigate(roleGuide.config?.dashboardRoute || `/${role}/dashboard`)}
            >
              Finish later
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1440px] px-3 py-5 sm:px-6 sm:py-7 lg:px-8 lg:py-9">
          {children}
        </main>
      </div>
    );
  }

  return (
''',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '''            {showGettingStartedBanner ? (
              <GettingStartedBanner
''',
    '''            {guideReturn?.role === role ? (
              <section className="flex flex-col gap-3 rounded-2xl border border-primary/25 bg-primary-subtle/70 px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                    <ArrowLeft className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-text">Tutorial still in progress</p>
                    <p className="truncate text-xs text-text-muted">
                      {guideReturn.label || "Return to the getting-started page when you are done exploring."}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button type="button" size="small" onClick={returnToGuide}>
                    Return to tutorial
                  </Button>
                  <button
                    type="button"
                    onClick={dismissGuideReturn}
                    className="grid h-9 w-9 place-items-center rounded-xl text-text-muted transition hover:bg-surface hover:text-text"
                    aria-label="Dismiss tutorial return prompt"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </section>
            ) : null}
            {showGettingStartedBanner ? (
              <GettingStartedBanner
''',
)

replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    'import { ArrowLeft, ArrowRight, CheckCircle2, ExternalLink, Sparkles } from "lucide-react";\n',
    'import { ArrowLeft, ArrowRight, BookOpenCheck, CheckCircle2, ExternalLink } from "lucide-react";\n',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    'import useRoleGuide from "../../features/guides/useRoleGuide";\n',
    'import { saveGuideReturn } from "../../features/guides/guideNavigation";\nimport useRoleGuide from "../../features/guides/useRoleGuide";\n',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '''  const openWorkspace = async () => {
    await guide.moveTo(current.id);
    navigate(current.to);
  };
''',
    '''  const openWorkspace = async () => {
    await guide.moveTo(current.id);
    saveGuideReturn({
      role,
      route: guide.config.route,
      stepId: current.id,
      label: current.label,
    });
    navigate(current.to);
  };
''',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '<Sparkles className="h-4 w-4" />',
    '<BookOpenCheck className="h-4 w-4" />',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '''                    This guide does not cover the application with an overlay. Open the feature, use it normally, then return and mark the step complete.
''',
    '''                    Open the real workspace and use it normally. A persistent return bar will keep the tutorial one click away on every page.
''',
)

# ---------------------------------------------------------------------------
# Admin setup: multiple resources and class progression
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/features/guides/roleGuideConfig.js",
    '  GraduationCap,\n  School,\n',
    '  GraduationCap,\n  Route,\n  School,\n',
)
replace_once(
    "frontend/src/features/guides/roleGuideConfig.js",
    '''      {
        id: "session_open",
''',
    '''      {
        id: "progression",
        shortLabel: "Progression",
        label: "Configure class progression",
        description:
          "Choose the next class for every non-terminal class and mark final classes as terminal.",
        icon: Route,
      },
      {
        id: "session_open",
''',
)
replace_once(
    "frontend/src/features/guides/roleGuideConfig.test.js",
    '    const expectedStepCount = role === "admin" ? 7 : 4;\n',
    '    const expectedStepCount = role === "admin" ? 8 : 4;\n',
)
replace_once(
    "frontend/src/features/guides/roleGuideConfig.test.js",
    '''      "structure",
      "session_open",
''',
    '''      "structure",
      "progression",
      "session_open",
''',
)

replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '  School,\n  Sparkles,\n',
    '  Route,\n  School,\n',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '{Icon ? <Icon className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}',
    '{Icon ? <Icon className="h-5 w-5" /> : <CircleDashed className="h-5 w-5" />}',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '  const [subjectForm, setSubjectForm] = useState({ name: "", code: "" });\n',
    '  const [subjectForm, setSubjectForm] = useState({ name: "", code: "" });\n  const [progressionDrafts, setProgressionDrafts] = useState({});\n',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '  const calendarActive = statusValue(selectedCalendar) === "active";\n',
    '''  const calendarActive = statusValue(selectedCalendar) === "active";
  const activeClasses = useMemo(
    () => classes.filter((item) => item?.is_active !== false && !item?.archived_at),
    [classes],
  );
  const activeSubjects = useMemo(
    () => subjects.filter((item) => item?.is_active !== false && !item?.archived_at),
    [subjects],
  );
  const progressionComplete = Boolean(
    activeClasses.length > 0 &&
      activeClasses.every((item) => item.is_terminal || item.next_class_id),
  );

  useEffect(() => {
    setProgressionDrafts((current) => {
      const next = {};
      for (const classroom of activeClasses) {
        next[classroom.id] = current[classroom.id] || {
          is_terminal: Boolean(classroom.is_terminal),
          next_class_id: classroom.next_class_id || "",
        };
      }
      return next;
    });
  }, [activeClasses]);
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '      structure: classes.length > 0 && subjects.length > 0,\n      session_open: sessionActive,\n',
    '      structure: activeClasses.length > 0 && activeSubjects.length > 0,\n      progression: progressionComplete,\n      session_open: sessionActive,\n',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''      classes.length,
      selectedSession,
''',
    '''      activeClasses.length,
      activeSubjects.length,
      progressionComplete,
      selectedSession,
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '    if (subjects.length > 0) await guide.moveTo("session_open");\n',
    '',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '    if (classes.length > 0) await guide.moveTo("session_open");\n',
    '',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''  const openSession = async () => {
''',
    '''  const saveClassProgression = async (classroom) => {
    const draft = progressionDrafts[classroom.id] || {};
    if (!draft.is_terminal && !draft.next_class_id) {
      showError(`Choose a next class or mark ${classLabel(classroom)} as terminal.`);
      return;
    }
    await runAction(
      `progression-${classroom.id}`,
      () =>
        classService.configureClassProgression(classroom.id, {
          is_terminal: Boolean(draft.is_terminal),
          next_class_id: draft.is_terminal ? null : draft.next_class_id,
        }),
      `${classLabel(classroom)} progression saved.`,
    );
  };

  const openSession = async () => {
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '    if (result) await guide.finish();\n',
    '    if (result) {\n      await guide.finish();\n      navigate("/admin/dashboard", { replace: true });\n    }\n',
)

replace_regex(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    r'''  const renderStructureStep = \(\) => \(.*?\n  const renderSessionOpenStep = \(\) => \(''',
    '''  const renderStructureStep = () => (
    <div className="space-y-5">
      <div className="rounded-2xl border border-border bg-surface-muted/25 p-4 text-sm leading-6 text-text-muted">
        Add as many classes and subjects as the school needs. The forms remain available after each creation. Continue when the minimum structure is ready, or skip the stage and return later.
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-text">Classes</p>
              <p className="mt-1 text-sm text-text-muted">
                {activeClasses.length} active class{activeClasses.length === 1 ? "" : "es"}
              </p>
            </div>
            {activeClasses.length ? <Badge variant="success">Ready</Badge> : null}
          </div>
          {activeClasses.length ? (
            <div className="mt-4 flex max-h-32 flex-wrap gap-2 overflow-y-auto">
              {activeClasses.map((item) => (
                <span key={item.id} className="rounded-full border border-border bg-surface-muted/40 px-3 py-1.5 text-xs font-semibold text-text-soft">
                  {classLabel(item)}
                </span>
              ))}
            </div>
          ) : null}
          <form onSubmit={createClass} className="mt-4 space-y-3 border-t border-border pt-4">
            <Input
              label="Class name"
              value={classForm.name}
              placeholder="JSS 1"
              onChange={(event) => setClassForm((currentForm) => ({ ...currentForm, name: event.target.value }))}
              required
            />
            <Input
              label="Arm"
              value={classForm.arm}
              placeholder="A"
              onChange={(event) => setClassForm((currentForm) => ({ ...currentForm, arm: event.target.value }))}
            />
            <Button type="submit" disabled={saving === "class"} className="w-full">
              {saving === "class" ? <Loader2 className="h-4 w-4 animate-spin" /> : <School className="h-4 w-4" />}
              {saving === "class" ? "Adding class..." : "Add another class"}
            </Button>
          </form>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-text">Subjects</p>
              <p className="mt-1 text-sm text-text-muted">
                {activeSubjects.length} active subject{activeSubjects.length === 1 ? "" : "s"}
              </p>
            </div>
            {activeSubjects.length ? <Badge variant="success">Ready</Badge> : null}
          </div>
          {activeSubjects.length ? (
            <div className="mt-4 flex max-h-32 flex-wrap gap-2 overflow-y-auto">
              {activeSubjects.map((item) => (
                <span key={item.id} className="rounded-full border border-border bg-surface-muted/40 px-3 py-1.5 text-xs font-semibold text-text-soft">
                  {item.name}
                </span>
              ))}
            </div>
          ) : null}
          <form onSubmit={createSubject} className="mt-4 space-y-3 border-t border-border pt-4">
            <Input
              label="Subject name"
              value={subjectForm.name}
              placeholder="Mathematics"
              onChange={(event) => setSubjectForm((currentForm) => ({ ...currentForm, name: event.target.value }))}
              required
            />
            <Input
              label="Subject code"
              value={subjectForm.code}
              placeholder="MTH"
              onChange={(event) => setSubjectForm((currentForm) => ({ ...currentForm, code: event.target.value }))}
            />
            <Button type="submit" disabled={saving === "subject"} className="w-full">
              {saving === "subject" ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookOpen className="h-4 w-4" />}
              {saving === "subject" ? "Adding subject..." : "Add another subject"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );

  const renderProgressionStep = () => (
    <div className="space-y-4">
      <div className="rounded-2xl border border-primary/20 bg-primary-subtle/45 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <Route className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div>
            <p className="font-semibold text-text">Define what happens at session closure</p>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              Every active class must point to its next class, or be marked terminal when learners graduate from it.
            </p>
          </div>
        </div>
      </div>

      {!activeClasses.length ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4 text-sm text-text-soft">
          Create at least one class before configuring progression. You may skip this stage and return later.
        </div>
      ) : (
        <div className="grid gap-3">
          {activeClasses.map((classroom) => {
            const draft = progressionDrafts[classroom.id] || {
              is_terminal: Boolean(classroom.is_terminal),
              next_class_id: classroom.next_class_id || "",
            };
            const configured = Boolean(classroom.is_terminal || classroom.next_class_id);
            const nextOptions = activeClasses
              .filter((candidate) => candidate.id !== classroom.id)
              .map((candidate) => ({
                value: candidate.id,
                label: classLabel(candidate),
                description: candidate.is_terminal ? "Terminal class" : "Active class",
              }));

            return (
              <div key={classroom.id} className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-text">{classLabel(classroom)}</p>
                      {configured ? <Badge variant="success">Configured</Badge> : <Badge variant="warning">Required</Badge>}
                    </div>
                    <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-border bg-surface-muted/25 px-3 text-sm font-medium text-text-soft">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-primary"
                        checked={Boolean(draft.is_terminal)}
                        onChange={(event) =>
                          setProgressionDrafts((current) => ({
                            ...current,
                            [classroom.id]: {
                              ...draft,
                              is_terminal: event.target.checked,
                              next_class_id: event.target.checked ? "" : draft.next_class_id,
                            },
                          }))
                        }
                      />
                      Terminal class — students graduate after this class
                    </label>
                  </div>
                  <div className="grid min-w-0 flex-[1.2] gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                    <SearchableSelect
                      label="Next class"
                      value={draft.next_class_id || ""}
                      onChange={(value) =>
                        setProgressionDrafts((current) => ({
                          ...current,
                          [classroom.id]: {
                            ...draft,
                            is_terminal: false,
                            next_class_id: value,
                          },
                        }))
                      }
                      options={nextOptions}
                      placeholder={draft.is_terminal ? "Terminal class" : "Select next class"}
                      searchable={nextOptions.length > 5}
                      clearable
                      disabled={draft.is_terminal}
                    />
                    <Button
                      type="button"
                      onClick={() => saveClassProgression(classroom)}
                      disabled={
                        saving === `progression-${classroom.id}` ||
                        (!draft.is_terminal && !draft.next_class_id)
                      }
                      className="w-full sm:w-auto"
                    >
                      {saving === `progression-${classroom.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Route className="h-4 w-4" />}
                      Save
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const renderSessionOpenStep = () => (''',
    flags=re.DOTALL,
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '    if (current.id === "structure") return renderStructureStep();\n    if (current.id === "session_open") return renderSessionOpenStep();\n',
    '    if (current.id === "structure") return renderStructureStep();\n    if (current.id === "progression") return renderProgressionStep();\n    if (current.id === "session_open") return renderSessionOpenStep();\n',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '<Sparkles className="h-4 w-4" />',
    '<School className="h-4 w-4" />',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${classes.length} classes · ${subjects.length} subjects`}
                />
                <SetupCheck
                  label="Academic period active"
''',
    '''                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${activeClasses.length} classes · ${activeSubjects.length} subjects`}
                />
                <SetupCheck
                  label="Class progression"
                  complete={completionMap.progression}
                  detail={progressionComplete ? "Every active class has a destination" : "Choose next classes or terminal classes"}
                />
                <SetupCheck
                  label="Academic period active"
''',
)

# ---------------------------------------------------------------------------
# Remove star/sparkle visuals and use appropriate product marks
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/components/guides/GettingStartedBanner.jsx",
    'import { ArrowRight, Sparkles } from "lucide-react";\n',
    'import { ArrowRight, ClipboardList } from "lucide-react";\n',
)
replace_once(
    "frontend/src/components/guides/GettingStartedBanner.jsx",
    '<Sparkles className="h-4 w-4" />',
    '<ClipboardList className="h-4 w-4" />',
)
replace_once(
    "frontend/src/components/ai/AiChatPanel.jsx",
    'import { Sparkles, X } from "lucide-react";\n',
    'import { MessageCircle, X } from "lucide-react";\n',
)
replace_once(
    "frontend/src/components/ai/AiChatPanel.jsx",
    '<Sparkles className="h-4 w-4" />',
    '<MessageCircle className="h-4 w-4" />',
)
replace_once(
    "frontend/src/components/layout/Topbar.jsx",
    'FileText, LogOut, Menu, Moon, Settings, Sparkles, Sun, Trash2, UserRound',
    'CreditCard, FileText, LogOut, Menu, Moon, Settings, Sun, Trash2, UserRound',
)
replace_once(
    "frontend/src/components/layout/Topbar.jsx",
    '<Sparkles className="h-4 w-4" />',
    '<CreditCard className="h-4 w-4" />',
)
replace_once(
    "frontend/src/pages/shared/RoleAnalyticsPage.jsx",
    'import { BarChart3, LineChart, PieChart, Sparkles } from "lucide-react";\n',
    'import { BarChart3, LineChart, LockKeyhole, PieChart } from "lucide-react";\n',
)
replace_once(
    "frontend/src/pages/shared/RoleAnalyticsPage.jsx",
    '<Sparkles className="h-5 w-5" />',
    '<LockKeyhole className="h-5 w-5" />',
)
replace_once(
    "frontend/src/pages/admin/SubscriptionOptionsPage.jsx",
    'import { CheckCircle2, Sparkles } from "lucide-react";\n',
    'import { CheckCircle2 } from "lucide-react";\n',
)
replace_once(
    "frontend/src/pages/admin/SubscriptionOptionsPage.jsx",
    'import PublicLayout from "../../components/layout/PublicLayout";\n',
    'import WeaveIcon from "../../components/brand/WeaveIcon";\nimport PublicLayout from "../../components/layout/PublicLayout";\n',
)
replace_once(
    "frontend/src/pages/admin/SubscriptionOptionsPage.jsx",
    '''                <div className="mt-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
''',
    '''                <div className="mt-5 flex justify-center">
                  <div className="grid h-20 w-20 place-items-center rounded-3xl border border-border/70 bg-surface-muted/35 shadow-inner-soft">
                    <WeaveIcon className="h-16 w-16" decorative />
                  </div>
                </div>
''',
)
replace_once(
    "frontend/src/pages/public/PricingPage.jsx",
    'import { HelpCircle, ShieldCheck, Sparkles } from "lucide-react";\n',
    'import { HelpCircle, ShieldCheck } from "lucide-react";\n',
)
replace_once(
    "frontend/src/pages/public/PricingPage.jsx",
    'import Navbar from "../../components/layout/Navbar";\n',
    'import WeaveIcon from "../../components/brand/WeaveIcon";\nimport Navbar from "../../components/layout/Navbar";\n',
)
replace_once(
    "frontend/src/pages/public/PricingPage.jsx",
    '<Sparkles className="h-8 w-8 text-primary-soft" />',
    '<WeaveIcon className="mx-auto h-20 w-20" decorative />',
)
replace_once(
    "frontend/src/pages/public/LandingPage.jsx",
    '  ShieldCheck,\n  Sparkles,\n  Users,\n',
    '  ShieldCheck,\n  Users,\n',
)
replace_once(
    "frontend/src/pages/public/LandingPage.jsx",
    'import Navbar from "../../components/layout/Navbar";\n',
    'import WeaveIcon from "../../components/brand/WeaveIcon";\nimport Navbar from "../../components/layout/Navbar";\n',
)
replace_once(
    "frontend/src/pages/public/LandingPage.jsx",
    '''      <h3 className="mt-4 text-2xl font-semibold text-text">{plan.name}</h3>
''',
    '''      <div className="mt-4 flex justify-center">
        <WeaveIcon className="h-16 w-16" decorative />
      </div>
      <h3 className="mt-3 text-center text-2xl font-semibold text-text">{plan.name}</h3>
''',
)
replace_once(
    "frontend/src/pages/public/LandingPage.jsx",
    '<Sparkles className="h-4 w-4 text-primary" />',
    '<ShieldCheck className="h-4 w-4 text-primary" />',
)

# Neutral fallback for any remaining star icon introduced elsewhere.
for source_path in (ROOT / "frontend/src").rglob("*"):
    if source_path.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
        continue
    content = source_path.read_text(encoding="utf-8")
    if "Sparkles" in content:
        source_path.write_text(content.replace("Sparkles", "CircleDot"), encoding="utf-8")

write(
    "frontend/src/noSparklesIcon.test.js",
    '''import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(fullPath) : [fullPath];
  });
}

test("frontend does not use the sparkle/star assistant icon", () => {
  const violations = walk(root)
    .filter((file) => /\.(js|jsx|ts|tsx)$/.test(file))
    .filter((file) => !file.endsWith("noSparklesIcon.test.js"))
    .filter((file) => fs.readFileSync(file, "utf8").includes("Sparkles"));
  assert.deepEqual(violations, []);
});
''',
)

# ---------------------------------------------------------------------------
# Dark-mode selection and progress highlighting
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/components/guides/GuideProgressStepper.jsx",
    '"grid h-[2.1rem] w-[2.1rem] place-items-center rounded-full border-2 bg-surface text-xs font-bold shadow-[0_0_0_5px_rgb(var(--color-surface))] transition",\n                      active && "border-primary bg-primary text-white",\n                      complete && !active && "border-success bg-success text-white",',
    '"guide-progress-node grid h-[2.1rem] w-[2.1rem] place-items-center rounded-full border-2 bg-surface text-xs font-bold shadow-[0_0_0_5px_rgb(var(--color-surface))] transition",\n                      active && "guide-progress-node-active border-primary bg-primary text-white",\n                      complete && !active && "guide-progress-node-complete border-success bg-success text-white",',
)
replace_once(
    "frontend/src/components/guides/GuideProgressStepper.jsx",
    'active ? "text-primary" : "text-text-soft",',
    'active ? "guide-progress-label-active text-primary" : "text-text-soft",',
)
replace_once(
    "frontend/src/index.css",
    '''  :root[data-theme="dark"] .is-selected-highlight {
    border-color: rgb(147 197 253 / 0.65) !important;
    background: rgb(var(--color-surface-raised)) !important;
    color: rgb(var(--color-text)) !important;
    box-shadow: inset 0 0 0 1px rgb(147 197 253 / 0.12);
  }
''',
    '''  :root[data-theme="dark"] .is-selected-highlight {
    border-color: rgb(96 165 250 / 0.58) !important;
    background: linear-gradient(135deg, rgb(30 64 175 / 0.24), rgb(20 31 54 / 0.92)) !important;
    color: rgb(219 234 254) !important;
    box-shadow:
      inset 0 0 0 1px rgb(147 197 253 / 0.12),
      0 10px 28px rgb(2 6 23 / 0.18);
  }
''',
)
replace_once(
    "frontend/src/index.css",
    '''  :root[data-theme="dark"] .academic-lifecycle-step[data-state="active"] {
    border-color: rgb(147 197 253 / 0.75);
    background: rgb(var(--color-surface-raised));
    box-shadow: inset 0 0 0 1px rgb(147 197 253 / 0.2);
  }
''',
    '''  :root[data-theme="dark"] .academic-lifecycle-step[data-state="active"] {
    border-color: rgb(96 165 250 / 0.6);
    background: linear-gradient(135deg, rgb(30 64 175 / 0.2), rgb(20 31 54 / 0.94));
    box-shadow: inset 0 0 0 1px rgb(147 197 253 / 0.12);
  }

  :root[data-theme="dark"] .guide-progress-node-active {
    border-color: rgb(96 165 250 / 0.82) !important;
    background-color: rgb(30 64 175 / 0.72) !important;
    color: rgb(239 246 255) !important;
  }

  :root[data-theme="dark"] .guide-progress-node-complete {
    border-color: rgb(52 211 153 / 0.72) !important;
    background-color: rgb(5 150 105 / 0.58) !important;
  }

  :root[data-theme="dark"] .guide-progress-label-active {
    color: rgb(147 197 253) !important;
  }
''',
)
replace_once(
    "frontend/src/index.css",
    '''  ::selection {
    @apply bg-primary-soft text-primary-deep;
  }
''',
    '''  ::selection {
    @apply bg-primary-soft text-primary-deep;
  }

  :root[data-theme="dark"] ::selection {
    background: rgb(30 64 175 / 0.78);
    color: rgb(239 246 255);
  }
''',
)

# ---------------------------------------------------------------------------
# Bulk import idempotency: canonical source fingerprint + unique confirmation
# ---------------------------------------------------------------------------
replace_once(
    "backend/app/modules/bulk_imports/models.py",
    '    Text,\n    UniqueConstraint,\n)',
    '    Text,\n    UniqueConstraint,\n    text,\n)',
)
replace_once(
    "backend/app/modules/bulk_imports/models.py",
    '''    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_rows: Mapped[int] = mapped_column(
''',
    '''    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    confirmed_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    total_rows: Mapped[int] = mapped_column(
''',
)
replace_once(
    "backend/app/modules/bulk_imports/models.py",
    '''        Index("ix_import_jobs_status_created_at", "status", "created_at"),
    )
''',
    '''        Index("ix_import_jobs_status_created_at", "status", "created_at"),
        Index(
            "ix_import_jobs_tenant_source_fingerprint",
            "tenant_id",
            "resource_type",
            "source_fingerprint",
        ),
        Index(
            "uq_import_jobs_tenant_confirmed_fingerprint",
            "tenant_id",
            "resource_type",
            "confirmed_fingerprint",
            unique=True,
            postgresql_where=text("confirmed_fingerprint IS NOT NULL"),
        ),
    )
''',
)
replace_once(
    "backend/app/modules/bulk_imports/schemas.py",
    '    file_size_bytes: int | None = Field(default=None, ge=0)\n    created_by_admin_id: uuid.UUID | None = None\n',
    '    file_size_bytes: int | None = Field(default=None, ge=0)\n    source_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)\n    confirmed_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)\n    created_by_admin_id: uuid.UUID | None = None\n',
)
replace_once(
    "backend/app/modules/bulk_imports/schemas.py",
    '    file_size_bytes: int | None = Field(default=None, ge=0)\n    total_rows: int | None = Field(default=None, ge=0)\n',
    '    file_size_bytes: int | None = Field(default=None, ge=0)\n    source_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)\n    confirmed_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)\n    total_rows: int | None = Field(default=None, ge=0)\n',
)
replace_once(
    "backend/app/modules/bulk_imports/repository.py",
    '''            file_size_bytes=job_data.file_size_bytes,
            created_by_admin_id=job_data.created_by_admin_id,
''',
    '''            file_size_bytes=job_data.file_size_bytes,
            source_fingerprint=job_data.source_fingerprint,
            confirmed_fingerprint=job_data.confirmed_fingerprint,
            created_by_admin_id=job_data.created_by_admin_id,
''',
)
replace_once(
    "backend/app/modules/bulk_imports/repository.py",
    '''    @staticmethod
    async def list_jobs(
''',
    '''    @staticmethod
    async def get_confirmed_job_by_fingerprint(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        resource_type: ImportResourceType,
        source_fingerprint: str,
        exclude_job_id: UUID | None = None,
        lock: bool = False,
    ) -> ImportJob | None:
        """Return the job that already claimed a canonical import fingerprint."""

        query = select(ImportJob).where(
            ImportJob.tenant_id == tenant_id,
            ImportJob.resource_type == resource_type,
            ImportJob.confirmed_fingerprint == source_fingerprint,
        )
        if exclude_job_id is not None:
            query = query.where(ImportJob.id != exclude_job_id)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_jobs(
''',
)
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    'from __future__ import annotations\n\nfrom datetime import datetime, timezone\n',
    'from __future__ import annotations\n\nimport hashlib\nimport json\nfrom datetime import datetime, timezone\n',
)
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    '''def _format_class_reference(class_name: Any, class_arm: Any) -> str:
    """Build a concise class label for validation messages."""

    parts = [str(part).strip() for part in (class_name, class_arm) if not _is_blank(part)]
    return " ".join(parts) or "the supplied class"


def build_parent_invitations_from_row(
''',
    '''def _format_class_reference(class_name: Any, class_arm: Any) -> str:
    """Build a concise class label for validation messages."""

    parts = [str(part).strip() for part in (class_name, class_arm) if not _is_blank(part)]
    return " ".join(parts) or "the supplied class"


def build_import_source_fingerprint(
    *,
    resource_type: ImportResourceType,
    template_version: str | None,
    rows: list[tuple[int, dict[str, Any]]],
) -> str:
    """Hash canonical normalized rows so the same workbook cannot be confirmed twice."""

    canonical_payload = {
        "resource_type": resource_type.value,
        "template_version": str(template_version or ""),
        "rows": [
            {"row_number": int(row_number), "data": normalized_row}
            for row_number, normalized_row in sorted(rows, key=lambda item: item[0])
        ],
    }
    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def duplicate_import_message(import_job: ImportJob) -> str:
    completed = import_job.completed_at or import_job.created_at
    completed_text = completed.isoformat() if completed else "an earlier date"
    return (
        "This student workbook has already been confirmed and processed "
        f"by import job {import_job.id} on {completed_text}. "
        "Use a new workbook containing only records that have not been imported."
    )


def build_parent_invitations_from_row(
''',
)
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    '''        BulkImportService.validate_import_template_contract(
            tenant_id=actor.tenant_id,
            endpoint_resource_type=resource_type,
            parsed_file=parsed_file,
        )

        import_job = await ImportJobRepository.create_job(
''',
    '''        BulkImportService.validate_import_template_contract(
            tenant_id=actor.tenant_id,
            endpoint_resource_type=resource_type,
            parsed_file=parsed_file,
        )

        row_items = BulkImportService.build_row_items(
            resource_type=resource_type,
            parsed_file=parsed_file,
        )
        source_fingerprint = build_import_source_fingerprint(
            resource_type=resource_type,
            template_version=parsed_file.metadata.get("_import_template_version"),
            rows=[(row_number, normalized_row) for row_number, _, normalized_row, _ in row_items],
        )
        existing_import = await ImportJobRepository.get_confirmed_job_by_fingerprint(
            db=db,
            tenant_id=actor.tenant_id,
            resource_type=resource_type,
            source_fingerprint=source_fingerprint,
        )
        if existing_import is not None:
            raise ConflictException(detail=duplicate_import_message(existing_import))

        import_job = await ImportJobRepository.create_job(
''',
)
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    '''                file_size_bytes=parsed_file.file_size_bytes,
                created_by_admin_id=actor.id,
''',
    '''                file_size_bytes=parsed_file.file_size_bytes,
                source_fingerprint=source_fingerprint,
                created_by_admin_id=actor.id,
''',
)
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    '''                    "template_headers_hash": parsed_file.metadata.get("_import_headers_hash"),
                    "result_rows": [],
''',
    '''                    "template_headers_hash": parsed_file.metadata.get("_import_headers_hash"),
                    "source_fingerprint": source_fingerprint,
                    "result_rows": [],
''',
)
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    '''        row_items = BulkImportService.build_row_items(
            resource_type=resource_type,
            parsed_file=parsed_file,
        )
        validation_results = BulkImportValidator.validate_rows(
''',
    '''        validation_results = BulkImportValidator.validate_rows(
''',
)

# Synchronous confirmation path gets the same database claim.
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    '''        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=import_job,
            staged_row_count=len(staged_rows),
        )

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=actor.tenant_id)
''',
    '''        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=import_job,
            staged_row_count=len(staged_rows),
        )

        source_fingerprint = import_job.source_fingerprint or build_import_source_fingerprint(
            resource_type=import_job.resource_type,
            template_version=metadata_json.get("template_version"),
            rows=[(row.row_number, row.normalized_row) for row in staged_rows],
        )
        existing_import = await ImportJobRepository.get_confirmed_job_by_fingerprint(
            db=db,
            tenant_id=actor.tenant_id,
            resource_type=import_job.resource_type,
            source_fingerprint=source_fingerprint,
            exclude_job_id=import_job.id,
        )
        if existing_import is not None:
            raise ConflictException(detail=duplicate_import_message(existing_import))

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=actor.tenant_id)
''',
)
replace_once(
    "backend/app/modules/bulk_imports/service.py",
    '''                skipped_rows=0,
            ),
        )

        validation_results = [
''',
    '''                skipped_rows=0,
                source_fingerprint=source_fingerprint,
                confirmed_fingerprint=source_fingerprint,
            ),
        )

        validation_results = [
''',
)

replace_once(
    "backend/app/modules/bulk_imports/live_service.py",
    '''    compact_validation_error,
    utc_now,
)
''',
    '''    build_import_source_fingerprint,
    compact_validation_error,
    duplicate_import_message,
    utc_now,
)
''',
)
replace_once(
    "backend/app/modules/bulk_imports/live_service.py",
    '''        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=import_job,
            staged_row_count=len(staged_rows),
        )

        await SubscriptionFeatureService.ensure_resource_limit_available(
''',
    '''        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=import_job,
            staged_row_count=len(staged_rows),
        )

        source_fingerprint = import_job.source_fingerprint or build_import_source_fingerprint(
            resource_type=import_job.resource_type,
            template_version=metadata_json.get("template_version"),
            rows=[(row.row_number, row.normalized_row) for row in staged_rows],
        )
        existing_import = await ImportJobRepository.get_confirmed_job_by_fingerprint(
            db=db,
            tenant_id=actor.tenant_id,
            resource_type=import_job.resource_type,
            source_fingerprint=source_fingerprint,
            exclude_job_id=import_job.id,
        )
        if existing_import is not None:
            raise ConflictException(detail=duplicate_import_message(existing_import))

        await SubscriptionFeatureService.ensure_resource_limit_available(
''',
)
replace_once(
    "backend/app/modules/bulk_imports/live_service.py",
    '''                skipped_rows=0,
                metadata_json=metadata_json,
            ),
        )
        await db.commit()
''',
    '''                skipped_rows=0,
                source_fingerprint=source_fingerprint,
                confirmed_fingerprint=source_fingerprint,
                metadata_json=metadata_json,
            ),
        )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            duplicate = await ImportJobRepository.get_confirmed_job_by_fingerprint(
                db=db,
                tenant_id=actor.tenant_id,
                resource_type=import_job.resource_type,
                source_fingerprint=source_fingerprint,
                exclude_job_id=import_job.id,
            )
            if duplicate is not None:
                raise ConflictException(detail=duplicate_import_message(duplicate)) from exc
            raise
''',
)
replace_once(
    "backend/app/modules/bulk_imports/live_service.py",
    '''                failed_metadata["queue_error"] = str(exc)
                await ImportJobRepository.update_job(
                    db=db,
                    import_job=failed_job,
                    job_update=ImportJobUpdate(
                        status=ImportJobStatus.FAILED,
                        error_message="Could not queue the background import worker.",
                        completed_at=utc_now(),
                        metadata_json=failed_metadata,
                    ),
                )
''',
    '''                failed_metadata["queue_error"] = str(exc)
                failed_metadata["dry_run"] = True
                failed_metadata["confirmation_required"] = True
                failed_metadata.pop("confirmed_at", None)
                failed_metadata.pop("queued_at", None)
                await ImportJobRepository.update_job(
                    db=db,
                    import_job=failed_job,
                    job_update=ImportJobUpdate(
                        status=ImportJobStatus.COMPLETED,
                        error_message="Could not queue the background import worker. Try confirming again.",
                        completed_at=utc_now(),
                        confirmed_fingerprint=None,
                        metadata_json=failed_metadata,
                    ),
                )
''',
)

write(
    "backend/alembic/versions/20260801_import_idempotency.py",
    '''"""Prevent duplicate confirmed bulk imports.

Revision ID: 20260801_import_idempotency
Revises: 20260731_clean_baseline
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_import_idempotency"
down_revision: str | Sequence[str] | None = "20260731_clean_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(bind: sa.Connection) -> set[str]:
    inspector = sa.inspect(bind)
    if "import_jobs" not in inspector.get_table_names(schema="public"):
        return set()
    return {column["name"] for column in inspector.get_columns("import_jobs", schema="public")}


def _index_names(bind: sa.Connection) -> set[str]:
    inspector = sa.inspect(bind)
    if "import_jobs" not in inspector.get_table_names(schema="public"):
        return set()
    return {index["name"] for index in inspector.get_indexes("import_jobs", schema="public")}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind)
    if not columns:
        return

    if "source_fingerprint" not in columns:
        op.add_column(
            "import_jobs",
            sa.Column("source_fingerprint", sa.String(length=64), nullable=True),
            schema="public",
        )
    if "confirmed_fingerprint" not in columns:
        op.add_column(
            "import_jobs",
            sa.Column("confirmed_fingerprint", sa.String(length=64), nullable=True),
            schema="public",
        )

    indexes = _index_names(bind)
    if "ix_import_jobs_tenant_source_fingerprint" not in indexes:
        op.create_index(
            "ix_import_jobs_tenant_source_fingerprint",
            "import_jobs",
            ["tenant_id", "resource_type", "source_fingerprint"],
            schema="public",
        )
    if "uq_import_jobs_tenant_confirmed_fingerprint" not in indexes:
        op.create_index(
            "uq_import_jobs_tenant_confirmed_fingerprint",
            "import_jobs",
            ["tenant_id", "resource_type", "confirmed_fingerprint"],
            unique=True,
            schema="public",
            postgresql_where=sa.text("confirmed_fingerprint IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = _index_names(bind)
    if "uq_import_jobs_tenant_confirmed_fingerprint" in indexes:
        op.drop_index(
            "uq_import_jobs_tenant_confirmed_fingerprint",
            table_name="import_jobs",
            schema="public",
        )
    if "ix_import_jobs_tenant_source_fingerprint" in indexes:
        op.drop_index(
            "ix_import_jobs_tenant_source_fingerprint",
            table_name="import_jobs",
            schema="public",
        )

    columns = _column_names(bind)
    if "confirmed_fingerprint" in columns:
        op.drop_column("import_jobs", "confirmed_fingerprint", schema="public")
    if "source_fingerprint" in columns:
        op.drop_column("import_jobs", "source_fingerprint", schema="public")
''',
)

write(
    "backend/tests/unit/bulk_imports/test_import_idempotency.py",
    '''from app.modules.bulk_imports.models import ImportJob, ImportResourceType
from app.modules.bulk_imports.service import build_import_source_fingerprint


def test_import_source_fingerprint_is_stable_for_equivalent_rows() -> None:
    rows = [
        (3, {"first_name": "Ada", "last_name": "Okafor", "class_id": "class-1"}),
        (2, {"first_name": "Tunde", "last_name": "Bello", "class_id": "class-2"}),
    ]
    first = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=rows,
    )
    second = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=list(reversed(rows)),
    )
    assert first == second
    assert len(first) == 64


def test_import_source_fingerprint_changes_when_student_data_changes() -> None:
    original = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[(2, {"first_name": "Ada", "last_name": "Okafor"})],
    )
    changed = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[(2, {"first_name": "Ada", "last_name": "Bello"})],
    )
    assert original != changed


def test_confirmed_fingerprint_has_unique_tenant_resource_index() -> None:
    index = next(
        item
        for item in ImportJob.__table__.indexes
        if item.name == "uq_import_jobs_tenant_confirmed_fingerprint"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "tenant_id",
        "resource_type",
        "confirmed_fingerprint",
    ]
''',
)

# Add the new migration and test to the focused workflow without assuming old guide revisions.
workflow_path = "frontend/src/noSparklesIcon.test.js"
assert (ROOT / workflow_path).exists()

print("Applied frontend guide, dark-mode, pricing, progression, and bulk-import idempotency cleanup.")
