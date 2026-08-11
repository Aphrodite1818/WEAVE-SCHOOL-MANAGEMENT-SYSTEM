import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  CreditCard,
  GraduationCap,
  ImageIcon,
  Loader2,
  RefreshCw,
  Route,
  School,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import GuideProgressStepper from "../../components/guides/GuideProgressStepper";
import DashboardLayout from "../../components/layout/DashboardLayout";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { useTenantBranding } from "../../features/tenant-branding/useTenantBranding";
import { schoolCalendarService } from "../../features/schoolCalendar/api/schoolCalendarService";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import useRoleGuide from "../../features/guides/useRoleGuide";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { academicLevelService, classService } from "../../services/academicsService";
import { authSession, getErrorMessage, parseApiError } from "../../services/api";
import { mediaService } from "../../services/mediaService";
import { tenantBrandingService } from "../../services/tenantBrandingService";
import { subjectService } from "../../services/subject.service";
import { subscriptionService } from "../../services/subscriptionService";

const ACCEPTED_LOGO_TYPES = ["image/jpeg", "image/png", "image/webp"];

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const isoDate = (date = new Date()) => date.toISOString().slice(0, 10);
const addMonths = (date, months) => {
  const next = new Date(date);
  next.setMonth(next.getMonth() + months);
  return isoDate(next);
};
const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
const statusValue = (item) => String(item?.status || "").toLowerCase();
const sessionLabel = (item) => item?.name || "Academic session";
const termLabel = (item) => titleCase(item?.display_name || item?.name || "Term");
const classLabel = (item) =>
  [item?.academic_level_name, item?.arm].filter(Boolean).join(" ") || "Class";
const schoolLogoFromUser = (user) =>
  user?.tenant_logo_url || user?.tenant?.logo_url || "";
const uploadedLogoUrl = (response) =>
  response?.render_url ||
  response?.media_asset?.cdn_url ||
  response?.media_asset?.public_url ||
  "";

const today = new Date();
const DEFAULT_SESSION = {
  name: `${today.getFullYear()}/${today.getFullYear() + 1}`,
  start_date: isoDate(today),
  end_date: addMonths(today, 11),
};
const DEFAULT_TERM = {
  name: "first_term",
  start_date: isoDate(today),
  end_date: addMonths(today, 4),
};
const DEFAULT_CALENDAR = {
  timezone: "Africa/Lagos",
  default_open_time: "08:00",
  default_close_time: "15:00",
};

function SetupCheck({ label, complete, detail }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-surface px-3 py-3">
      <span
        className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full ${
          complete
            ? "bg-success text-white"
            : "border border-border bg-surface-muted text-text-faint"
        }`}
      >
        {complete ? <Check className="h-3.5 w-3.5" /> : <CircleDashed className="h-3.5 w-3.5" />}
      </span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-text">{label}</p>
        {detail ? <p className="mt-0.5 text-xs leading-5 text-text-muted">{detail}</p> : null}
      </div>
    </div>
  );
}

function StepHeading({ step, number, total, complete }) {
  const Icon = step.icon;
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
        {Icon ? <Icon className="h-5 w-5" /> : <CircleDashed className="h-5 w-5" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
            Step {number} of {total}
          </p>
          {complete ? <Badge variant="success">Complete</Badge> : null}
        </div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text sm:text-2xl">
          {step.label}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-7 text-text-muted">
          {step.description}
        </p>
      </div>
    </div>
  );
}

function AdminGettingStartedPage() {
  const navigate = useNavigate();
  const { showSuccess, showError, showWarning } = useToast();
  const { refreshSubscriptionState } = useSubscription();
  const { applyResponse: applyBrandingResponse } = useTenantBranding();
  const logoInputRef = useRef(null);
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [calendars, setCalendars] = useState([]);
  const [levels, setLevels] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [calendarConfiguration, setCalendarConfiguration] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedTermId, setSelectedTermId] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [sessionForm, setSessionForm] = useState(DEFAULT_SESSION);
  const [termForm, setTermForm] = useState(DEFAULT_TERM);
  const [calendarForm, setCalendarForm] = useState(DEFAULT_CALENDAR);
  const [levelForm, setLevelForm] = useState({ name: "" });
  const [classForm, setClassForm] = useState({ academic_level_id: "", arm: "" });
  const [subjectForm, setSubjectForm] = useState({ name: "", code: "" });
  const [progressionDrafts, setProgressionDrafts] = useState({});
  const [schoolLogoUrl, setSchoolLogoUrl] = useState(() =>
    schoolLogoFromUser(authSession.getUser()),
  );
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState("");
  const [logoError, setLogoError] = useState("");
  const [structureLimitNotice, setStructureLimitNotice] = useState(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState(null);
  const [warningDialog, setWarningDialog] = useState(null);

  useEffect(() => () => {
    if (logoPreview) URL.revokeObjectURL(logoPreview);
  }, [logoPreview]);

  const loadSetup = useCallback(async ({ quiet = false } = {}) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const [
        sessionResponse,
        termResponse,
        calendarResponse,
        levelResponse,
        classResponse,
        subjectResponse,
        configurationResponse,
      ] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        schoolCalendarService.listAdminCalendars({ limit: 100 }),
        academicLevelService.getLevels({ limit: 500, activeOnly: false }),
        classService.getClasses({ limit: 500, activeOnly: false }),
        subjectService.getSubjects({ limit: 500, includeArchived: false }),
        schoolCalendarService.getConfiguration().catch((requestError) => {
          if (requestError?.response?.status === 404) return null;
          throw requestError;
        }),
      ]);

      const sessionItems = asItems(sessionResponse);
      const termItems = asItems(termResponse);
      const calendarItems = asItems(calendarResponse);
      const levelItems = asItems(levelResponse);
      const classItems = asItems(classResponse);
      const subjectItems = asItems(subjectResponse);
      const preferredSession =
        sessionItems.find((item) => item.is_current) ||
        sessionItems.find((item) => statusValue(item) === "open") ||
        sessionItems.find((item) => statusValue(item) === "draft") ||
        sessionItems[0] ||
        null;
      const preferredTerms = termItems.filter(
        (item) => !preferredSession || item.academic_session_id === preferredSession.id,
      );
      const preferredTerm =
        preferredTerms.find((item) => item.is_current) ||
        preferredTerms.find((item) => statusValue(item) === "open") ||
        preferredTerms.find((item) => statusValue(item) === "draft") ||
        preferredTerms[0] ||
        null;

      setSessions(sessionItems);
      setTerms(termItems);
      setCalendars(calendarItems);
      setLevels(levelItems);
      setClasses(classItems);
      setSubjects(subjectItems);
      setCalendarConfiguration(configurationResponse);
      setSelectedSessionId((current) =>
        sessionItems.some((item) => item.id === current)
          ? current
          : preferredSession?.id || "",
      );
      setSelectedTermId((current) =>
        termItems.some((item) => item.id === current)
          ? current
          : preferredTerm?.id || "",
      );
      if (configurationResponse) {
        setCalendarForm({
          timezone: configurationResponse.timezone || DEFAULT_CALENDAR.timezone,
          default_open_time:
            configurationResponse.default_open_time || DEFAULT_CALENDAR.default_open_time,
          default_close_time:
            configurationResponse.default_close_time || DEFAULT_CALENDAR.default_close_time,
        });
      }
    } catch (requestError) {
      const message = getErrorMessage(requestError, "Could not load the school setup state.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showError]);

  useEffect(() => {
    loadSetup();
  }, [loadSetup]);

  const selectedSession = useMemo(
    () => sessions.find((item) => item.id === selectedSessionId) || null,
    [selectedSessionId, sessions],
  );
  const termsForSession = useMemo(
    () =>
      terms.filter(
        (item) => !selectedSessionId || item.academic_session_id === selectedSessionId,
      ),
    [selectedSessionId, terms],
  );
  const selectedTerm = useMemo(
    () =>
      termsForSession.find((item) => item.id === selectedTermId) ||
      termsForSession.find((item) => item.is_current) ||
      termsForSession[0] ||
      null,
    [selectedTermId, termsForSession],
  );
  const calendarsForTerm = useMemo(
    () =>
      calendars.filter(
        (item) => !selectedTerm?.id || item.academic_term_id === selectedTerm.id,
      ),
    [calendars, selectedTerm],
  );
  const selectedCalendar = useMemo(
    () =>
      calendarsForTerm.find((item) => statusValue(item) === "active") ||
      calendarsForTerm[0] ||
      null,
    [calendarsForTerm],
  );

  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedTermId("");
      return;
    }
    if (selectedTerm?.id) setSelectedTermId(selectedTerm.id);
  }, [selectedSessionId, selectedTerm?.id]);

  const sessionActive = Boolean(
    selectedSession &&
      statusValue(selectedSession) === "open" &&
      selectedSession.is_current,
  );
  const termActive = Boolean(
    selectedTerm && statusValue(selectedTerm) === "open" && selectedTerm.is_current,
  );
  const calendarActive = statusValue(selectedCalendar) === "active";
  const activeClasses = useMemo(
    () => classes.filter((item) => item?.is_active !== false && !item?.archived_at),
    [classes],
  );
  const activeLevels = useMemo(
    () => levels.filter((item) => item?.is_active !== false && !item?.archived_at),
    [levels],
  );
  const activeSubjects = useMemo(
    () => subjects.filter((item) => item?.is_active !== false && !item?.archived_at),
    [subjects],
  );
  const progressionComplete = Boolean(
    activeLevels.length > 0 &&
      activeLevels.every((item) => item.is_terminal || item.next_level_id),
  );

  useEffect(() => {
    setProgressionDrafts((current) => {
      const next = {};
      for (const level of activeLevels) {
        next[level.id] = current[level.id] || {
          is_terminal: Boolean(level.is_terminal),
          next_level_id: level.next_level_id || "",
        };
      }
      return next;
    });
  }, [activeLevels]);

  useEffect(() => {
    setClassForm((current) => {
      if (activeLevels.some((level) => level.id === current.academic_level_id)) {
        return current;
      }
      return { ...current, academic_level_id: activeLevels[0]?.id || "" };
    });
  }, [activeLevels]);
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
      school_logo: Boolean(schoolLogoUrl),
      session: Boolean(selectedSession),
      term: Boolean(selectedSession && selectedTerm),
      calendar: calendarPrepared,
      structure: activeClasses.length > 0 && activeSubjects.length > 0,
      progression: progressionComplete,
      session_open: sessionActive,
      calendar_active: calendarActive,
      term_open: termActive,
    }),
    [
      calendarActive,
      calendarPrepared,
      activeClasses.length,
      activeSubjects.length,
      progressionComplete,
      schoolLogoUrl,
      selectedSession,
      selectedTerm,
      sessionActive,
      termActive,
    ],
  );
  const guide = useRoleGuide({
    role: "admin",
    completionMap,
    allowCompletedCurrentStep: true,
    allowSkippedCurrentStep: true,
  });
  const guideLoading = guide.loading;
  const guideState = guide.guideState;
  const startGuide = guide.start;
  const moveGuideTo = guide.moveTo;

  useEffect(() => {
    if (!guideLoading && guideState?.status === "not_started") {
      startGuide();
    }
  }, [guideLoading, guideState?.status, startGuide]);

  useEffect(() => {
    if (guideLoading || !guideState || schoolLogoUrl) return;
    if (guideState.status !== "in_progress") return;
    if (guideState.current_step === "school_logo") return;
    if ((guideState.skipped_steps || []).includes("school_logo")) return;
    moveGuideTo("school_logo");
  }, [guideLoading, guideState, moveGuideTo, schoolLogoUrl]);

  const persistSchoolLogo = (logoUrl) => {
    const currentUser = authSession.getUser() || {};
    const nextUser = {
      ...currentUser,
      tenant_logo_url: logoUrl || null,
      tenant: {
        ...(currentUser.tenant || {}),
        logo_url: logoUrl || null,
      },
    };
    authSession.setUser(nextUser, {
      remember: authSession.getRememberPreference(),
    });
    setSchoolLogoUrl(logoUrl || "");
  };

  const refreshWorkspaceBranding = async () => {
    try {
      const response = await tenantBrandingService.getEffective();
      applyBrandingResponse(response);
    } catch {
      // The local upload state is enough for this step; branding will refresh on reload.
    }
  };

  const chooseLogoFile = (file) => {
    if (!ACCEPTED_LOGO_TYPES.includes(file.type)) {
      setLogoError("Choose a PNG, JPG, or WebP image.");
      return;
    }
    if (file.size > 1024 * 1024) {
      setLogoError("The school logo must be smaller than 1 MB.");
      return;
    }
    if (logoPreview) URL.revokeObjectURL(logoPreview);
    setLogoFile(file);
    setLogoPreview(URL.createObjectURL(file));
    setLogoError("");
  };

  const uploadSchoolLogo = async () => {
    if (!logoFile) return;
    setSaving("school-logo");
    setError("");
    setLogoError("");
    try {
      const response = await mediaService.uploadSchoolLogo(logoFile);
      const nextLogoUrl = uploadedLogoUrl(response);
      persistSchoolLogo(nextLogoUrl);
      setLogoFile(null);
      if (logoPreview) URL.revokeObjectURL(logoPreview);
      setLogoPreview("");
      await refreshWorkspaceBranding();
      showSuccess("School logo uploaded.");
    } catch (uploadError) {
      const parsed = parseApiError(uploadError, "The school logo could not be uploaded.");
      setLogoError(parsed.message);
      showError(parsed.message);
    } finally {
      setSaving("");
    }
  };

  const removeSchoolLogo = async () => {
    setSaving("school-logo-remove");
    setError("");
    setLogoError("");
    try {
      await mediaService.deleteSchoolLogo();
      persistSchoolLogo("");
      setLogoFile(null);
      if (logoPreview) URL.revokeObjectURL(logoPreview);
      setLogoPreview("");
      await refreshWorkspaceBranding();
      showSuccess("School logo removed.");
    } catch (removeError) {
      const parsed = parseApiError(removeError, "The school logo could not be removed.");
      setLogoError(parsed.message);
      showError(parsed.message);
    } finally {
      setSaving("");
    }
  };

  const runAction = async (key, action, successMessage) => {
    setSaving(key);
    setError("");
    setStructureLimitNotice(null);
    try {
      const result = await action();
      if (successMessage) showSuccess(successMessage);
      await loadSetup({ quiet: true });
      return result;
    } catch (requestError) {
      const parsed = parseApiError(requestError, "Setup action failed.");
      const detail = parsed.data?.detail || {};
      if (detail?.reason === "resource_limit_reached") {
        const resourceLabel = String(detail.resource || "resource").replaceAll("_", " ");
        const notice = {
          resource: resourceLabel,
          used: detail.used,
          limit: detail.limit,
          message:
            parsed.message ||
            `Your current plan has reached its ${resourceLabel} limit.`,
        };
        setStructureLimitNotice(notice);
        setWarningDialog({
          title: "Plan limit reached",
          message: notice.message,
          detail:
            notice.limit !== null && notice.limit !== undefined
              ? `${notice.used} of ${notice.limit} ${notice.resource}`
              : "",
          actionLabel: "Upgrade plan",
          onAction: goToPlanUpgrade,
        });
        return null;
      }

      const message = getErrorMessage(requestError, "Setup action failed.");
      setError(message);
      showError(message);
      return null;
    } finally {
      setSaving("");
    }
  };

  const createSession = async (event) => {
    event.preventDefault();
    const created = await runAction(
      "session",
      () => academicService.createSession(sessionForm),
      "Academic session created.",
    );
    if (!created?.id) return;
    setSelectedSessionId(created.id);
    await guide.moveTo("term");
  };

  const createTerm = async (event) => {
    event.preventDefault();
    if (!selectedSessionId) {
      showWarning("Create or select an academic session first.");
      return;
    }
    const created = await runAction(
      "term",
      () =>
        academicService.createTerm({
          ...termForm,
          academic_session_id: selectedSessionId,
        }),
      "Academic term created.",
    );
    if (!created?.id) return;
    setSelectedTermId(created.id);
    await guide.moveTo("calendar");
  };

  const generateCalendar = async (event) => {
    event.preventDefault();
    if (!selectedSessionId || !selectedTerm?.id) {
      showWarning("Create and select a session and term before generating the calendar.");
      return;
    }
    const result = await runAction(
      "calendar",
      async () => {
        await schoolCalendarService.updateConfiguration({
          timezone: calendarForm.timezone,
          instructional_weekdays: [0, 1, 2, 3, 4],
          default_open_time: calendarForm.default_open_time,
          default_close_time: calendarForm.default_close_time,
          default_student_attendance_required: true,
          default_workforce_attendance_required: true,
        });
        return schoolCalendarService.generateCalendar({
          academic_session_id: selectedSessionId,
          academic_term_id: selectedTerm.id,
          overwrite_generated_days: Boolean(selectedCalendar),
        });
      },
      "School calendar generated.",
    );
    if (result) await guide.moveTo("structure");
  };

  const createLevel = async (event) => {
    event.preventDefault();
    const created = await runAction(
      "level",
      () => academicLevelService.createLevel({ name: levelForm.name }),
      "Academic level created. Now add its class arm.",
    );
    if (!created?.id) return;
    setLevelForm({ name: "" });
    setClassForm((current) => ({ ...current, academic_level_id: created.id }));
  };

  const createClass = async (event) => {
    event.preventDefault();
    if (!classForm.academic_level_id) {
      showWarning("Create or select an academic level before adding an arm.");
      return;
    }
    const created = await runAction(
      "class",
      () => classService.createClass(classForm),
      "Class created.",
    );
    if (!created) return;
    setClassForm((current) => ({ ...current, arm: "" }));
  };

  const createSubject = async (event) => {
    event.preventDefault();
    const created = await runAction(
      "subject",
      () => subjectService.createSubject({ ...subjectForm, description: "" }),
      "Subject created.",
    );
    if (!created) return;
    setSubjectForm({ name: "", code: "" });
  };

  const removeClass = async (classroom, label = classLabel(classroom)) => {
    const removed = await runAction(
      `class-delete-${classroom.id}`,
      () => classService.removeClassFromSetup(classroom.id),
      `${label} removed from setup.`,
    );
    if (removed) await refreshSubscriptionState({ silent: true });
  };

  const removeLevel = async (level, label = level?.name || "Academic level") => {
    await runAction(
      `level-delete-${level.id}`,
      () => academicLevelService.removeLevelFromSetup(level.id),
      `${label} removed from setup.`,
    );
  };

  const removeSubject = async (subject, label = subject?.name || "Subject") => {
    const removed = await runAction(
      `subject-delete-${subject.id}`,
      () => subjectService.removeSubjectFromSetup(subject.id),
      `${label} removed from setup.`,
    );
    if (removed) await refreshSubscriptionState({ silent: true });
  };

  const requestSetupRemoval = (type, item) => {
    const label = type === "class"
      ? classLabel(item)
      : item?.name || (type === "level" ? "Academic level" : "Subject");
    setDeleteConfirmation({ type, item, label });
  };

  const confirmSetupRemoval = async () => {
    if (!deleteConfirmation) return;

    const { type, item, label } = deleteConfirmation;
    if (type === "class") {
      await removeClass(item, label);
    } else if (type === "level") {
      await removeLevel(item, label);
    } else {
      await removeSubject(item, label);
    }
    setDeleteConfirmation(null);
  };

  const saveLevelProgression = async (level) => {
    const draft = progressionDrafts[level.id] || {};
    if (!draft.is_terminal && !draft.next_level_id) {
      showWarning(`Choose a next level or mark ${level.name} as terminal.`);
      return;
    }
    await runAction(
      `progression-${level.id}`,
      () =>
        academicLevelService.configureProgression(level.id, {
          is_terminal: Boolean(draft.is_terminal),
          next_level_id: draft.is_terminal ? null : draft.next_level_id,
        }),
      `${level.name} progression saved.`,
    );
  };

  const openSession = async () => {
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
    setSaving("open-term");
    setError("");
    try {
      await academicService.openTerm(selectedTerm.id);
      showSuccess("Academic term opened.");
      await guide.finish();
      navigate("/admin/dashboard", { replace: true });
    } catch (requestError) {
      const parsed = parseApiError(requestError, "Could not open the academic term.");
      const activation = parsed.data?.code === "TERM_PLAN_ACTIVATION_REQUIRED"
        ? parsed.data
        : parsed.data?.detail?.code === "TERM_PLAN_ACTIVATION_REQUIRED"
          ? parsed.data.detail
          : null;

      if (!activation) {
        setError(parsed.message);
        showError(parsed.message);
        return;
      }

      try {
        if (!activation.suggested_plan) {
          navigate(`/admin/billing/plans?term=${encodeURIComponent(selectedTerm.id)}`);
          return;
        }

        if (activation.payment_required) {
          const checkout = await subscriptionService.initializeTermCheckout({
            academic_term_id: selectedTerm.id,
            plan_code: activation.suggested_plan,
          });
          window.location.assign(checkout.authorization_url);
          return;
        }

        if (activation.suggested_plan === "free") {
          await subscriptionService.activateFreeTerm(selectedTerm.id);
          await academicService.openTerm(selectedTerm.id);
          showSuccess("Free plan activated and academic term opened.");
          await guide.finish();
          navigate("/admin/dashboard", { replace: true });
          return;
        }

        navigate(`/admin/billing/plans?term=${encodeURIComponent(selectedTerm.id)}`);
      } catch (activationError) {
        const message = getErrorMessage(
          activationError,
          "Could not prepare the selected plan for this academic term.",
        );
        setError(message);
        showError(message);
      }
    } finally {
      setSaving("");
    }
  };

  if (loading || guide.loading || !guide.config || !guide.currentStep) {
    return (
      <DashboardLayout role="admin" title="School setup">
        <LoadingState label="Preparing your school setup..." />
      </DashboardLayout>
    );
  }

  const current = guide.currentStep;
  const currentComplete = Boolean(completionMap[current.id]);
  const firstStep = guide.currentIndex === 0;
  const lastStep = guide.currentIndex >= guide.steps.length - 1;
  const setupReadyToComplete =
    guide.steps.length > 0 &&
    guide.steps.every((step) => step.complete || step.skipped);
  const sessionOptions = sessions.map((item) => ({
    value: item.id,
    label: sessionLabel(item),
    description: `${titleCase(item.status)}${item.is_current ? " · Current" : ""}`,
  }));
  const termOptions = termsForSession.map((item) => ({
    value: item.id,
    label: termLabel(item),
    description: `${titleCase(item.status)}${item.is_current ? " · Current" : ""}`,
  }));

  const levelOptions = activeLevels.map((item) => {
    const armCount = activeClasses.filter(
      (classroom) => classroom.academic_level_id === item.id,
    ).length;
    return {
      value: item.id,
      label: item.name,
      description: `${armCount} class arm${armCount === 1 ? "" : "s"}`,
    };
  });

  const goPrevious = () => {
    if (!firstStep) guide.moveTo(guide.steps[guide.currentIndex - 1].id);
  };
  const goToPlanUpgrade = () => {
    setWarningDialog(null);
    navigate("/admin/billing/plans");
  };
  const continueStep = async () => {
    if (guide.guideState?.status === "completed") {
      navigate("/admin/dashboard", { replace: true });
      return;
    }
    if (lastStep || setupReadyToComplete) {
      if (!currentComplete && !setupReadyToComplete) return;
      try {
        await guide.finish();
        showSuccess("Assisted setup completed.");
        navigate("/admin/dashboard", { replace: true });
      } catch (completionError) {
        showError(getErrorMessage(completionError, "Could not complete assisted setup."));
      }
      return;
    }
    await guide.advanceFrom(current.id);
  };
  const skipStep = async () => {
    await guide.skipStep(current.id);
    if (lastStep) navigate("/admin/dashboard", { replace: true });
  };

  const renderLogoStep = () => (
    <div className="space-y-5">
      <div className="rounded-2xl border border-border bg-surface-muted/25 p-4 text-sm leading-6 text-text-muted">
        Upload the school logo once so it appears consistently in the workspace, student slips,
        invitations, report cards, and printable records. PNG with a transparent background works best.
      </div>

      {logoError ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {logoError}
        </div>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(18rem,0.65fr)]">
        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <div
            className="flex min-h-52 flex-col items-center justify-center rounded-2xl border border-dashed border-primary/55 bg-surface-muted/25 px-5 text-center transition hover:bg-primary-soft/20"
            onDragEnter={(event) => event.preventDefault()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const file = event.dataTransfer.files?.[0];
              if (file) chooseLogoFile(file);
            }}
          >
            <span className="grid h-12 w-12 place-items-center rounded-full bg-primary-soft text-primary">
              <UploadCloud className="h-6 w-6" />
            </span>
            <p className="mt-4 text-sm font-semibold text-text">
              Drop the school logo here
            </p>
            <p className="mt-1 text-xs text-text-muted">
              PNG, JPG, or WebP - Max 1 MB
            </p>
            <input
              ref={logoInputRef}
              className="sr-only"
              type="file"
              accept={ACCEPTED_LOGO_TYPES.join(",")}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) chooseLogoFile(file);
                event.target.value = "";
              }}
            />
            <Button
              type="button"
              variant="outline"
              className="mt-4 bg-surface"
              disabled={saving === "school-logo" || saving === "school-logo-remove"}
              onClick={() => logoInputRef.current?.click()}
            >
              Choose image
            </Button>
          </div>

          {logoFile ? (
            <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="truncate text-sm font-medium text-text-soft">
                {logoFile.name}
              </p>
              <Button
                type="button"
                className="w-full sm:w-auto"
                disabled={saving === "school-logo"}
                onClick={uploadSchoolLogo}
              >
                {saving === "school-logo" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <UploadCloud className="h-4 w-4" />
                )}
                {saving === "school-logo" ? "Uploading..." : "Upload logo"}
              </Button>
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <p className="text-sm font-semibold text-text">Logo preview</p>
          <div className="mt-4 flex min-h-44 items-center justify-center rounded-2xl border border-border bg-surface-muted/30 p-5">
            {logoPreview || schoolLogoUrl ? (
              <img
                src={logoPreview || schoolLogoUrl}
                alt="School logo preview"
                className="max-h-32 max-w-full object-contain"
              />
            ) : (
              <div className="text-center text-text-faint">
                <ImageIcon className="mx-auto h-10 w-10" />
                <p className="mt-2 text-sm">No logo uploaded yet</p>
              </div>
            )}
          </div>
          {schoolLogoUrl ? (
            <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-text">School logo uploaded</p>
                <p className="text-xs text-text-muted">Ready across school-facing records</p>
              </div>
              <Button
                type="button"
                variant="ghost"
                className="justify-start text-error hover:bg-error-soft hover:text-error sm:justify-center"
                disabled={saving === "school-logo-remove"}
                onClick={removeSchoolLogo}
              >
                {saving === "school-logo-remove" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
                Remove
              </Button>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-text-muted">
              You can skip this step if the school does not have a logo ready yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );

  const renderSessionStep = () => (
    <div className="space-y-5">
      {sessions.length ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Session available</p>
              <p className="mt-1 text-sm text-text-muted">
                {sessionLabel(selectedSession)} is ready for term configuration.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={createSession} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Input
              label="Session name"
              value={sessionForm.name}
              placeholder="2026/2027"
              onChange={(event) =>
                setSessionForm((currentForm) => ({
                  ...currentForm,
                  name: event.target.value,
                }))
              }
              required
            />
          </div>
          <Input
            label="Start date"
            type="date"
            value={sessionForm.start_date}
            onChange={(event) =>
              setSessionForm((currentForm) => ({
                ...currentForm,
                start_date: event.target.value,
              }))
            }
            required
          />
          <Input
            label="End date"
            type="date"
            value={sessionForm.end_date}
            onChange={(event) =>
              setSessionForm((currentForm) => ({
                ...currentForm,
                end_date: event.target.value,
              }))
            }
            required
          />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={saving === "session"} className="w-full sm:w-auto">
              {saving === "session" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
              {saving === "session" ? "Creating session..." : "Create session"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );

  const renderTermStep = () => (
    <div className="space-y-5">
      {!selectedSession ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4 text-sm text-text-soft">
          A term must belong to a session. Return to the previous step or skip this step for now.
        </div>
      ) : termsForSession.length ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Term available</p>
              <p className="mt-1 text-sm text-text-muted">
                {termLabel(selectedTerm)} belongs to {sessionLabel(selectedSession)}.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={createTerm} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <SearchableSelect
              label="Academic session"
              value={selectedSessionId}
              onChange={setSelectedSessionId}
              options={sessionOptions}
              searchable={sessions.length > 5}
              required
            />
          </div>
          <div className="sm:col-span-2">
            <SearchableSelect
              label="Term"
              value={termForm.name}
              onChange={(value) =>
                setTermForm((currentForm) => ({ ...currentForm, name: value }))
              }
              searchable={false}
              options={[
                { value: "first_term", label: "First term" },
                { value: "second_term", label: "Second term" },
                { value: "third_term", label: "Third term" },
              ]}
              required
            />
          </div>
          <Input
            label="Start date"
            type="date"
            value={termForm.start_date}
            onChange={(event) =>
              setTermForm((currentForm) => ({
                ...currentForm,
                start_date: event.target.value,
              }))
            }
            required
          />
          <Input
            label="End date"
            type="date"
            value={termForm.end_date}
            onChange={(event) =>
              setTermForm((currentForm) => ({
                ...currentForm,
                end_date: event.target.value,
              }))
            }
            required
          />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={saving === "term"} className="w-full sm:w-auto">
              {saving === "term" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
              {saving === "term" ? "Creating term..." : "Create term"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );

  const renderCalendarStep = () => (
    <div className="space-y-5">
      {!selectedTerm ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4 text-sm text-text-soft">
          Create a term before generating its school calendar.
        </div>
      ) : calendarPrepared ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Calendar generated</p>
              <p className="mt-1 text-sm text-text-muted">
                The calendar for {termLabel(selectedTerm)} matches the current saved configuration and is ready for lifecycle checks.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={generateCalendar} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <SearchableSelect
              label="Academic session"
              value={selectedSessionId}
              onChange={setSelectedSessionId}
              options={sessionOptions}
              searchable={sessions.length > 5}
              required
            />
            <SearchableSelect
              label="Academic term"
              value={selectedTerm?.id || ""}
              onChange={setSelectedTermId}
              options={termOptions}
              searchable={termsForSession.length > 5}
              required
            />
            <Input
              label="Timezone"
              value={calendarForm.timezone}
              onChange={(event) =>
                setCalendarForm((currentForm) => ({
                  ...currentForm,
                  timezone: event.target.value,
                }))
              }
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Opens"
                type="time"
                value={calendarForm.default_open_time}
                onChange={(event) =>
                  setCalendarForm((currentForm) => ({
                    ...currentForm,
                    default_open_time: event.target.value,
                  }))
                }
                required
              />
              <Input
                label="Closes"
                type="time"
                value={calendarForm.default_close_time}
                onChange={(event) =>
                  setCalendarForm((currentForm) => ({
                    ...currentForm,
                    default_close_time: event.target.value,
                  }))
                }
                required
              />
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
            The quick setup uses Monday to Friday as instructional days. You can refine holidays, events, and attendance rules later in the full calendar workspace.
          </div>
          <Button type="submit" disabled={saving === "calendar"} className="w-full sm:w-auto">
            {saving === "calendar" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
            {saving === "calendar" ? "Preparing calendar..." : selectedCalendar ? "Save defaults and regenerate calendar" : "Save defaults and generate calendar"}
          </Button>
        </form>
      )}
    </div>
  );

  const renderStructureStep = () => (
    <div className="space-y-5">
      <div className="rounded-2xl border border-border bg-surface-muted/25 p-4 text-sm leading-6 text-text-muted">
        Build the school structure in order: create an academic level first, then add one or more class arms under that level. Subjects are created separately. Continue when the minimum structure is ready, or skip the stage and return later.
      </div>
      {structureLimitNotice ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4 sm:p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-text">Plan limit reached</p>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                {structureLimitNotice.message}
              </p>
              {structureLimitNotice.limit !== null && structureLimitNotice.limit !== undefined ? (
                <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                  {structureLimitNotice.used} of {structureLimitNotice.limit} {structureLimitNotice.resource}
                </p>
              ) : null}
            </div>
            <Button
              type="button"
              className="w-full sm:w-auto"
              onClick={goToPlanUpgrade}
            >
              <CreditCard className="h-4 w-4" />
              Upgrade plan
            </Button>
          </div>
        </div>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-text">Academic levels and class arms</p>
              <p className="mt-1 text-sm text-text-muted">
                {activeLevels.length} level{activeLevels.length === 1 ? "" : "s"} · {activeClasses.length} class{activeClasses.length === 1 ? "" : "es"}
              </p>
            </div>
            {activeClasses.length ? <Badge variant="success">Ready</Badge> : null}
          </div>
          {activeLevels.length ? (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-bold uppercase tracking-wide text-text-faint">Saved levels</p>
              <div className="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
                {activeLevels.map((level) => {
                  const armCount = activeClasses.filter(
                    (classroom) => classroom.academic_level_id === level.id,
                  ).length;
                  return (
                    <span key={level.id} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-muted/40 py-1 pl-3 pr-1 text-xs font-semibold text-text-soft">
                      <span>{level.name} · {armCount} arm{armCount === 1 ? "" : "s"}</span>
                      {armCount === 0 ? (
                        <button
                          type="button"
                          className="grid h-6 w-6 place-items-center rounded-full text-text-faint transition hover:bg-error-soft hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
                          title={`Remove unused level ${level.name}`}
                          aria-label={`Remove unused level ${level.name}`}
                          disabled={saving === `level-delete-${level.id}`}
                          onClick={() => requestSetupRemoval("level", level)}
                        >
                          {saving === `level-delete-${level.id}` ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      ) : null}
                    </span>
                  );
                })}
              </div>
            </div>
          ) : null}
          {activeClasses.length ? (
            <div className="mt-4 flex max-h-32 flex-wrap gap-2 overflow-y-auto border-t border-border/70 pt-4">
              {activeClasses.map((item) => (
                <span key={item.id} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-muted/40 py-1 pl-3 pr-1 text-xs font-semibold text-text-soft">
                  <span>{classLabel(item)}</span>
                  <button
                    type="button"
                    className="grid h-6 w-6 place-items-center rounded-full text-text-faint transition hover:bg-error-soft hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
                    title={`Remove ${classLabel(item)}`}
                    aria-label={`Remove ${classLabel(item)}`}
                    disabled={saving === `class-delete-${item.id}`}
                    onClick={() => requestSetupRemoval("class", item)}
                  >
                    {saving === `class-delete-${item.id}` ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                </span>
              ))}
            </div>
          ) : null}
          <div className="mt-4 space-y-4 border-t border-border pt-4">
            <form onSubmit={createLevel} className="rounded-xl border border-border/70 bg-surface-muted/25 p-3">
              <div className="mb-3 flex items-start gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground">1</span>
                <div>
                  <p className="text-sm font-semibold text-text">Create the academic level</p>
                  <p className="mt-0.5 text-xs leading-5 text-text-muted">Use the year or stage name only, for example JSS 1. Do not include the arm here.</p>
                </div>
              </div>
              <div className="space-y-3">
                <Input
                  label="Level name"
                  value={levelForm.name}
                  placeholder="JSS 1"
                  onChange={(event) => setLevelForm({ name: event.target.value })}
                  required
                />
                <Button type="submit" variant="outline" disabled={saving === "level"} className="w-full">
                  {saving === "level" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}
                  {saving === "level" ? "Creating level..." : "Create level"}
                </Button>
              </div>
            </form>

            <form onSubmit={createClass} className="rounded-xl border border-border/70 bg-surface-muted/25 p-3">
              <div className="mb-3 flex items-start gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground">2</span>
                <div>
                  <p className="text-sm font-semibold text-text">Add an arm to the level</p>
                  <p className="mt-0.5 text-xs leading-5 text-text-muted">Select a saved level, then add one arm at a time, for example A, B, or Gold.</p>
                </div>
              </div>
              <div className="space-y-3">
                <SearchableSelect
                  label="Academic level"
                  value={classForm.academic_level_id}
                  onChange={(value) => setClassForm((currentForm) => ({ ...currentForm, academic_level_id: value }))}
                  options={levelOptions}
                  placeholder={activeLevels.length ? "Select a level" : "Create a level first"}
                  searchable={activeLevels.length > 5}
                  required
                />
                <Input
                  label="Class arm"
                  value={classForm.arm}
                  placeholder="A"
                  onChange={(event) => setClassForm((currentForm) => ({ ...currentForm, arm: event.target.value }))}
                  required
                />
                <Button type="submit" disabled={!activeLevels.length || saving === "class"} className="w-full">
                  {saving === "class" ? <Loader2 className="h-4 w-4 animate-spin" /> : <School className="h-4 w-4" />}
                  {saving === "class" ? "Adding arm..." : "Add class arm"}
                </Button>
              </div>
            </form>
          </div>
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
                <span key={item.id} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-muted/40 py-1 pl-3 pr-1 text-xs font-semibold text-text-soft">
                  <span>{item.name}</span>
                  <button
                    type="button"
                    className="grid h-6 w-6 place-items-center rounded-full text-text-faint transition hover:bg-error-soft hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
                    title={`Remove ${item.name}`}
                    aria-label={`Remove ${item.name}`}
                    disabled={saving === `subject-delete-${item.id}`}
                    onClick={() => requestSetupRemoval("subject", item)}
                  >
                    {saving === `subject-delete-${item.id}` ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
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
              Progression belongs to academic levels, so every arm at the same level follows one consistent destination.
            </p>
          </div>
        </div>
      </div>

      {!activeLevels.length ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4 text-sm text-text-soft">
          Create at least one academic level before configuring progression. You may skip this stage and return later.
        </div>
      ) : (
        <div className="grid gap-3">
          {activeLevels.map((level) => {
            const draft = progressionDrafts[level.id] || {
              is_terminal: Boolean(level.is_terminal),
              next_level_id: level.next_level_id || "",
            };
            const configured = Boolean(level.is_terminal || level.next_level_id);
            const nextOptions = activeLevels
              .filter((candidate) => candidate.id !== level.id)
              .map((candidate) => ({
                value: candidate.id,
                label: candidate.name,
                description: candidate.is_terminal ? "Terminal level" : "Active level",
              }));

            return (
              <div key={level.id} className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-text">{level.name}</p>
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
                            [level.id]: {
                              ...draft,
                              is_terminal: event.target.checked,
                              next_level_id: event.target.checked ? "" : draft.next_level_id,
                            },
                          }))
                        }
                      />
                      Terminal level — students graduate after this level
                    </label>
                  </div>
                  <div className="grid min-w-0 flex-[1.2] gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                    <SearchableSelect
                      label="Next level"
                      value={draft.next_level_id || ""}
                      onChange={(value) =>
                        setProgressionDrafts((current) => ({
                          ...current,
                          [level.id]: {
                            ...draft,
                            is_terminal: false,
                            next_level_id: value,
                          },
                        }))
                      }
                      options={nextOptions}
                      placeholder={draft.is_terminal ? "Terminal level" : "Select next level"}
                      searchable={nextOptions.length > 5}
                      clearable
                      disabled={draft.is_terminal}
                    />
                    <Button
                      type="button"
                      onClick={() => saveLevelProgression(level)}
                      disabled={
                        saving === `progression-${level.id}` ||
                        (!draft.is_terminal && !draft.next_level_id)
                      }
                      className="w-full sm:w-auto"
                    >
                      {saving === `progression-${level.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Route className="h-4 w-4" />}
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

  const renderSessionOpenStep = () => (
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
  );

  const renderCurrentStep = () => {
    if (current.id === "school_logo") return renderLogoStep();
    if (current.id === "session") return renderSessionStep();
    if (current.id === "term") return renderTermStep();
    if (current.id === "calendar") return renderCalendarStep();
    if (current.id === "structure") return renderStructureStep();
    if (current.id === "progression") return renderProgressionStep();
    if (current.id === "session_open") return renderSessionOpenStep();
    if (current.id === "calendar_active") return renderCalendarActivationStep();
    return renderTermOpenStep();
  };

  return (
    <DashboardLayout
      role="admin"
      title="School setup"
      description="Follow the backend-safe setup sequence without leaving the guided workspace."
      actions={(
        <Button
          type="button"
          size="small"
          variant="outline"
          onClick={() => loadSetup({ quiet: true })}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh status
        </Button>
      )}
    >
      <div className="space-y-5">
        <Card className="overflow-hidden border-primary/20 p-0">
          <div className="border-b border-border bg-primary-soft/45 px-4 py-5 sm:px-6 sm:py-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <div className="flex items-center gap-2 text-primary">
                  <School className="h-4 w-4" />
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em]">
                    Guided academic launch
                  </p>
                </div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-text sm:text-3xl">
                  Build the foundation, then run the school
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted sm:text-base">
                  The assistant verifies live records after every action. It does not cover the dashboard or prevent you from using other features.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="small"
                onClick={() => navigate("/admin/dashboard")}
                className="self-start lg:self-auto"
              >
                Finish later
              </Button>
            </div>
          </div>
          <div className="px-4 py-5 sm:px-6">
            <GuideProgressStepper
              steps={guide.steps}
              currentStepId={current.id}
              onStepSelect={(step) => guide.moveTo(step.id)}
            />
          </div>
        </Card>

        {error ? (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
            {error}
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <Card className="p-4 sm:p-6">
            <StepHeading
              step={current}
              number={guide.currentIndex + 1}
              total={guide.steps.length}
              complete={currentComplete}
            />
            <div className="mt-6 border-t border-border pt-6">
              {renderCurrentStep()}
            </div>

            <div className="mt-7 flex flex-col-reverse gap-2 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <Button
                type="button"
                variant="ghost"
                disabled={firstStep}
                onClick={goPrevious}
              >
                <ArrowLeft className="h-4 w-4" />
                Previous
              </Button>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button type="button" variant="outline" onClick={skipStep}>
                  Skip this step
                </Button>
                <Button
                  type="button"
                  onClick={continueStep}
                  disabled={!currentComplete && !setupReadyToComplete && guide.guideState?.status !== "completed"}
                >
                  {lastStep || setupReadyToComplete ? "Complete setup" : "Continue"}
                  {lastStep || setupReadyToComplete ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <ArrowRight className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </Card>

          <div className="space-y-4">
            <Card className="p-4 sm:p-5">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
                Setup context
              </p>
              <div className="mt-4 space-y-3">
                <SearchableSelect
                  label="Session"
                  value={selectedSessionId}
                  onChange={setSelectedSessionId}
                  options={sessionOptions}
                  placeholder="No session yet"
                  searchable={sessions.length > 5}
                  clearable={false}
                  disabled={!sessions.length}
                />
                <SearchableSelect
                  label="Term"
                  value={selectedTerm?.id || ""}
                  onChange={setSelectedTermId}
                  options={termOptions}
                  placeholder="No term yet"
                  searchable={termsForSession.length > 5}
                  clearable={false}
                  disabled={!termsForSession.length}
                />
              </div>
            </Card>

            <Card className="p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
                  Live status
                </p>
                <span className="text-sm font-bold text-primary">
                  {guide.completionPercent}%
                </span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300"
                  style={{ width: `${guide.completionPercent}%` }}
                />
              </div>
              <div className="mt-4 space-y-2">
                <SetupCheck
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
                  detail={`${activeClasses.length} classes · ${activeSubjects.length} subjects`}
                />
                <SetupCheck
                  label="Level progression"
                  complete={completionMap.progression}
                  detail={progressionComplete ? "Every active level has a destination" : "Choose next levels or terminal levels"}
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
                />
              </div>
              <p className="mt-4 text-xs leading-5 text-text-faint">
                {calendarConfiguration
                  ? "Calendar defaults are saved."
                  : "Calendar defaults will be saved during the calendar step."}
              </p>
            </Card>
          </div>
        </div>

        <ConfirmDialog
          open={Boolean(deleteConfirmation)}
          title={
            deleteConfirmation?.type === "class"
              ? "Remove class from setup?"
              : deleteConfirmation?.type === "level"
                ? "Remove academic level from setup?"
                : "Remove subject from setup?"
          }
          description={
            deleteConfirmation
              ? deleteConfirmation.type === "level"
                ? `${deleteConfirmation.label} has no class arms and will be permanently removed from assisted setup.`
                : `${deleteConfirmation.label} is unused and will be permanently removed from assisted setup. Your plan usage will be refreshed.`
              : ""
          }
          confirmLabel="Remove"
          variant="danger"
          isLoading={
            deleteConfirmation
              ? saving === `${deleteConfirmation.type}-delete-${deleteConfirmation.item.id}`
              : false
          }
          onCancel={() => {
            if (!saving) setDeleteConfirmation(null);
          }}
          onConfirm={confirmSetupRemoval}
        />

        <Modal
          open={Boolean(warningDialog)}
          title={warningDialog?.title || "Action needed"}
          description={warningDialog?.message || ""}
          onClose={() => setWarningDialog(null)}
          placement="center"
          footer={(
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={() => setWarningDialog(null)}>
                Stay here
              </Button>
              {warningDialog?.onAction ? (
                <Button
                  type="button"
                  onClick={() => {
                    const action = warningDialog.onAction;
                    setWarningDialog(null);
                    action();
                  }}
                >
                  <CreditCard className="h-4 w-4" />
                  {warningDialog.actionLabel || "Continue"}
                </Button>
              ) : null}
            </div>
          )}
        >
          <div className="flex gap-3 rounded-2xl border border-warning/30 bg-warning-soft px-4 py-4 text-sm leading-6 text-amber-900">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold text-amber-950">
                This setup action is blocked by the current plan.
              </p>
              {warningDialog?.detail ? (
                <p className="mt-1 text-xs font-semibold uppercase tracking-wide">
                  {warningDialog.detail}
                </p>
              ) : null}
            </div>
          </div>
        </Modal>
      </div>
    </DashboardLayout>
  );
}

export default AdminGettingStartedPage;
