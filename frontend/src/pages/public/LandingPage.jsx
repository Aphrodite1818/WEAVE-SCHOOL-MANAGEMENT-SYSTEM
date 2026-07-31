import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  BarChart3,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  GraduationCap,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import {
  LANDING_PRICING_PLANS,
  buildRegistrationHref,
  formatLimitValue,
  saveSelectedSubscriptionPlan,
} from "../../features/subscriptions/subscriptionConfig";
import Navbar from "../../components/layout/Navbar";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import previewImage from "../../assets/images/academic-workspace-preview.png";

const features = [
  { title: "Student Management", description: "Create student records, assign classes, link guardians, and keep academic status visible.", icon: GraduationCap },
  { title: "Teacher Management", description: "Manage teacher profiles, subjects, class assignments, and verification status.", icon: Users },
  { title: "Attendance", description: "Mark daily attendance and keep summaries available for admins, teachers, and parents.", icon: ClipboardCheck },
  { title: "Grades", description: "Record scores, track drafts and submissions, and prepare report cards.", icon: BookOpen },
  { title: "Timetable", description: "Organize class schedules and keep teaching assignments clear.", icon: CalendarDays },
  { title: "Analytics", description: "Track enrollment, attendance, results, usage, and billing signals without digging through tables.", icon: BarChart3 },
];

const benefits = [
  "Separate dashboards for admins, teachers, students, parents, and platform operators.",
  "Routes, services, and API calls stay separated so the frontend remains maintainable.",
  "Mobile layouts keep the common tasks usable on phones, not just desktop.",
];

const operationalNotes = [
  {
    title: "Admins see the school state",
    description: "Enrollment, staff, classes, results, billing, and notices stay reachable from one workspace.",
  },
  {
    title: "Teachers stay focused",
    description: "Attendance, class context, score entry, and announcements sit close to the daily teaching flow.",
  },
  {
    title: "Parents get the right context",
    description: "Portal views keep student updates, attendance, and school notices clear without exposing admin tools.",
  },
];

function PlanLimit({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-text-muted">{label}</span>
      <span className="font-semibold text-text">{value}</span>
    </div>
  );
}

function formatLandingPrice(plan) {
  if (plan.planCode === "enterprise") return "From \u20a680,000/mo";
  if (!plan.priceMonthly) return "\u20a60";
  return `\u20a6${Number(plan.priceMonthly).toLocaleString()}/mo`;
}

function LandingPricingCard({ plan, activePlanCode, onSelect }) {
  const isFree = plan.planCode === "free_trial";
  const isSelected = plan.planCode === activePlanCode;
  const isCurrent = plan.planCode === "professional";

  return (
    <article
      id={`landing-plan-${plan.planCode}`}
      className={`flex min-h-[34rem] scroll-mt-28 flex-col rounded-[1.6rem] border bg-surface p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-premium-hover sm:p-6 ${
        isSelected
          ? "border-primary/60 ring-4 ring-primary/10"
          : plan.highlighted
            ? "border-border/80"
            : "border-border/70"
      }`}
    >
      <div className="flex min-h-8 flex-wrap items-center gap-2">
        {isFree ? <Badge variant="success">Free</Badge> : null}
        {plan.highlighted ? <Badge variant="primary">Recommended</Badge> : null}
        {isCurrent ? <Badge variant="success">Current plan</Badge> : null}
      </div>

      <h3 className="mt-4 text-2xl font-semibold text-text">{plan.name}</h3>
      <p className="mt-2 text-sm font-semibold text-primary">{plan.bestFor}</p>
      <p className="mt-4 min-h-[4.5rem] text-sm leading-6 text-text-muted">{plan.description}</p>

      <div className="mt-5">
        <p className="text-2xl font-bold text-text">{formatLandingPrice(plan)}</p>
        <p className="mt-1 text-xs font-medium text-text-muted">Monthly billing</p>
      </div>

      <ul className="mt-5 space-y-3 text-sm text-text-soft">
        {plan.features.map((feature) => (
          <li key={feature} className="flex gap-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      <div className="mt-5 grid gap-2 rounded-2xl border border-border/70 bg-surface-muted/25 px-4 py-3 text-sm">
        <PlanLimit label="Students" value={formatLimitValue(plan.limits.students)} />
        <PlanLimit label="Teachers" value={formatLimitValue(plan.limits.teachers)} />
        <PlanLimit label="Classes" value={formatLimitValue(plan.limits.classes)} />
      </div>

      <div className="flex flex-1 items-center justify-center pt-6">
        <div className="w-full max-w-[19rem] text-center">
          <Link
            to={buildRegistrationHref(plan.planCode)}
            onClick={() => onSelect(plan.planCode)}
          >
            <Button className="w-full">
              Get started
            </Button>
          </Link>
          <div className="mt-3 flex justify-center">
            <span
              className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                isSelected ? "bg-primary/10 text-primary" : "bg-surface-muted text-text-muted"
              }`}
            >
              {isSelected ? "Selected" : `Choose ${plan.name}`}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}

function LandingPage() {
  const location = useLocation();
  const [activePricingPlan, setActivePricingPlan] = useState("plus");

  const handlePlanSelection = (planCode, billingInterval = "monthly") => {
    saveSelectedSubscriptionPlan({ planCode, billingInterval });
  };
  const handlePricingTabClick = (planCode) => {
    setActivePricingPlan(planCode);
  };
  const freePlan = LANDING_PRICING_PLANS.find((plan) => plan.planCode === "free_trial");
  const paidLandingPlans = LANDING_PRICING_PLANS.filter((plan) => plan.planCode !== "free_trial");

  useEffect(() => {
    if (!location.hash) return;

    const target = document.getElementById(location.hash.slice(1));
    if (!target) return;

    window.requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [location.hash]);

  return (
    <div className="public-page-shell min-h-[100dvh] overflow-x-hidden bg-background text-text">
      <Navbar />

      <main>
        <section id="home" className="relative min-h-[calc(100dvh-4.4rem)] scroll-mt-24 overflow-hidden border-b border-border bg-slate-950 text-white">
          <img
            src={previewImage}
            alt="Weave dashboard preview"
            className="absolute inset-0 h-full w-full object-cover opacity-35"
          />
          <div className="absolute inset-0 bg-slate-950/70" />
          <div className="section-container relative flex min-h-[calc(100dvh-4.4rem)] items-center py-8 pb-[max(2rem,env(safe-area-inset-bottom))] sm:py-18 lg:py-24">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)] lg:items-center">
              <div className="max-w-3xl">
                <h1 className="text-balance text-4xl font-semibold leading-tight tracking-tight text-white sm:text-6xl lg:text-7xl">
                  Run school records, results, attendance, and notices from one workspace.
                </h1>
                <p className="mt-5 max-w-2xl text-base leading-7 text-slate-200 sm:text-lg sm:leading-8">
                  Weave gives admins, teachers, students, and parents the screens they need for daily school work: enrollment, class setup, attendance, score entry, report cards, announcements, and billing.
                </p>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Link to={buildRegistrationHref("free_trial")}>
                    <Button size="large" className="w-full sm:w-auto">
                      Start Free Trial
                    </Button>
                  </Link>
                  <Link to="/pricing" className="w-full sm:w-auto">
                    <Button
                      variant="outline"
                      size="large"
                      className="w-full border-white/20 bg-white/10 text-white hover:bg-white/15"
                    >
                      View Pricing
                    </Button>
                  </Link>
                </div>
                <div className="mt-8 grid gap-3 sm:grid-cols-3">
                  {[
                    ["Multi-role", "Admin, teacher, student, and parent workspaces"],
                    ["Tenant-aware", "School-level boundaries and onboarding"],
                    ["Billing-ready", "Checkout and subscription verification"],
                  ].map(([title, copy]) => (
                    <div
                      key={title}
                      className="rounded-2xl border border-white/10 bg-white/10 px-4 py-4 backdrop-blur-xl"
                    >
                      <p className="text-sm font-semibold text-white">{title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-300">{copy}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[1.75rem] border border-white/10 bg-white/10 p-4 backdrop-blur-xl sm:p-5">
                <div className="rounded-[1.45rem] border border-white/10 bg-slate-950/35 p-4">
                  <p className="text-sm font-semibold text-white">What schools get first</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    Set up the school, create users, assign classes, publish notices, and start recording academic work.
                  </p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {LANDING_PRICING_PLANS.slice(0, 4).map((plan) => (
                    <Link
                      key={plan.planCode}
                      to="/pricing"
                      onClick={() => handlePlanSelection(plan.planCode)}
                      className={`rounded-[1.25rem] border px-4 py-4 text-left transition ${
                        plan.highlighted
                          ? "border-primary/40 bg-primary/10"
                          : "border-white/10 bg-white/5 hover:bg-white/10"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-white">{plan.name}</p>
                        {plan.highlighted ? (
                          <span className="rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-semibold text-white">
                            Popular
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 text-xs uppercase tracking-wide text-slate-300">
                        {plan.priceLabel}
                      </p>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="section-container scroll-mt-24 py-20">
          <div className="max-w-3xl">
            <p className="text-sm font-bold uppercase tracking-wide text-primary">Features</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
              The daily school work is already mapped.
            </h2>
            <p className="mt-4 text-base leading-7 text-text-muted">
              Each role gets a focused workspace for the tasks they repeat most.
            </p>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article key={feature.title} className="rounded-2xl border border-border bg-surface p-6 shadow-soft-card">
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-text-muted">{feature.description}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section id="benefits" className="scroll-mt-24 border-y border-border bg-surface">
          <div className="section-container grid gap-10 py-20 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <div>
              <p className="text-sm font-bold uppercase tracking-wide text-primary">Benefits</p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
                Built for daily use, not demos.
              </h2>
              <p className="mt-4 text-base leading-7 text-text-muted">
                The interface favors quick scans, clear actions, and records that stay tied to the right tenant.
              </p>
            </div>
            <div className="grid gap-3">
              {benefits.map((benefit) => (
                <div key={benefit} className="flex gap-3 rounded-2xl border border-border bg-background px-5 py-4">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                  <p className="text-sm font-medium leading-6 text-text-soft">{benefit}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section-container py-20">
          <div className="grid gap-6 lg:grid-cols-3">
            {operationalNotes.map((note) => (
              <article key={note.title} className="rounded-2xl border border-border bg-surface p-6 shadow-soft-card">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-soft text-primary">
                  <CheckCircle2 className="h-5 w-5" />
                </span>
                <h3 className="mt-5 text-lg font-semibold">{note.title}</h3>
                <p className="mt-2 text-sm leading-6 text-text-muted">{note.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="pricing" className="relative scroll-mt-24 overflow-hidden border-y border-border bg-background">
          <div className="section-container relative py-16 sm:py-20">
            <div className="mx-auto max-w-3xl text-center">
              <Badge variant="primary">Pricing</Badge>
              <h2 className="mt-5 text-4xl font-semibold tracking-tight text-text sm:text-5xl">
                Simple capacity-based plans.
              </h2>
              <p className="mt-4 text-base leading-7 text-text-muted">
                Start free. Upgrade when student, teacher, class, import, or analytics limits become real.
              </p>
            </div>

            <div className="mx-auto mt-8 flex max-w-full justify-center overflow-x-auto px-1 pb-1">
              <div className="inline-grid min-w-[34rem] grid-cols-4 gap-1 rounded-full border border-border/70 bg-surface-muted/60 p-1 shadow-soft-card sm:min-w-[42rem]">
                {LANDING_PRICING_PLANS.map((plan) => (
                  <a
                    key={`landing-plan-tab-${plan.planCode}`}
                    href={`#landing-plan-${plan.planCode}`}
                    onClick={() => handlePricingTabClick(plan.planCode)}
                    aria-current={activePricingPlan === plan.planCode ? "true" : undefined}
                    className={`rounded-full px-3 py-2.5 text-center text-sm font-semibold transition ${
                      activePricingPlan === plan.planCode
                        ? "bg-surface text-primary shadow-[0_10px_30px_rgba(15,23,42,0.12)] ring-1 ring-border/60"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {plan.planCode === "free_trial" ? "Free" : plan.name}
                  </a>
                ))}
              </div>
            </div>

            <div className="mt-10">
              {freePlan ? (
                <div
                  id="landing-plan-free_trial"
                  className={`mb-5 flex scroll-mt-28 flex-col gap-4 rounded-[1.5rem] border px-5 py-5 shadow-soft-card sm:flex-row sm:items-center sm:justify-between ${
                    activePricingPlan === "free_trial"
                      ? "border-primary/60 bg-surface ring-4 ring-primary/10"
                      : "border-primary/25 bg-primary/5"
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="success">Free</Badge>
                      <span className="text-xs font-bold uppercase tracking-wide text-primary">Start here</span>
                    </div>
                    <h3 className="mt-3 text-xl font-semibold text-text">{freePlan.name}</h3>
                    <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">{freePlan.description}</p>
                  </div>
                  <div className="flex shrink-0 flex-col gap-2 sm:min-w-56">
                    <p className="text-2xl font-bold text-text">{formatLandingPrice(freePlan)}</p>
                    <Link
                      to={buildRegistrationHref(freePlan.planCode)}
                      onClick={() => handlePlanSelection(freePlan.planCode)}
                    >
                      <Button className="w-full">Get started</Button>
                    </Link>
                  </div>
                </div>
              ) : null}

              <div className="grid items-stretch gap-5 lg:grid-cols-3">
                {paidLandingPlans.map((plan) => (
                  <LandingPricingCard
                    key={plan.planCode}
                    plan={plan}
                    activePlanCode={activePricingPlan}
                    onSelect={handlePlanSelection}
                  />
                ))}
              </div>
            </div>

            <div className="mt-8 flex flex-col items-center justify-between gap-4 rounded-[1.5rem] border border-border/70 bg-surface px-5 py-5 text-center shadow-soft-card sm:flex-row sm:text-left">
              <div>
                <div className="flex items-center justify-center gap-2 sm:justify-start">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <p className="text-sm font-semibold text-text">Need the full comparison?</p>
                </div>
                <p className="mt-1 text-sm leading-6 text-text-muted">Open the dedicated pricing page for the full plan matrix and FAQs.</p>
              </div>
              <Link to="/pricing" className="w-full sm:w-auto">
                <Button className="w-full sm:w-auto">
                  View full pricing
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
        </section>

        <section className="section-container py-20">
          <div className="rounded-2xl border border-border bg-slate-950 px-6 py-12 text-center text-white shadow-premium sm:px-10">
            <ShieldCheck className="mx-auto h-10 w-10 text-primary-soft" />
            <h2 className="mt-5 text-4xl font-semibold tracking-tight text-white">
              Set up a school workspace.
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-300">
              Create the tenant, invite users, and start with the core academic flow before upgrading.
            </p>
            <Link to={buildRegistrationHref("free_trial")} className="mt-8 inline-flex">
              <Button size="large">Create workspace</Button>
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="section-container flex flex-col gap-4 py-8 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-bold">Weave</p>
            <p className="mt-1 text-sm text-text-muted">School management workspace.</p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm font-semibold text-text-muted">
            <a href="#features" className="hover:text-primary">Features</a>
            <a href="#benefits" className="hover:text-primary">Benefits</a>
            <Link to="/pricing" className="hover:text-primary">Pricing</Link>
            <Link to="/login" className="hover:text-primary">Log in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;

