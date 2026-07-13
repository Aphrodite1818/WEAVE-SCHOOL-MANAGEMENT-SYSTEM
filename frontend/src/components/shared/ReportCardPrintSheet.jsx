import { useEffect } from "react";

import ReportCardLinesTable from "./ReportCardLinesTable";
import { cleanText } from "../../utils/academicDashboard";

const formatClassLabel = (card) =>
  [card?.class_name, card?.class_arm].filter(Boolean).join(" ") || "Not assigned";

function ReportCardPrintSheet({ card, schoolName = "Weave", onAfterPrint }) {
  useEffect(() => {
    if (!card) return undefined;

    const clearAfterPrint = () => onAfterPrint?.();
    window.addEventListener("afterprint", clearAfterPrint, { once: true });

    const timer = window.setTimeout(() => {
      window.print();
    }, 50);

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("afterprint", clearAfterPrint);
    };
  }, [card, onAfterPrint]);

  if (!card) return null;

  return (
    <section className="report-card-print-root" aria-hidden="true">
      <style>
        {`
          .report-card-print-root { display: none; }
          @media print {
            body * { visibility: hidden; }
            .report-card-print-root {
              display: block;
              position: absolute;
              inset: 0;
              color: #0f172a;
              font-family: Arial, sans-serif;
              line-height: 1.45;
              visibility: visible;
            }
            .report-card-print-root * {
              visibility: visible;
            }
            .report-card-print-sheet { padding: 24px; }
            .report-card-print-brand {
              background: #1a237e;
              color: #ffffff;
              margin-bottom: 20px;
              padding: 18px 20px;
            }
            .report-card-print-brand h1,
            .report-card-print-title { margin: 0; }
            .report-card-print-status {
              display: inline-block;
              margin-top: 8px;
              background: #e5e7eb;
              color: #374151;
              padding: 6px 10px;
              font-size: 12px;
              font-weight: 700;
            }
            .report-card-print-meta,
            .report-card-print-summary {
              display: grid;
              gap: 12px;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              margin: 20px 0;
            }
            .report-card-print-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .report-card-print-card {
              border: 1px solid #cbd5e1;
              background: #f8fafc;
              padding: 12px;
            }
            .report-card-print-card span {
              color: #64748b;
              display: block;
              font-size: 11px;
              font-weight: 800;
              text-transform: uppercase;
            }
            .report-card-print-card strong {
              display: block;
              font-size: 15px;
              margin-top: 3px;
            }
            .report-card-print-root table {
              border-collapse: collapse;
              width: 100%;
              font-size: 12px;
            }
            .report-card-print-root th,
            .report-card-print-root td {
              border: 1px solid #cbd5e1;
              padding: 8px;
              text-align: left;
              vertical-align: top;
            }
            .report-card-print-root th {
              background: #e8eaf6;
              color: #1a237e;
              font-size: 10px;
              text-transform: uppercase;
            }
            .report-card-print-footer {
              margin-top: 20px;
              border-top: 1px solid #cbd5e1;
              color: #64748b;
              font-size: 12px;
              padding-top: 12px;
            }
          }
        `}
      </style>
      <main>
        <section className="report-card-print-sheet">
          <section className="report-card-print-brand">
            <h1>{schoolName}</h1>
            <p>Termly academic report</p>
          </section>
          <h1 className="report-card-print-title">Report Card</h1>
          <p>
            <strong>{cleanText(card.student_name, card.admission_number || "Student")}</strong>
          </p>
          <div className="report-card-print-status">{cleanText(card.status)}</div>
          <section className="report-card-print-meta">
            <div className="report-card-print-card">
              <span>Admission No.</span>
              <strong>{cleanText(card.admission_number, "Not assigned")}</strong>
            </div>
            <div className="report-card-print-card">
              <span>Class</span>
              <strong>{formatClassLabel(card)}</strong>
            </div>
            <div className="report-card-print-card">
              <span>Session</span>
              <strong>{cleanText(card.academic_session_name)}</strong>
            </div>
            <div className="report-card-print-card">
              <span>Term</span>
              <strong>{cleanText(card.academic_term_name)}</strong>
            </div>
          </section>
          <section className="report-card-print-summary">
            <div className="report-card-print-card">
              <span>Total score</span>
              <strong>{cleanText(card.total_score)}</strong>
            </div>
            <div className="report-card-print-card">
              <span>Average</span>
              <strong>{cleanText(card.average_score)}</strong>
            </div>
          </section>
          <ReportCardLinesTable lines={card.lines} />
          <footer className="report-card-print-footer">
            Generated by Weave - {cleanText(card.academic_session_name)} academic session
          </footer>
        </section>
      </main>
    </section>
  );
}

export default ReportCardPrintSheet;
