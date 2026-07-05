import Badge from "../ui/Badge";
import { cleanText } from "../../utils/academicDashboard";

function ReportCardLinesTable({ lines = [] }) {
  if (!Array.isArray(lines) || lines.length === 0) {
    return (
      <p className="mt-4 text-sm text-text-muted">
        No subject lines are attached to this report card.
      </p>
    );
  }

  return (
    <div className="mt-4 overflow-hidden rounded-[1.3rem] border border-border/70 bg-surface shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm text-text">
          <thead className="border-b border-border/70 bg-surface-muted/30 text-[11px] uppercase tracking-[0.12em] text-text-muted">
            <tr>
              <th className="px-4 py-3.5 font-semibold">Subject</th>
              <th className="px-4 py-3.5 text-center font-semibold">Test</th>
              <th className="px-4 py-3.5 text-center font-semibold">
                Assessment
              </th>
              <th className="px-4 py-3.5 text-center font-semibold">Exam</th>
              <th className="px-4 py-3.5 text-center font-semibold">Total</th>
              <th className="px-4 py-3.5 text-center font-semibold">Grade</th>
              <th className="px-4 py-3.5 text-right font-semibold">Remark</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {lines.map((line) => (
              <tr
                key={line.id}
                className="align-top transition hover:bg-surface-muted/20"
              >
                <td className="px-4 py-4">
                  <div className="min-w-[13rem]">
                    <p className="font-semibold text-text">
                      {cleanText(line.subject_name, "Subject")}
                    </p>
                    <p className="mt-1 text-[11px] text-text-muted">
                      Teacher: {cleanText(line.teacher_name)}
                    </p>
                  </div>
                </td>
                <td className="px-4 py-4 text-center font-medium">
                  {cleanText(line.test_score, "-")}
                </td>
                <td className="px-4 py-4 text-center font-medium">
                  {cleanText(line.assessment_score, "-")}
                </td>
                <td className="px-4 py-4 text-center font-medium">
                  {cleanText(line.exam_score, "-")}
                </td>
                <td className="px-4 py-4 text-center">
                  <span className="inline-flex min-w-[4.5rem] items-center justify-center rounded-full bg-primary-soft px-3 py-1 text-sm font-bold text-primary">
                    {cleanText(line.total_score, "-")}
                  </span>
                </td>
                <td className="px-4 py-4 text-center">
                  <Badge variant="info" className="px-2.5 py-0.5">
                    {cleanText(line.grade, "-")}
                  </Badge>
                </td>
                <td className="px-4 py-4 text-right text-xs font-medium text-text-soft">
                  <span className="inline-block min-w-[6rem] rounded-full bg-surface-muted/30 px-3 py-1.5 text-center">
                    {cleanText(line.remark, "-")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ReportCardLinesTable;
