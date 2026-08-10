import { BookOpen, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "../../utils/cn";
import Badge from "../ui/Badge";
import Card from "../ui/Card";

const hasValue = (value) =>
  value !== undefined && value !== null && value !== "";

const cleanText = (value, fallback = "-") => {
  if (!hasValue(value)) return fallback;
  return String(value).replaceAll("_", " ");
};

const formatScore = (value) => {
  if (!hasValue(value)) return "--";
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return value;
  return Number.isInteger(numericValue) ? String(numericValue) : numericValue.toFixed(1);
};

const percentage = (value, max) => {
  const numericValue = Number(value);
  const numericMax = Number(max);
  if (!Number.isFinite(numericValue) || !Number.isFinite(numericMax) || numericMax <= 0) return 0;
  return Math.min(Math.max((numericValue / numericMax) * 100, 0), 100);
};

const statusVariant = (status) => {
  const value = String(status || "").toLowerCase();
  if (["submitted", "published", "locked", "complete", "active"].includes(value)) return "success";
  if (["failed", "rejected", "declined"].includes(value)) return "error";
  if (["draft", "pending", "in_progress", "incomplete"].includes(value)) return "warning";
  return "info";
};

const displayStatusLabel = (value, fallback = "Pending") => {
  const text = hasValue(value) ? String(value) : fallback;
  return text.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
};

const gradeTone = (grade) => {
  const value = String(grade || "").trim().toUpperCase();
  if (["A", "A+", "B", "B+"].includes(value)) return "text-emerald-600 border-emerald-400/70 bg-emerald-500/10";
  if (["C", "D"].includes(value)) return "text-amber-600 border-amber-400/70 bg-amber-500/10";
  if (["E", "F"].includes(value)) return "text-rose-600 border-rose-400/70 bg-rose-500/10";
  return "text-text-muted border-border bg-surface-muted/20";
};

const scoreTone = (score, max) => {
  const value = Number(score);
  const maximum = Number(max);
  if (!Number.isFinite(value) || !Number.isFinite(maximum) || maximum <= 0) return "text-primary";
  const ratio = value / maximum;
  if (ratio >= 0.7) return "text-emerald-500";
  if (ratio >= 0.5) return "text-amber-500";
  return "text-rose-500";
};

function ScoreRing({ value, max }) {
  const toneClass = scoreTone(value, max);
  const percent = percentage(value, max);
  return (
    <div className={cn("relative grid h-[4.85rem] w-[4.85rem] shrink-0 place-items-center rounded-full sm:h-24 sm:w-24", toneClass)}>
      <div
        className="absolute inset-0 rounded-full opacity-90"
        style={{
          background: hasValue(max)
            ? `conic-gradient(currentColor ${percent * 3.6}deg, rgba(148, 163, 184, 0.16) 0deg)`
            : "rgba(148, 163, 184, 0.12)",
        }}
      />
      <div className="absolute inset-2 rounded-full bg-surface" />
      <div className="relative text-center leading-none">
        <p className="text-lg font-semibold text-text sm:text-2xl">{formatScore(value)}</p>
        <p className="mt-1 text-[9px] font-medium text-text-muted sm:text-[10px]">
          {hasValue(max) ? `of ${formatScore(max)}` : "Limit pending"}
        </p>
      </div>
    </div>
  );
}

function ScoreBar({ label, value, max }) {
  const hasScoreValue = hasValue(value);
  const hasMaximum = hasValue(max);
  const percent = percentage(value, max);
  return (
    <div className="grid grid-cols-[3.4rem_minmax(0,1fr)_3.5rem] items-center gap-2 text-xs sm:grid-cols-[4.75rem_minmax(0,1fr)_4.25rem] sm:text-sm">
      <span className="truncate text-text-muted">{label}</span>
      <span className="h-1.5 overflow-hidden rounded-full bg-surface-muted/50 sm:h-2">
        {hasScoreValue && hasMaximum ? (
          <span className="block h-full rounded-full bg-current text-primary" style={{ width: `${percent}%` }} />
        ) : null}
      </span>
      <span className="text-right font-semibold text-text">
        {formatScore(value)}{hasMaximum ? `/${formatScore(max)}` : ""}
      </span>
    </div>
  );
}

function TeacherLine({ name }) {
  const teacherName = cleanText(name, "Teacher not assigned");
  const initials = teacherName.split(" ").filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "T";
  return (
    <div className="flex min-w-0 items-center gap-3 border-t border-dashed border-border/70 pt-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/70 bg-surface-muted/30 text-[11px] font-bold text-primary sm:h-9 sm:w-9 sm:text-xs">{initials}</span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted">Teacher</p>
        <p className="truncate text-sm font-semibold text-text">{teacherName}</p>
      </div>
    </div>
  );
}

function StudentSubjectPerformanceCard({ card, classLabel, compact = false }) {
  const subjectName = cleanText(card?.subject_name, "Subject");
  const statusLabel = displayStatusLabel(card?.status, card?.result_id ? "Pending" : "Awaiting marks");
  const grade = cleanText(card?.grade, "--").toUpperCase();
  const link = card?.id ? `/student/subjects/${card.id}` : undefined;
  const components = card?.components || [];
  const totalMax = card?.maximum_score ?? null;

  return (
    <Card
      as={link ? Link : "div"}
      to={link}
      className={cn(
        "group h-full overflow-hidden rounded-[1.45rem] border border-border/80 bg-surface text-left shadow-sm transition-all duration-200",
        link ? "hover:-translate-y-0.5 hover:border-border-strong hover:shadow-premium" : "cursor-default",
        compact ? "p-4" : "p-4 sm:p-5",
      )}
    >
      <div className="flex h-full flex-col gap-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] border border-border/70 bg-surface-muted/25 text-primary sm:h-12 sm:w-12">
              <BookOpen className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h3 className="text-lg font-semibold leading-tight text-text sm:text-xl">{subjectName}</h3>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                <span>{cleanText(card?.class_name || classLabel, "Class")}</span>
                <Badge variant={statusVariant(card?.status)} className="px-2 py-0.5 text-[11px]">{statusLabel}</Badge>
              </div>
            </div>
          </div>
          {link ? <ChevronRight className="mt-2 h-5 w-5 shrink-0 text-text-faint transition group-hover:translate-x-0.5" /> : <span className="mt-2 shrink-0 text-[11px] font-semibold text-text-faint">Pending</span>}
        </div>
        <div className="border-t border-dashed border-border/70" />
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 sm:gap-4">
          <ScoreRing value={card?.total_score} max={totalMax} />
          <div className="min-w-0 space-y-2">
            {components.map((component) => (
              <ScoreBar key={component.assessment_component_id} label={component.name} value={component.score} max={component.maximum_score} />
            ))}
          </div>
          <div className={cn("grid h-16 w-16 shrink-0 place-items-center rounded-full border text-center sm:h-20 sm:w-20", gradeTone(grade))}>
            <div>
              <p className="text-xl font-semibold leading-none sm:text-2xl">{grade}</p>
              <p className="mt-1 text-[9px] font-bold uppercase tracking-[0.14em] opacity-75 sm:text-[10px]">Grade</p>
            </div>
          </div>
        </div>
        {components.length === 0 ? (
          <p className="rounded-xl bg-warning-soft px-3 py-2 text-xs text-amber-900">An assessment scheme has not been configured by the school.</p>
        ) : null}
        <TeacherLine name={card?.teacher_name} />
      </div>
    </Card>
  );
}

export default StudentSubjectPerformanceCard;
