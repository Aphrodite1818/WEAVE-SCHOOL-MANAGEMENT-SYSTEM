import { ArrowRight, CalendarDays } from "lucide-react";
import Button from "../ui/Button";

export default function GettingStartedBanner({ guide, onContinue, onDismiss }) {
  if (!guide?.config) return null;
  return <section className="flex flex-col gap-5 rounded-2xl border border-border bg-surface p-6 sm:flex-row sm:items-center sm:justify-between">
    <div className="flex items-start gap-4"><CalendarDays className="mt-1 h-6 w-6 shrink-0 text-primary" /><div><h2 className="text-base font-semibold text-text">Set up your school year</h2><p className="mt-2 text-sm leading-6 text-text-muted">Your school-year setup is incomplete. Continue with your session, term, and calendar when you are ready.</p></div></div>
    <div className="flex shrink-0 gap-2">{onDismiss ? <Button variant="ghost" onClick={onDismiss}>Do not show again</Button> : null}<Button onClick={onContinue}>Continue<ArrowRight className="h-4 w-4" /></Button></div>
  </section>;
}
