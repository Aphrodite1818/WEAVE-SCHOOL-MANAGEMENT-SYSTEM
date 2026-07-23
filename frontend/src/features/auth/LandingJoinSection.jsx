import { Building2, CheckCircle2, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import Button from "../../components/ui/Button";
import AccountRegistrationForm from "./AccountRegistrationForm";

const benefits = [
  "One account can connect to multiple invited schools.",
  "School access remains isolated by membership.",
  "Email verification is required before invitation acceptance.",
];

function LandingJoinSection() {
  return (
    <section id="join" className="scroll-mt-24 border-b border-border bg-surface">
      <div className="section-container py-10 sm:py-14 lg:py-16">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,0.82fr)_minmax(420px,1.18fr)] lg:items-start">
          <div className="lg:sticky lg:top-28">
            <p className="text-xs font-bold uppercase tracking-wide text-primary">
              Join Weave
            </p>
            <h2 className="mt-3 max-w-xl text-3xl font-semibold tracking-tight text-text sm:text-4xl">
              Create your teacher or parent account.
            </h2>
            <p className="mt-4 max-w-xl text-base leading-7 text-text-muted">
              Teachers and parents create personal accounts first. A school invitation then creates the membership that gives access to that school workspace.
            </p>

            <div className="mt-6 space-y-3">
              {benefits.map((benefit) => (
                <div key={benefit} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                  <p className="text-sm leading-6 text-text-soft">{benefit}</p>
                </div>
              ))}
            </div>

            <div className="mt-7 rounded-2xl border border-border/70 bg-background p-4 sm:p-5">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Building2 className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="font-semibold text-text">Running a school?</p>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    School administrators create a separate tenant workspace and choose a subscription plan.
                  </p>
                  <Link to="/register" className="mt-3 inline-flex">
                    <Button type="button" variant="outline" size="small">
                      Create school workspace
                    </Button>
                  </Link>
                </div>
              </div>
            </div>

            <div className="mt-4 flex items-start gap-3 rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-3">
              <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <p className="text-xs leading-5 text-text-muted">
                Students do not self-register. Their school provides an admission number and first-login access code.
              </p>
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-border/70 bg-background p-4 shadow-premium sm:p-6 lg:p-7">
            <AccountRegistrationForm role="teacher" allowRoleSwitch />
          </div>
        </div>
      </div>
    </section>
  );
}

export default LandingJoinSection;
