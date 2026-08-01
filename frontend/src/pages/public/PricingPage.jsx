import { Link } from "react-router-dom";
import { HelpCircle, ShieldCheck } from "lucide-react";

import WeaveIcon from "../../components/brand/WeaveIcon";
import Navbar from "../../components/layout/Navbar";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import {
  LANDING_PRICING_PLANS,
  formatLimitValue,
} from "../../features/subscriptions/subscriptionConfig";

const comparisonRows = [
  ["Students", (plan) => formatLimitValue(plan.limits.students)],
  ["Teachers", (plan) => formatLimitValue(plan.limits.teachers)],
  ["Parents", (plan) => formatLimitValue(plan.limits.parents)],
  ["Classes", (plan) => formatLimitValue(plan.limits.classes)],
  ["Subjects", (plan) => formatLimitValue(plan.limits.subjects)],
  ["Bulk import", (plan) => plan.features.some((feature) => /bulk import/i.test(feature)) ? "Included" : "—"],
  ["Advanced analytics", (plan) => plan.features.some((feature) => /advanced analytics/i.test(feature)) ? "Included" : "—"],
  ["AI assistant", (plan) => plan.features.some((feature) => /ai assistant/i.test(feature)) ? "Included" : "—"],
  ["Parent portal", (plan) => plan.planCode === "free_trial" ? "Limited" : "Included"],
  ["Support", (plan) => plan.planCode === "enterprise" ? "Priority" : "Standard"],
];

const faqs = [
  ["Can I start free?", "Yes. Schools can begin with the Free Trial and move to a paid plan when they are ready."],
  ["Does bulk import work on every plan?", "Bulk import is available on paid plans. It uses backend-generated XLSX templates and dry-run validation before creating records."],
  ["Can I upgrade later?", "Yes. Tenant admins can open billing from the dashboard and move to a higher plan when school usage grows."],
  ["Are limits tenant-scoped?", "Yes. Limits are evaluated per school tenant so one school cannot leak into another school's capacity."],
];

function PricingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-background text-text">
      <Navbar />
      <main>
        <section className="relative overflow-hidden border-b border-border bg-slate-950 text-white">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.24),transparent_34%),radial-gradient(circle_at_top_right,rgba(168,85,247,0.2),transparent_32%),linear-gradient(180deg,rgba(15,23,42,1),rgba(15,23,42,0.94))]" />
          <div className="section-container relative py-16 sm:py-20 lg:py-24">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)] lg:items-center">
              <div>
                <Badge variant="primary">Pricing</Badge>
                <h1 className="mt-5 max-w-4xl text-balance text-4xl font-semibold leading-tight tracking-tight text-white sm:text-6xl">
                  Choose the plan that matches your school growth.
                </h1>
                <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
                  Start small, validate the workflow, then move into higher limits, bulk imports, analytics, and AI support as your school expands.
                </p>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <a href="#compare" className="w-full sm:w-auto">
                    <Button size="large" className="w-full sm:w-auto">Compare features</Button>
                  </a>
                  <Link to="/#pricing" className="w-full sm:w-auto">
                    <Button variant="outline" size="large" className="w-full border-white/15 bg-white/10 text-white hover:bg-white/15">View plans</Button>
                  </Link>
                </div>
              </div>
              <Card className="border-white/10 bg-white/10 p-5 text-white backdrop-blur-xl">
                <WeaveIcon className="mx-auto h-20 w-20" decorative />
                <h2 className="mt-4 text-xl font-semibold text-white">Pay for the capacity you need.</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  Free Trial proves the product. Paid plans unlock higher limits and operational features like bulk import and advanced analytics.
                </p>
                <div className="mt-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                  {["Dry-run imports", "Tenant limits", "Safe billing"].map((item) => (
                    <div key={item} className="rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm font-semibold">
                      {item}
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </section>

        <section id="compare" className="border-y border-border bg-surface">
          <div className="section-container py-16">
            <div className="mx-auto max-w-3xl text-center">
              <p className="text-sm font-bold uppercase tracking-wide text-primary">Compare</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-5xl">Feature limits without guessing.</h2>
              <p className="mt-4 text-sm leading-6 text-text-muted">The desktop view uses a comparison grid. On mobile, each feature stacks cleanly without breaking the layout.</p>
            </div>
            <div className="mt-10 overflow-hidden rounded-[1.75rem] border border-border bg-background shadow-soft-card">
              <div className="hidden min-w-[760px] grid-cols-[1.2fr_repeat(4,1fr)] border-b border-border bg-surface-muted/30 px-5 py-4 text-sm font-semibold md:grid">
                <span>Feature</span>
                {LANDING_PRICING_PLANS.map((plan) => <span key={plan.planCode}>{plan.name}</span>)}
              </div>
              <div className="divide-y divide-border">
                {comparisonRows.map(([label, resolver]) => (
                  <div key={label} className="grid gap-3 px-5 py-4 md:min-w-[760px] md:grid-cols-[1.2fr_repeat(4,1fr)] md:items-center">
                    <p className="text-sm font-semibold text-text">{label}</p>
                    {LANDING_PRICING_PLANS.map((plan) => (
                      <div key={`${label}-${plan.planCode}`} className="flex items-center justify-between rounded-xl bg-surface-muted/30 px-3 py-2 text-sm md:block md:bg-transparent md:px-0 md:py-0">
                        <span className="text-xs font-semibold text-text-muted md:hidden">{plan.name}</span>
                        <span>{resolver(plan)}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="section-container py-16">
          <div className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr] lg:items-start">
            <div>
              <HelpCircle className="h-8 w-8 text-primary" />
              <h2 className="mt-4 text-3xl font-semibold tracking-tight">Common questions</h2>
              <p className="mt-3 text-sm leading-6 text-text-muted">Simple answers for schools comparing plan capacity and billing behavior.</p>
            </div>
            <div className="grid gap-3">
              {faqs.map(([question, answer]) => (
                <Card key={question} className="p-5">
                  <h3 className="font-semibold">{question}</h3>
                  <p className="mt-2 text-sm leading-6 text-text-muted">{answer}</p>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="section-container pb-16">
          <div className="rounded-[2rem] border border-border bg-slate-950 px-6 py-12 text-center text-white shadow-premium sm:px-10">
            <ShieldCheck className="mx-auto h-10 w-10 text-primary-soft" />
            <h2 className="mt-5 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Start with a safe workspace.</h2>
            <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-slate-300">Create a tenant, test the core school flow, and upgrade only when the school needs more capacity.</p>
            <Link to="/#pricing" className="mt-8 inline-flex">
              <Button size="large">View plans</Button>
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}

export default PricingPage;
