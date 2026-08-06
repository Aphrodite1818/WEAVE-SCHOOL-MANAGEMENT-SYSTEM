import {
  CalendarDays,
  CalendarPlus,
  History,
  Info,
  Settings2,
  ShieldAlert,
} from "lucide-react";

const tabGuides = {
  overview: {
    icon: Info,
    title: "Calendar overview",
    summary:
      "See whether the selected term calendar is ready, active, complete, and safe to use across school operations.",
    points: [
      "Use this page to understand status and readiness, not to edit individual dates.",
      "Missing means a date inside the term has no calendar-day record.",
      "Invalid means a day has conflicting rules, such as attendance being required while school is closed.",
    ],
  },
  setup: {
    icon: Settings2,
    title: "Set the normal school pattern",
    summary:
      "Choose the academic session and term, define normal weekdays and operating hours, then generate the term calendar.",
    points: [
      "Setup defines the default pattern used to generate every date in the term.",
      "Regenerating refreshes generated dates while preserving manual day overrides.",
      "Review the generated calendar before activation.",
    ],
  },
  calendar: {
    icon: CalendarDays,
    title: "Review and edit individual days",
    summary:
      "Each tile represents one operational school day. Select a tile only when you need to override that specific date.",
    points: [
      "Clicking a tile opens the Day Editor; it does not create an event.",
      "Use the editor to change whether school is open, operating hours, attendance requirements, or the type of day.",
      "Use Events for scheduled activities and Closures for closing a continuous date range.",
    ],
  },
  events: {
    icon: CalendarPlus,
    title: "Manage scheduled school activities",
    summary:
      "Events describe something happening on a date or time, such as a PTA meeting, examination, sports day, or graduation.",
    points: [
      "An event does not automatically close the school or disable attendance.",
      "Events can be drafted, edited, published, and cancelled.",
      "Change the underlying day separately when the event also affects school operations.",
    ],
  },
  closures: {
    icon: ShieldAlert,
    title: "Close school operations for a date range",
    summary:
      "Closures are operational overrides used when the school must not operate normally, such as flooding, elections, or an emergency.",
    points: [
      "A closure changes the affected calendar days to closed operational days.",
      "Use this page for one or more consecutive dates instead of editing tiles individually.",
      "Use Events when school remains open and you only need to announce an activity.",
    ],
  },
  history: {
    icon: History,
    title: "Review calendar changes",
    summary:
      "History is the audit trail showing what changed, who changed it, and why. It does not modify the live calendar.",
    points: [
      "Use history to investigate configuration, generation, activation, closure, day-edit, and event actions.",
      "The live calendar remains on the Calendar tab.",
      "This view will become fully populated when the audit-read endpoint is exposed.",
    ],
  },
};

function SchoolCalendarGuide({ activeTab }) {
  const guide = tabGuides[activeTab] || tabGuides.calendar;
  const Icon = guide.icon;

  return (
    <section
      className="rounded-2xl border border-primary/20 bg-primary-subtle/30 p-4 sm:p-5"
      aria-labelledby="calendar-guide-title"
    >
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-primary">
            What this page does
          </p>
          <h2 id="calendar-guide-title" className="mt-1 text-base font-semibold text-text sm:text-lg">
            {guide.title}
          </h2>
          <p className="mt-1 text-sm leading-6 text-text-muted">{guide.summary}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {guide.points.map((point) => (
          <div key={point} className="rounded-xl border border-border/70 bg-surface/80 px-3 py-3 text-sm text-text-muted">
            {point}
          </div>
        ))}
      </div>
    </section>
  );
}

export default SchoolCalendarGuide;
