import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  CalendarDays,
  FileText,
  GitBranch,
  GraduationCap,
  Layers3,
  Ruler,
  School,
  Users,
} from "lucide-react";

import {
  DashboardMetricCard,
} from "../../components/dashboard/DashboardPrimitives";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import { academicWorkflowConfig } from "../../features/academic-admin/academicWorkflowConfig";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import {
  getCachedDashboardBundle,
  getDashboardSessionCacheKey,
} from "../../services/dashboardSessionCache";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";

const ACADEMIC_HUB_CACHE_KEY = getDashboardSessionCacheKey(
  "admin:academic-hub-overview",
);

const domainIcons = {
  classes: School,
  subjects: BookOpen,
  "class-subjects": Layers3,
  assignments: Users,
  sessions: CalendarDays,
  terms: CalendarDays,
  grading: Ruler,
  results: BarChart3,
  "report-cards": FileText,
  "school-calendar": CalendarDays,
  progression: GitBranch,
};

const domains = [
  "classes",
  "subjects",
  "class-subjects",
  "assignments",
  "sessions",
  "terms",
  "grading",
  "results",
  "report-cards",
  "school-calendar",
  "progression",
].map((key) => ({
  key,
  ...academicWorkflowConfig[key],
  icon: domainIcons[key] || academicWorkflowConfig[key].icon,
  to: `/admin/academic/${key}`,
}));

const metricNumber = (value, fallback = "-") => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

function scheduleBackgroundTask(callback) {
  if (typeof window === "undefined") return undefined;
  if (typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(callback, { timeout: 1200 });
    return () => window.cancelIdleCallback(id);
  }
  const id = window.setTimeout(callback, 250);
  return () => window.clearTimeout(id);
}

function AcademicHubOverviewPage() {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [metricsError, setMetricsError] = useState(null);
  const [selectedDomain, setSelectedDomain] = useState("classes");
  const [isMetricsRefreshing, setIsMetricsRefreshing] = useState(false);
  const [orbitRotation, setOrbitRotation] = useState(0);
  const [isSpinning, setIsSpinning] = useState(false);
  const orbitRotationRef = useRef(0);
  const orbitDragRef = useRef({
    active: false,
    dragged: false,
    domainKey: "",
    pointerType: "",
    startRotation: 0,
    currentRotation: 0,
    lastX: 0,
    lastY: 0,
    lastTime: 0,
    velocity: 0,
  });
  const spinFrameRef = useRef(0);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    const cancelIdleTask = scheduleBackgroundTask(async () => {
      if (!mounted) return;
      setIsMetricsRefreshing(true);
      setMetricsError(null);
      try {
        const data = await getCachedDashboardBundle(ACADEMIC_HUB_CACHE_KEY, () =>
          dashboardService.getTenantAdminAnalytics({ signal: controller.signal }),
        );
        if (!mounted || controller.signal.aborted) return;
        setAnalytics(data);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setMetricsError(getErrorMessage(err, "Academic metrics could not be loaded."));
      } finally {
        if (mounted) setIsMetricsRefreshing(false);
      }
    });

    return () => {
      mounted = false;
      controller.abort();
      if (typeof cancelIdleTask === "function") cancelIdleTask();
    };
  }, []);

  const stats = analytics?.stats || {};
  const hasMetrics = Boolean(analytics?.stats);

  const orbitDomains = useMemo(
    () =>
      domains.map((domain, index) => ({
        ...domain,
        style: {
          "--orbit-index": index,
          "--orbit-count": domains.length,
          "--orbit-angle": `${(360 / domains.length) * index}deg`,
          "--orbit-angle-counter": `${(-360 / domains.length) * index}deg`,
        },
      })),
    [],
  );

  const updateOrbitRotation = (value) => {
    orbitRotationRef.current = value;
    setOrbitRotation(value);
  };

  const getDragRotationDelta = (event, previousX, previousY) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const centerX = bounds.left + bounds.width / 2;
    const centerY = bounds.top + bounds.height / 2;
    const dx = event.clientX - previousX;
    const dy = event.clientY - previousY;
    const relativeX = previousX - centerX;
    const relativeY = previousY - centerY;
    const distance = Math.hypot(relativeX, relativeY);

    if (distance < bounds.width * 0.14) {
      return dx * 0.42;
    }

    const tangentX = -relativeY / distance;
    const tangentY = relativeX / distance;
    const tangentMovement = dx * tangentX + dy * tangentY;
    return (tangentMovement / Math.max(distance, 1)) * (180 / Math.PI);
  };

  useEffect(
    () => () => {
      if (spinFrameRef.current) window.cancelAnimationFrame(spinFrameRef.current);
    },
    [],
  );

  const startOrbitSpin = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const domainButton = event.target.closest?.("[data-academic-domain-key]");
    if (spinFrameRef.current) {
      window.cancelAnimationFrame(spinFrameRef.current);
      spinFrameRef.current = 0;
    }
    orbitDragRef.current = {
      active: true,
      dragged: false,
      domainKey: domainButton?.dataset?.academicDomainKey || "",
      pointerType: event.pointerType,
      startRotation: orbitRotationRef.current,
      currentRotation: orbitRotationRef.current,
      lastX: event.clientX,
      lastY: event.clientY,
      lastTime: performance.now(),
      velocity: 0,
    };
    setIsSpinning(true);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const spinOrbit = (event) => {
    const drag = orbitDragRef.current;
    if (!drag.active) return;
    event.preventDefault();
    const now = performance.now();
    const elapsed = Math.max(now - drag.lastTime, 16);
    const delta = getDragRotationDelta(event, drag.lastX, drag.lastY);
    const nextRotation = drag.currentRotation + delta;
    if (Math.abs(nextRotation - drag.startRotation) > 3) {
      drag.dragged = true;
    }
    drag.velocity = delta / elapsed;
    drag.currentRotation = nextRotation;
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;
    drag.lastTime = now;
    updateOrbitRotation(nextRotation);
  };

  const coastOrbit = (initialRotation, initialVelocity) => {
    let velocity = initialVelocity * 16;
    let rotation = initialRotation;
    const step = () => {
      velocity *= 0.94;
      rotation += velocity;
      updateOrbitRotation(rotation);
      if (Math.abs(velocity) > 0.05) {
        spinFrameRef.current = window.requestAnimationFrame(step);
      } else {
        spinFrameRef.current = 0;
      }
    };
    spinFrameRef.current = window.requestAnimationFrame(step);
  };

  const stopOrbitSpin = (event) => {
    const drag = orbitDragRef.current;
    drag.active = false;
    setIsSpinning(false);
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    if (drag.dragged) {
      coastOrbit(orbitRotationRef.current, drag.velocity);
      return;
    }

    if (drag.domainKey) {
      const domain = domains.find((item) => item.key === drag.domainKey);
      if (domain) navigate(domain.to);
    }
  };

  const openDomain = (domain) => {
    if (orbitDragRef.current.dragged) {
      orbitDragRef.current.dragged = false;
      return;
    }
    navigate(domain.to);
  };

  return (
    <DashboardLayout
      role="admin"
    >
      <section className="academic-hub-domain-shell">
        <Card className="academic-hub-selector-card overflow-hidden p-4 sm:p-6">
          <div className="academic-hub-selector-top min-w-0">
            <h2 className="max-w-3xl text-2xl font-semibold leading-tight sm:text-3xl">
              Academic Hub
            </h2>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge
                className="academic-hub-status-badge"
                variant={stats.active_academic_session ? "success" : "warning"}
              >
                Session: {cleanText(stats.active_academic_session, hasMetrics ? "Not set" : "Loading")}
              </Badge>
              <Badge
                className="academic-hub-status-badge"
                variant={stats.active_academic_term ? "primary" : "warning"}
              >
                Term: {cleanText(stats.active_academic_term, hasMetrics ? "Not set" : "Loading")}
              </Badge>
              {isMetricsRefreshing ? (
                <Badge className="academic-hub-status-badge" variant="primary">
                  Metrics refreshing
                </Badge>
              ) : null}
              {metricsError ? (
                <Badge className="academic-hub-status-badge" variant="error">
                  Metrics unavailable
                </Badge>
              ) : null}
            </div>
            {metricsError ? (
              <p className="mt-3 max-w-2xl text-sm font-medium">
                {metricsError}
              </p>
            ) : null}
          </div>

          <div className="academic-orbit-wrap mt-4">
            <div
              className={cn("academic-orbit", isSpinning ? "is-spinning" : "")}
              style={{
                "--orbit-rotation": `${orbitRotation}deg`,
                "--orbit-rotation-counter": `${-orbitRotation}deg`,
              }}
              aria-label="Academic Hub domains"
              onPointerDown={startOrbitSpin}
              onPointerMove={spinOrbit}
              onPointerUp={stopOrbitSpin}
              onPointerCancel={stopOrbitSpin}
            >
              <div className="academic-orbit-ring academic-orbit-ring-outer" />
              <div className="academic-orbit-ring academic-orbit-ring-inner" />
              <div className="academic-orbit-core">
                <GraduationCap className="h-9 w-9 text-primary" />
                <span>Academic Hub</span>
              </div>
              {orbitDomains.map((domain) => {
                const Icon = domain.icon;
                const active = selectedDomain === domain.key;
                return (
                  <button
                    key={domain.key}
                    type="button"
                    data-academic-domain-key={domain.key}
                    style={domain.style}
                    onMouseEnter={() => setSelectedDomain(domain.key)}
                    onFocus={() => setSelectedDomain(domain.key)}
                    onClick={() => openDomain(domain)}
                    onDragStart={(event) => event.preventDefault()}
                    className={cn(
                      "academic-orbit-node group",
                      active ? "is-active" : "",
                    )}
                    aria-label={`Open ${domain.title}`}
                  >
                    <span className="academic-orbit-icon">
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="academic-orbit-label">{domain.shortTitle}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </Card>

        <div className="academic-hub-wave" aria-hidden="true" />

        <div className="academic-hub-kpi-grid grid grid-cols-2 gap-3 xl:grid-cols-4">
          <DashboardMetricCard
            compact
            label="Students"
            value={metricNumber(stats.total_students)}
            description="Learner records"
            icon={Users}
            tone="primary"
            to="/admin/students"
          />
          <DashboardMetricCard
            compact
            label="Subjects"
            value={metricNumber(stats.total_subjects)}
            description="Catalog records"
            icon={BookOpen}
            tone="success"
            to="/admin/academic/subjects"
          />
          <DashboardMetricCard
            compact
            label="Result completion"
            value={
              Number.isFinite(Number(stats.result_completion_percent))
                ? `${stats.result_completion_percent}%`
                : "-"
            }
            description="Submitted rows"
            icon={BarChart3}
            tone="warning"
            to="/admin/academic/results?view=submitted"
          />
          <DashboardMetricCard
            compact
            label="Report cards"
            value={metricNumber(stats.report_cards_published)}
            description={`${metricNumber(stats.report_cards_generated)} generated`}
            icon={FileText}
            tone="primary"
            to="/admin/academic/report-cards?view=published"
          />
        </div>

      </section>
    </DashboardLayout>
  );
}

export default AcademicHubOverviewPage;
