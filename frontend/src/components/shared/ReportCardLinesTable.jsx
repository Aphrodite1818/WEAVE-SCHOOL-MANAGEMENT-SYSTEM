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
  const componentHeaders = lines[0]?.components || [];

  return (
    <div className="mt-4 overflow-hidden rounded-[1.3rem] border border-border/70 bg-surface shadow-sm">
      <div className="grid gap-3 p-3 md:hidden">
        {lines.map((line) => (
          <article
            key={line.id}
            className="rounded-[1.1rem] border border-border/70 bg-surface px-3 py-3"
          >
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold leading-5 text-text">
                {cleanText(line.subject_name, "Subject")}
              </p>
              <p className="mt-1 break-words text-[11px] leading-4 text-text-muted">
                Teacher: {cleanText(line.teacher_name)}
              </p>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-3">
              {(line.components || []).map((component) => (
                <ScoreCell key={component.assessment_component_id} label={component.name} value={`${cleanText(component.score, "-")} / ${cleanText(component.maximum_score, "-")}`} />
              ))}
            </dl>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex min-w-[4.25rem] items-center justify-center rounded-full bg-primary-soft px-3 py-1 text-sm font-bold text-primary">
                {cleanText(line.total_score, "-")}
              </span>
              <Badge variant="info" className="px-2.5 py-0.5">
                {cleanText(line.grade, "-")}
              </Badge>
              <span className="min-w-0 flex-1 rounded-full bg-surface-muted/30 px-3 py-1.5 text-center text-xs font-medium leading-4 text-text-soft">
                {cleanText(line.remark, "-")}
              </span>
            </div>
          </article>
        ))}
      </div>

      <div className="hidden max-w-full overflow-x-auto overscroll-x-contain md:block">
        <table className="w-full min-w-[54rem] table-fixed text-left text-sm text-text lg:min-w-[72rem] xl:min-w-full">
          <thead className="border-b border-border/70 bg-surface-muted/30 text-[11px] uppercase tracking-[0.12em] text-text-muted">
            <tr>
              <th className="whitespace-nowrap px-4 py-3.5 font-semibold">Subject</th>
              {componentHeaders.map((component) => (
                <th key={component.assessment_component_id} className="whitespace-nowrap px-4 py-3.5 text-center font-semibold">{component.name}</th>
              ))}
              <th className="whitespace-nowrap px-4 py-3.5 text-center font-semibold">Total</th>
              <th className="whitespace-nowrap px-4 py-3.5 text-center font-semibold">Grade</th>
              <th className="whitespace-nowrap px-4 py-3.5 text-right font-semibold">Remark</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {lines.map((line) => (
              <tr
                key={line.id}
                className="align-top transition hover:bg-surface-muted/20"
              >
                <td className="px-4 py-4">
                  <div className="min-w-0">
                    <p className="font-semibold text-text">
                      {cleanText(line.subject_name, "Subject")}
                    </p>
                    <p className="mt-1 text-[11px] text-text-muted">
                      Teacher: {cleanText(line.teacher_name)}
                    </p>
                  </div>
                </td>
                {componentHeaders.map((header) => {
                  const component = (line.components || []).find((item) => item.assessment_component_id === header.assessment_component_id);
                  return <td key={header.assessment_component_id} className="whitespace-nowrap px-4 py-4 text-center font-medium">{cleanText(component?.score, "-")}</td>;
                })}
                <td className="whitespace-nowrap px-4 py-4 text-center">
                  <span className="inline-flex min-w-[4.5rem] items-center justify-center rounded-full bg-primary-soft px-3 py-1 text-sm font-bold text-primary">
                    {cleanText(line.total_score, "-")}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-center">
                  <Badge variant="info" className="px-2.5 py-0.5">
                    {cleanText(line.grade, "-")}
                  </Badge>
                </td>
                <td className="whitespace-nowrap px-4 py-4 text-right text-xs font-medium text-text-soft">
                  <span className="inline-block w-full rounded-full bg-surface-muted/30 px-3 py-1.5 text-center">
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

function ScoreCell({ label, value }) {
  return (
    <div className="rounded-xl bg-surface-muted/30 px-2 py-2">
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-semibold text-text">
        {cleanText(value, "-")}
      </dd>
    </div>
  );
}

export default ReportCardLinesTable;
