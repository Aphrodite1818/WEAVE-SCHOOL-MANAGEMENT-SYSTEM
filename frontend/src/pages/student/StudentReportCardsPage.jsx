import { useEffect, useMemo, useState } from "react";
import { ChevronDown, FileText, Printer } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import ReportCardLinesTable from "../../components/shared/ReportCardLinesTable";
import ReportCardPrintSheet from "../../components/shared/ReportCardPrintSheet";
import ReportCardPeriodFilters from "../../components/shared/ReportCardPeriodFilters";
import { filterReportCardsByPeriod } from "../../utils/reportCardPeriodFilters";
import { getErrorMessage } from "../../services/api";
import { reportCardService } from "../../services/reportCardService";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";
import { asStatus, statusVariant } from "./studentPageUtils";

function StudentReportCardsPage() {
  const [reportCards, setReportCards] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [printId, setPrintId] = useState(null);
  const [printCard, setPrintCard] = useState(null);
  const [sessionFilter, setSessionFilter] = useState("");
  const [termFilter, setTermFilter] = useState("");
  const filteredReportCards = useMemo(
    () => filterReportCardsByPeriod(reportCards, sessionFilter, termFilter),
    [reportCards, sessionFilter, termFilter],
  );

  useEffect(() => {
    let mounted = true;

    async function loadReportCards() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const response = await reportCardService.listMyReportCards();
        if (!mounted) return;
        setReportCards(response?.items || []);
      } catch (error) {
        if (mounted) setLoadError(getErrorMessage(error, "Failed to load report cards."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadReportCards();

    return () => {
      mounted = false;
    };
  }, []);

  const printReportCard = async (card) => {
    setPrintId(card.id);
    setLoadError(null);

    try {
      const printableCard = await reportCardService.getMyReportCard(card.id);
      setPrintCard(printableCard);
    } catch (error) {
      setLoadError(getErrorMessage(error, "Could not open report card."));
      setPrintId(null);
    }
  };

  const clearPrintCard = () => {
    setPrintCard(null);
    setPrintId(null);
  };

  if (isLoading) {
    return (
      <DashboardLayout role="student" title="Report Cards">
        <LoadingState label="Loading report cards..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="student"
      title="Report Cards"
      description="Published term reports arranged for reading first, with print and download still available."
    >
      <ReportCardPrintSheet card={printCard} onAfterPrint={clearPrintCard} />

      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && reportCards.length > 0 && (
        <Card className="p-5 sm:p-6">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-text">Filter report cards</h2>
            <p className="mt-1 text-sm text-text-muted">Choose a session and term to find an older published report quickly.</p>
          </div>
          <ReportCardPeriodFilters
            cards={reportCards}
            sessionId={sessionFilter}
            termId={termFilter}
            onSessionChange={setSessionFilter}
            onTermChange={setTermFilter}
          />
        </Card>
      )}

      {!loadError && reportCards.length === 0 && (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={FileText}
            title="No report cards available"
            description="Published report cards will appear here when your school releases them."
          />
        </Card>
      )}

      {!loadError && reportCards.length > 0 && filteredReportCards.length === 0 && (
        <Card className="p-5 sm:p-6">
          <EmptyState icon={FileText} title="No report cards match these filters" description="Choose another academic session or term." />
        </Card>
      )}

      {!loadError && filteredReportCards.length > 0 && (
        <section className="space-y-4">
          {filteredReportCards.map((card) => {
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
                    <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
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

                    <ReportCardLinesTable lines={card.lines} />
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

export default StudentReportCardsPage;
