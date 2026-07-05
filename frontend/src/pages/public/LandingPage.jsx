import { Link } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  GraduationCap,
  ShieldCheck,
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
  { title: "Student Management", description: "Centralized student profiles, guardians, class history, and academic status.", icon: GraduationCap },
  { title: "Teacher Management", description: "Profiles, qualifications, subjects, schedules, and assignment visibility.", icon: Users },
  { title: "Attendance", description: "Daily attendance marking with summaries for staff and parents.", icon: ClipboardCheck },
  { title: "Grades", description: "Score entry, performance tracking, report-card-ready academic records.", icon: BookOpen },
  { title: "Timetable", description: "Structured class schedules that make the school day easier to operate.", icon: CalendarDays },
  { title: "Analytics", description: "Operational dashboards for attendance, enrollment, notices, and AI activity.", icon: BarChart3 },
];

const benefits = [
  "Role-specific workspaces for admins, teachers, students, parents, and platform admins.",
  "Clean service boundaries so frontend pages do not own backend API logic.",
  "Mobile-friendly screens that stack naturally while staying optimized for desktop use.",
];

const testimonials = [
  {
    quote: "The dashboard gives our admin team the daily picture without forcing them into giant tables.",
    name: "Anita Sharma",
    role: "School Administrator",
  },
  {
    quote: "Attendance, notices, and class context finally live in one place that teachers can scan quickly.",
    name: "David Mensah",
    role: "Academic Lead",
  },
  {
    quote: "It feels calm and professional, which matters when parents and staff use the system every day.",
    name: "Ada Okafor",
    role: "Parent Liaison",
  },
];

function LandingPage() {
  const handlePlanSelection = (planCode, billingInterval = "monthly") => {
    saveSelectedSubscriptionPlan({ planCode, billingInterval });
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-background text-text">
      <Navbar />

      <main>
        <section className="relative overflow-hidden border-b border-border bg-slate-950 text-white">
          <img
            src={previewImage}
            alt="Learnly AI dashboard preview"
            className="absolute inset-0 h-full w-full object-cover opacity-35"
          />
          <div className="absolute inset-0 bg-slate-950/70" />
          <div className="section-container relative py-14 sm:py-18 lg:py-24">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)] lg:items-center">
              <div className="max-w-3xl">
                <h1 className="text-balance text-4xl font-semibold leading-tight tracking-tight text-white sm:text-6xl lg:text-7xl">
                  School operations, academics, and communication in one calm workspace.
                </h1>
                <p className="mt-5 max-w-2xl text-base leading-7 text-slate-200 sm:text-lg sm:leading-8">
                  Learnly AI gives tenant admins, teachers, students, and parents a cleaner way to run daily school work without breaking the backend model already driving the platform.
                </p>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Link to={buildRegistrationHref("free_trial")}>
                    <Button size="large" className="w-full sm:w-auto">
                      Start Free Trial
                    </Button>
                  </Link>
                  <a href="#pricing" className="w-full sm:w-auto">
                    <Button
                      variant="outline"
                      size="large"
                      className="w-full border-white/20 bg-white/10 text-white hover:bg-white/15"
                    >
                      View Plans
                    </Button>
                  </a>
                </div>
                <div className="mt-8 grid gap-3 sm:grid-cols-3">
                  {[
                    ["Multi-role", "Admin, teacher, student, and parent workspaces"],
                    ["Tenant-aware", "Built around school-level boundaries and onboarding"],
                    ["Billing-ready", "Live subscription checkout and verification flow"],
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
                  <p className="text-sm font-semibold text-white">Why tenant admins start here</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    Free Trial gets the school online quickly. Paid plans unlock larger limits, advanced analytics, bulk imports, and AI support as the school grows.
                  </p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {LANDING_PRICING_PLANS.slice(0, 4).map((plan) => (
                    <button
                      key={plan.planCode}
                      type="button"
                      onClick={() =>
                        handlePlanSelection(
                          plan.planCode,
                          plan.planCode === "free_trial" ? "monthly" : "monthly"
                        )
                      }
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
                        {plan.bestFor}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="section-container py-20">
          <div className="max-w-3xl">
            <p className="text-sm font-bold uppercase tracking-wide text-primary">Features</p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
              Built around the workflows schools repeat every day.
            </h2>
            <p className="mt-4 text-base leading-7 text-text-muted">
              The platform keeps operational visibility high without burying teams in old-style admin templates.
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

        <section id="benefits" className="border-y border-border bg-surface">
          <div className="section-container grid gap-10 py-20 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <div>
              <p className="text-sm font-bold uppercase tracking-wide text-primary">Benefits</p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
                Calm software for busy school teams.
              </h2>
              <p className="mt-4 text-base leading-7 text-text-muted">
                Learnly AI is designed for repeated daily use: scanning, acting, reviewing, and moving on.
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
            {testimonials.map((testimonial) => (
              <article key={testimonial.name} className="rounded-2xl border border-border bg-surface p-6 shadow-soft-card">
                <p className="text-base leading-7 text-text-soft">"{testimonial.quote}"</p>
                <div className="mt-6 flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-soft font-bold text-primary">
                    {testimonial.name.split(" ").map((part) => part[0]).join("")}
                  </span>
                  <div>
                    <p className="font-semibold">{testimonial.name}</p>
                    <p className="text-sm text-text-muted">{testimonial.role}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section id="pricing" className="border-y border-border bg-surface">
          <div className="section-container relative overflow-hidden py-20">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-x-0 top-8 -z-10 h-72 rounded-[2.5rem] bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.14),transparent_42%),radial-gradient(circle_at_left,rgba(59,130,246,0.08),transparent_34%)]"
            />
            <div className="mx-auto max-w-3xl text-center">
              <p className="text-sm font-bold uppercase tracking-wide text-primary">Pricing</p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
                Plans that match how schools actually grow.
              </h2>
              <p className="mt-4 text-base leading-7 text-text-muted">
                Pick a plan, continue to registration, and keep your selection ready for billing after tenant-admin setup.
              </p>
            </div>
            <div className="mt-10 grid items-stretch gap-5 md:grid-cols-2 2xl:grid-cols-4">
              {LANDING_PRICING_PLANS.map((plan) => (
                <article
                  key={plan.planCode}
                  className={`flex min-h-[430px] flex-col rounded-[1.75rem] border p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-premium-hover ${
                    plan.highlighted
                      ? "border-accent bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.16),transparent_34%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(15,23,42,0.94))] ring-4 ring-accent/10"
                      : "border-border/70 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.92))]"
                  }`}
                >
                  <div className="flex min-h-8 flex-wrap items-center gap-2">
                    {plan.highlighted ? (
                      <Badge variant="primary">Recommended</Badge>
                    ) : null}
                    {plan.planCode === "free_trial" ? (
                      <Badge variant="success">Get started</Badge>
                    ) : null}
                  </div>

                  <div>
                    <h3 className="mt-4 text-2xl font-semibold text-white">{plan.name}</h3>
                    <p className="mt-2 text-sm font-semibold text-primary">{plan.bestFor}</p>
                    <p className="mt-5 text-sm leading-6 text-slate-300">{plan.description}</p>
                    <div className="mt-5">
                      <p className="text-3xl font-bold text-white">{plan.priceLabel}</p>
                      <p className="mt-1 text-xs font-medium text-slate-400">
                        Monthly billing
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 rounded-[1.5rem] border border-border/70 bg-white/[0.03] p-4">
                    <ul className="space-y-3 text-sm text-slate-200">
                      {plan.features.map((feature) => (
                        <li key={feature} className="flex gap-3">
                          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="mt-6 grid gap-2 rounded-[1.5rem] border border-border/70 bg-surface-muted/30 px-4 py-4 text-sm">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-slate-400">Students</span>
                      <span className="font-semibold text-white">
                        {formatLimitValue(plan.limits.students)}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-3 text-sm">
                      <span className="text-slate-400">Teachers</span>
                      <span className="font-semibold text-white">
                        {formatLimitValue(plan.limits.teachers)}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-3 text-sm">
                      <span className="text-slate-400">Classes</span>
                      <span className="font-semibold text-white">
                        {formatLimitValue(plan.limits.classes)}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-1 items-center justify-center pt-6">
                    <div className="w-full max-w-[19rem] text-center">
                      <Link
                        to={buildRegistrationHref(plan.planCode)}
                        onClick={() => handlePlanSelection(plan.planCode)}
                      >
                        <Button
                          variant={plan.highlighted ? "primary" : "outline"}
                          className={`w-full ${plan.highlighted ? "" : "border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.08]"}`}
                        >
                          {plan.ctaLabel}
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </Link>
                      <div className="mt-3 flex justify-center">
                        <span
                          className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                            plan.highlighted
                              ? "bg-accent-soft text-accent"
                              : "bg-surface-muted text-text-muted"
                          }`}
                        >
                          {plan.planCode === "free_trial"
                            ? "30-day trial"
                            : plan.name}
                        </span>
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section-container py-20">
          <div className="rounded-2xl border border-border bg-slate-950 px-6 py-12 text-center text-white shadow-premium sm:px-10">
            <ShieldCheck className="mx-auto h-10 w-10 text-primary-soft" />
            <h2 className="mt-5 text-4xl font-semibold tracking-tight text-white">
              Modernize school operations without losing control.
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-300">
              Give every role a cleaner workspace while preserving your backend model, tenant boundaries, and authentication flows.
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
            <p className="font-bold">Learnly AI</p>
            <p className="mt-1 text-sm text-text-muted">School management workspace.</p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm font-semibold text-text-muted">
            <a href="#features" className="hover:text-primary">Features</a>
            <a href="#benefits" className="hover:text-primary">Benefits</a>
            <a href="#pricing" className="hover:text-primary">Pricing</a>
            <Link to="/login" className="hover:text-primary">Log in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
