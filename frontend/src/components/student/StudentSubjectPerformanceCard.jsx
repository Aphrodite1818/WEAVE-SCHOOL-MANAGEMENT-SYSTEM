import { Link } from "react-router-dom";
import { BookOpen, ChevronRight } from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import { cn } from "../../utils/cn";

const SCORE_MAXIMUMS = {
  test_score: 20,
  assessment_score: 10,
  exam_score: 10,
  total_score: 40,
};

const hasValue = (value) => value !== undefined && value !== null && value !== "";

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
  if (!Number.isFinite(numericValue) || max <= 0) return 0;
  return Math.min(Math.max((numericValue / max) * 100, 0), 100);
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
  if (["A", "B", "B+", "A+"].includes(value)) return "text-emerald-600 border-emerald-400/70 bg-emerald-500/10";
  if (["C", "D"].includes(value)) return "text-amber-600 border-amber-400/70 bg-amber-500/10";
  if (["E", "F"].includes(value)) return "text-rose-600 border-rose-400/70 bg-rose-500/10";
  return "text-text-muted border-border bg-surface-muted/20";
};

const scoreTone = (score) => {
  const value = Number(score);
  if (!Number.isFinite(value)) return "text-primary";
  if (value >= 30) return "text-emerald-500";
  if (value >= 20) return "text-amber-500";
  return "text-rose-500";
};

function ScoreRing({ value }) {
  const score = Number(value);
  const percent = percentage(value, SCORE_MAXIMUMS.total_score);
  const toneClass = scoreTone(score);

  return (
    <div className={cn("relative grid h-20 w-20 shrink-0 place-items-center rounded-full sm:h-24 sm:w-24", toneClass)}>
      <div
        className="absolute inset-0 rounded-full opacity-90"
        style={{
          background: `conic-gradient(currentColor ${percent * 3.6}deg, rgba(148, 163, 184, 0.16) 0deg)`,
        }}
      />
      <div className="absolute inset-2 rounded-full bg-surface" />
      <div className="relative text-center leading-none">
        <p className="text-xl font-semibold text-text sm:text-2xl">{formatScore(value)}</p>
        <p className="mt-1 text-[10px] font-medium text-text-muted">of {SCORE_MAXIMUMS.total_score}</p>
      </div>
    </div>
  );
}

function ScoreBar({ label, value, max }) {
  const percent = percentage(value, max);

  return (
    <div className="grid grid-cols-[4.25rem_minmax(0,1fr)_3.25rem] items-center gap-2 text-sm sm:grid-cols-[4.75rem_minmax(0,1fr)_3.5rem]">
      <span className="truncate text-text-muted">{label}</span>
      <span className="h-2 overflow-hidden rounded-full bg-surface-muted/50">
        <span
          className="block h-full rounded-full bg-current text-primary transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </span>
      <span className="text-right font-semibold text-text">
        {formatScore(value)}/{max}
      </span>
    </div>
  );
}

function TeacherLine({ name }) {
  const teacherName = cleanText(name, "Teacher not assigned");
  const initials = teacherName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "T";

  return (
    <div className="flex min-w-0 items-center gap-3 border-t border-dashed border-border/70 pt-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border/70 bg-surface-muted/30 text-xs font-bold text-primary">
        {initials}
      </span>
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
  const link = card?.result_id ? `/student/subjects/${card.result_id}` : undefined;

  return (
    <Card
      as={link ? Link : "div"}
      to={link}
      className={cn(
        "group h-full overflow-hidden rounded-[1.5rem] border border-border/80 bg-surface text-left shadow-sm transition-all duration-200",
        link ? "hover:-translate-y-0.5 hover:border-border-strong hover:shadow-premium" : "cursor-default",
        compact ? "p-4" : "p-5 sm:p-6"
      )}
    >
      <div className="flex h-full flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[1.1rem] border border-border/70 bg-surface-muted/25 text-primary">
              <BookOpen className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h3 className="text-lg font-semibold leading-tight text-text sm:text-xl">{subjectName}</h3>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                <span>{cleanText(card?.class_name || classLabel, "Class")}</span>
                <Badge variant={statusVariant(card?.status)} className="px-2 py-0.5 text-[11px]">
                  {statusLabel}
                </Badge>
              </div>
            </div>
          </div>
          {link ? (
            <ChevronRight className="mt-2 h-5 w-5 shrink-0 text-text-faint transition group-hover:translate-x-0.5" />
          ) : (
            <span className="mt-2 shrink-0 text-[11px] font-semibold text-text-faint">Pending</span>
          )}
        </div>

        <div className="border-t border-dashed border-border/70" />

        <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-4 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
          <ScoreRing value={card?.total_score} />
          <div className="min-w-0 space-y-2.5">
            <ScoreBar label="Test" value={card?.test_score} max={SCORE_MAXIMUMS.test_score} />
            <ScoreBar label="Assess." value={card?.assessment_score} max={SCORE_MAXIMUMS.assessment_score} />
            <ScoreBar label="Exam" value={card?.exam_score} max={SCORE_MAXIMUMS.exam_score} />
          </div>
          <div className={cn("col-span-2 grid h-20 w-full place-items-center rounded-full border text-center sm:col-span-1 sm:h-20 sm:w-20", gradeTone(grade))}>
            <div>
              <p className="text-2xl font-semibold leading-none">{grade}</p>
              <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] opacity-75">Grade</p>
            </div>
          </div>
        </div>

        <TeacherLine name={card?.teacher_name} />
      </div>
    </Card>
  );
}

export default StudentSubjectPerformanceCard;
