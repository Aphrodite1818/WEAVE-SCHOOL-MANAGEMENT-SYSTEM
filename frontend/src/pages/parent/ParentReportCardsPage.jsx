import { useEffect, useMemo, useState } from "react";
import { ChevronDown, FileText, Printer } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { getErrorMessage } from "../../services/api";
import { reportCardService } from "../../services/reportCardService";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";
import ParentChildSelector from "./ParentChildSelector";
import useParentChildren from "./useParentChildren";

function asStatus(value) {
  return String(value || "").trim().toLowerCase();
}

function statusVariant(status) {
  const normalized = asStatus(status);
  if (normalized === "published") return "success";
  if (normalized === "draft") return "warning";
  if (normalized === "locked") return "info";
  return "default";
}

function ParentReportCardsPage() {
  const {
    children,
    selectedChildId,
    selectedChildRecord,
    setSelectedChildId,
    isLoading,
    loadError,
    setLoadError,
  } = useParentChildren();
  const [reportCards, setReportCards] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [isLoadingCards, setIsLoadingCards] = useState(false);
  const [printId, setPrintId] = useState(null);

  const selectedChildAcademicLabel = useMemo(() => {
    const latestCard = reportCards[0];
    const session = latestCard?.academic_session_name;
    const term = latestCard?.academic_term_name;
    return [session, cleanText(term, "")].filter(Boolean).join(" / ") || "-";
  }, [reportCards]);

  useEffect(() => {
    let mounted = true;

    async function loadReportCards() {
      if (!selectedChildId) {
        setReportCards([]);
        setExpandedId(null);
        return;
      }

      setIsLoadingCards(true);

      try {
        const response = await reportCardService.listChildReportCards(selectedChildId);
        if (!mounted) return;
        setReportCards(response?.items || []);
        setExpandedId(null);
      } catch (error) {
        if (!mounted) return;
        setReportCards([]);
        setLoadError(getErrorMessage(error, "Failed to load report cards."));
      } finally {
        if (mounted) setIsLoadingCards(false);
      }
    }

    loadReportCards();

    return () => {
      mounted = false;
    };
  }, [selectedChildId, setLoadError]);

  const printReportCard = async (card) => {
    setPrintId(card.id);
    setLoadError(null);

    try {
      await reportCardService.printParentReportCard(selectedChildId, card.id);
    } catch (error) {
      setLoadError(getErrorMessage(error, "Could not open report card."));
    } finally {
      setPrintId(null);
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout role="parent" title="Report Cards">
        <LoadingState label="Loading report cards..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="parent"
      title="Report Cards"
      description="Published term reports for the selected child, with print and download available."
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      <Card className="p-5 sm:p-6">
        <ParentChildSelector
          linkedChildren={children}
          selectedChildId={selectedChildId}
          onSelectChild={setSelectedChildId}
          academicLabel={selectedChildAcademicLabel}
          showCards={false}
        />
      </Card>

      {!selectedChildRecord && (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={FileText}
            title="Select a linked child"
            description="Choose an approved student to view their published report cards."
          />
        </Card>
      )}

      {selectedChildRecord && isLoadingCards && (
        <LoadingState label="Loading report cards..." />
      )}

      {selectedChildRecord && !isLoadingCards && reportCards.length === 0 && (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={FileText}
            title="No report cards available"
            description="Published report cards will appear here when the school releases them."
          />
        </Card>
      )}

      {selectedChildRecord && !isLoadingCards && reportCards.length > 0 && (
        <section className="space-y-4">
          {reportCards.map((card) => {
            const isPublished = asStatus(card.status) === "published";
            const isExpanded = expandedId === card.id;
            const subjectCount = Array.isArray(card.lines) ? card.lines.length : 0;

            return (
              <Card key={card.id} className="overflow-hidden p-5 sm:p-6">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <button
                    type="button"
                    onClick={() => setExpandedId((current) => (current === card.id ? null : card.id))}
                    className="flex min-w-0 flex-1 items-start gap-4 text-left"
                  >
                    <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[1.25rem] border border-border/70 bg-surface-muted/25 text-primary">
                      <FileText className="h-6 w-6" />
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="block text-lg font-semibold text-text">
                        {cleanText(card.academic_session_name, "Session")} /{" "}
                        {cleanText(card.academic_term_name, "Term")}
                      </span>
                      <span className="mt-1 block text-sm text-text-muted">
                        {subjectCount} subject{subjectCount === 1 ? "" : "s"} / average{" "}
                        {cleanText(card.average_score)}
                        {card.position ? ` / position ${card.position}` : ""}
                      </span>
                    </span>

                    <ChevronDown
                      className={cn(
                        "mt-1 h-4 w-4 shrink-0 text-text-faint transition",
                        isExpanded && "rotate-180 text-primary"
                      )}
                    />
                  </button>

                  <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                    <Badge variant={statusVariant(card.status)}>{cleanText(card.status)}</Badge>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setExpandedId((current) => (current === card.id ? null : card.id))}
                    >
                      {isExpanded ? "Hide details" : "View details"}
                    </Button>
                    <Button
                      type="button"
                      disabled={!isPublished || printId === card.id}
                      onClick={() => printReportCard(card)}
                    >
                      <Printer className="h-4 w-4" />
                      {printId === card.id ? "Opening..." : "Print or download"}
                    </Button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-5 border-t border-border pt-5">
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Average</p>
                        <p className="mt-2 text-xl font-semibold text-text">
                          {cleanText(card.average_score)}
                        </p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Subjects</p>
                        <p className="mt-2 text-xl font-semibold text-text">{subjectCount}</p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Position</p>
                        <p className="mt-2 text-xl font-semibold text-text">
                          {cleanText(card.position, "-")}
                        </p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Status</p>
                        <p className="mt-2 text-xl font-semibold text-text">
                          {cleanText(card.status)}
                        </p>
                      </div>
                    </div>

                    {subjectCount === 0 ? (
                      <p className="mt-4 text-sm text-text-muted">
                        No subject lines are attached to this report card.
                      </p>
                    ) : (
                      <div className="mt-4 overflow-x-auto rounded-[1.25rem] border border-border bg-surface">
                        <table className="w-full text-left text-sm text-text">
                          <thead className="border-b border-border bg-surface-muted/30 text-xs uppercase tracking-wide text-text-muted">
                            <tr>
                              <th className="px-4 py-3 font-semibold">Subject</th>
                              <th className="px-4 py-3 text-center font-semibold">Test</th>
                              <th className="px-4 py-3 text-center font-semibold">Assmt</th>
                              <th className="px-4 py-3 text-center font-semibold">Exam</th>
                              <th className="px-4 py-3 text-center font-semibold">Total</th>
                              <th className="px-4 py-3 text-center font-semibold">Grade</th>
                              <th className="px-4 py-3 text-right font-semibold">Remark</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/60">
                            {card.lines.map((line) => (
                              <tr key={line.id} className="transition hover:bg-surface-muted/30">
                                <td className="px-4 py-3">
                                  <p className="font-semibold text-text">{cleanText(line.subject_name, "Subject")}</p>
                                  <p className="text-[11px] text-text-muted">Teacher: {cleanText(line.teacher_name)}</p>
                                </td>
                                <td className="px-4 py-3 text-center font-medium">{cleanText(line.test_score, "-")}</td>
                                <td className="px-4 py-3 text-center font-medium">{cleanText(line.assessment_score, "-")}</td>
                                <td className="px-4 py-3 text-center font-medium">{cleanText(line.exam_score, "-")}</td>
                                <td className="px-4 py-3 text-center font-bold text-primary">{cleanText(line.total_score, "-")}</td>
                                <td className="px-4 py-3 text-center">
                                  <Badge variant="info" className="px-2 py-0.5">{cleanText(line.grade, "-")}</Badge>
                                </td>
                                <td className="px-4 py-3 text-right text-xs font-medium text-text-soft">{cleanText(line.remark, "-")}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </section>
      )}
    </DashboardLayout>
  );
}

export default ParentReportCardsPage;
