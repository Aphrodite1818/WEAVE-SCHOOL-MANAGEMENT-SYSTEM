import { BookOpen, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "../../utils/cn";
import Badge from "../ui/Badge";
import Card from "../ui/Card";

const DEFAULT_LIMITS = {
  test_max: 20,
  assessment_max: 20,
  exam_max: 60,
};

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
  return Number.isInteger(numericValue)
    ? String(numericValue)
    : numericValue.toFixed(1);
};

const percentage = (value, maximum) => {
  const numericValue = Number(value);
  const numericMaximum = Number(maximum);
  if (!Number.isFinite(numericValue) || !Number.isFinite(numericMaximum) || numericMaximum <= 0) {
    return 0;
  }
  return Math.min(Math.max((numericValue / numericMaximum) * 100, 0), 100);
};

const assessmentLimits = (card) => ({
  test_max: Number(card?.test_max ?? card?.assessment_config?.test_max ?? DEFAULT_LIMITS.test_max),
  assessment_max: Number(
    card?.assessment_max ??
      card?.assessment_config?.assessment_max ??
      DEFAULT_LIMITS.assessment_max,
  ),
  exam_max: Number(card?.exam_max ?? card?.assessment_config?.exam_max ?? DEFAULT_LIMITS.exam_max),
});

const statusVariant = (status) => {
  const value = String(status || "").toLowerCase();
  if (
    ["submitted", "published", "locked", "complete", "active"].includes(value)
  )
    return "success";
  if (["failed", "rejected", "declined"].includes(value)) return "error";
  if (["draft", "pending", "in_progress", "incomplete"].includes(value))
    return "warning";
  return "info";
};

const displayStatusLabel = (value, fallback = "Pending") => {
  const text = hasValue(value) ? String(value) : fallback;
  return text
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const gradeTone = (grade) => {
  const value = String(grade || "")
    .trim()
    .toUpperCase();
  if (["A", "A+", "B", "B+"].includes(value))
    return "text-emerald-600 border-emerald-400/70 bg-emerald-500/10";
  if (["C", "D"].includes(value))
    return "text-amber-600 border-amber-400/70 bg-amber-500/10";
  if (["E", "F"].includes(value))
    return "text-rose-600 border-rose-400/70 bg-rose-500/10";
  return "text-text-muted border-border bg-surface-muted/20";
};

const scoreTone = (score) => {
  const value = Number(score);
  if (!Number.isFinite(value)) return "text-primary";
  if (value >= 70) return "text-emerald-500";
  if (value >= 50) return "text-amber-500";
  return "text-rose-500";
};

function ScoreRing({ value, maximum }) {
  const score = Number(value);
  const toneClass = scoreTone(score);

  return (
    <div
      className={cn(
        "relative grid h-[4.85rem] w-[4.85rem] shrink-0 place-items-center rounded-full sm:h-24 sm:w-24",
        toneClass,
      )}
    >
      <div
        className="absolute inset-0 rounded-full opacity-90"
        style={{
          background: `conic-gradient(currentColor ${percentage(value, maximum) * 3.6}deg, rgba(148, 163, 184, 0.16) 0deg)`,
        }}
      />
      <div className="absolute inset-2 rounded-full bg-surface" />
      <div className="relative text-center leading-none">
        <p className="text-lg font-semibold text-text sm:text-2xl">
          {formatScore(value)}
        </p>
        <p className="mt-1 text-[9px] font-medium text-text-muted sm:text-[10px]">
          of {formatScore(maximum)}
        </p>
      </div>
    </div>
  );
}

function ScoreBar({ label, value, maximum }) {
  const hasScoreValue = hasValue(value);

  return (
    <div className="grid grid-cols-[3.4rem_minmax(0,1fr)_3.3rem] items-center gap-2 text-xs sm:grid-cols-[4.75rem_minmax(0,1fr)_4rem] sm:text-sm">
      <span className="truncate text-text-muted">{label}</span>
      <span className="h-1.5 overflow-hidden rounded-full bg-surface-muted/50 sm:h-2">
        {hasScoreValue && (
          <span
            className="block h-full rounded-full bg-current text-primary transition-all"
            style={{ width: `${percentage(value, maximum)}%` }}
          />
        )}
      </span>
      <span className="text-right font-semibold text-text">
        {formatScore(value)}/{formatScore(maximum)}
      </span>
    </div>
  );
}

function TeacherLine({ name }) {
  const teacherName = cleanText(name, "Teacher not assigned");
  const initials =
    teacherName
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "T";

  return (
    <div className="flex min-w-0 items-center gap-3 border-t border-dashed border-border/70 pt-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/70 bg-surface-muted/30 text-[11px] font-bold text-primary sm:h-9 sm:w-9 sm:text-xs">
        {initials}
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted">
          Teacher
        </p>
        <p className="truncate text-sm font-semibold text-text">
          {teacherName}
        </p>
      </div>
    </div>
  );
}

function StudentSubjectPerformanceCard({ card, classLabel, compact = false }) {
  const subjectName = cleanText(card?.subject_name, "Subject");
  const statusLabel = displayStatusLabel(
    card?.status,
    card?.result_id ? "Pending" : "Awaiting marks",
  );
  const grade = cleanText(card?.grade, "--").toUpperCase();
  const link = card?.result_id
    ? `/student/subjects/${card.result_id}`
    : undefined;
  const limits = assessmentLimits(card);
  const totalMaximum = limits.test_max + limits.assessment_max + limits.exam_max;

  return (
    <Card
      as={link ? Link : "div"}
      to={link}
      className={cn(
        "group h-full overflow-hidden rounded-[1.45rem] border border-border/80 bg-surface text-left shadow-sm transition-all duration-200",
        link
          ? "hover:-translate-y-0.5 hover:border-border-strong hover:shadow-premium"
          : "cursor-default",
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
              <h3 className="text-lg font-semibold leading-tight text-text sm:text-xl">
                {subjectName}
              </h3>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                <span>{cleanText(card?.class_name || classLabel, "Class")}</span>
                <Badge
                  variant={statusVariant(card?.status)}
                  className="px-2 py-0.5 text-[11px]"
                >
                  {statusLabel}
                </Badge>
              </div>
            </div>
          </div>
          {link ? (
            <ChevronRight className="mt-2 h-5 w-5 shrink-0 text-text-faint transition group-hover:translate-x-0.5" />
          ) : (
            <span className="mt-2 shrink-0 text-[11px] font-semibold text-text-faint">
              Pending
            </span>
          )}
        </div>

        <div className="border-t border-dashed border-border/70" />

        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 sm:gap-4">
          <ScoreRing value={card?.total_score} maximum={totalMaximum} />
          <div className="min-w-0 space-y-2">
            <ScoreBar label="Test" value={card?.test_score} maximum={limits.test_max} />
            <ScoreBar label="Assess." value={card?.assessment_score} maximum={limits.assessment_max} />
            <ScoreBar label="Exam" value={card?.exam_score} maximum={limits.exam_max} />
          </div>
          <div
            className={cn(
              "grid h-16 w-16 shrink-0 place-items-center rounded-full border text-center sm:h-20 sm:w-20",
              gradeTone(grade),
            )}
          >
            <div>
              <p className="text-xl font-semibold leading-none sm:text-2xl">
                {grade}
              </p>
              <p className="mt-1 text-[9px] font-bold uppercase tracking-[0.14em] opacity-75 sm:text-[10px]">
                Grade
              </p>
            </div>
          </div>
        </div>

        <TeacherLine name={card?.teacher_name} />
      </div>
    </Card>
  );
}

export default StudentSubjectPerformanceCard;
