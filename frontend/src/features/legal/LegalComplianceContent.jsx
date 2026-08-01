import { CheckCircle2, ShieldCheck } from "lucide-react";

import {
  getRoleLegalCompliance,
  legalComplianceChecklist,
  legalComplianceSections,
} from "./legalComplianceCopy";

function LegalComplianceContent({ compact = false, role = "admin" }) {
  const roleTerms = getRoleLegalCompliance(role);

  return (
    <div className={compact ? "space-y-5" : "space-y-6"}>
      <section className="rounded-2xl border border-primary/20 bg-primary-subtle/60 p-4">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-base font-semibold text-text">
              Weave Legal And Compliance Terms
            </h2>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              These terms explain how Weave should be used by your role:
              {" "}
              <span className="font-semibold text-text">{roleTerms.label}</span>.
            </p>
          </div>
        </div>
      </section>

      <div className="space-y-4">
        {legalComplianceSections.map((section) => (
          <section key={section.title}>
            <h3 className="text-sm font-semibold text-text">{section.title}</h3>
            <p className="mt-1 text-sm leading-6 text-text-muted">{section.body}</p>
          </section>
        ))}
      </div>

      <section className="rounded-2xl border border-primary/20 bg-primary-subtle/30 p-4">
        <h3 className="text-sm font-semibold text-text">
          Role-Specific Terms: {roleTerms.label}
        </h3>
        <div className="mt-4 space-y-4">
          {roleTerms.sections.map((section) => (
            <section key={section.title}>
              <h4 className="text-sm font-semibold text-text">{section.title}</h4>
              {section.body ? (
                <p className="mt-1 text-sm leading-6 text-text-muted">{section.body}</p>
              ) : null}
              {section.items ? (
                <ul className="mt-2 space-y-2">
                  {section.items.map((item) => (
                    <li key={item} className="flex gap-2 text-sm leading-6 text-text-muted">
                      <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-success" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-surface-muted/40 p-4">
        <h3 className="text-sm font-semibold text-text">Before You Accept</h3>
        <ul className="mt-3 space-y-2">
          {[...legalComplianceChecklist, ...roleTerms.checklist].map((item) => (
            <li key={item} className="flex gap-2 text-sm leading-6 text-text-muted">
              <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-success" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default LegalComplianceContent;
