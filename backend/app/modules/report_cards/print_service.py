from __future__ import annotations

import html
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.modules.parents.models import Parent
from app.modules.report_cards.schemas import ReportCardResponse
from app.modules.report_cards.service import ReportCardService
from app.modules.students.models import Student
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


class ReportCardPrintService:
    """Render a consistent, school-branded A4 report card."""

    @staticmethod
    def _text(value: object | None, fallback: str = "—") -> str:
        normalized = " ".join(str(value or "").split())
        return html.escape(normalized or fallback)

    @staticmethod
    def _score(value: Decimal | None) -> str:
        if value is None:
            return "—"
        rendered = format(value, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered or "0"

    @staticmethod
    def _date(value: datetime | None) -> str:
        if value is None:
            return "—"
        return value.strftime("%d %B %Y")

    @staticmethod
    def _class_label(card: ReportCardResponse) -> str:
        value = " ".join(part for part in [card.class_name, card.class_arm] if part)
        return ReportCardPrintService._text(value, "Not assigned")

    @staticmethod
    async def render_html(
        db: AsyncSession,
        actor: TenantAdmin | Parent | Student,
        report_card_id: uuid.UUID,
    ) -> str:
        card = await ReportCardService.get(db, actor, report_card_id)
        tenant = await TenantRepository.get_by_id(db, actor.tenant_id)

        school_name = ReportCardPrintService._text(
            tenant.school_name if tenant else None,
            "Weave School",
        )
        school_address = ReportCardPrintService._text(
            tenant.address if tenant else None,
            "",
        )
        school_contact = " · ".join(
            value
            for value in [
                ReportCardPrintService._text(
                    tenant.phone if tenant else None,
                    "",
                ),
                ReportCardPrintService._text(
                    tenant.email if tenant else None,
                    "",
                ),
            ]
            if value
        )
        logo_url = (
            tenant.logo_url
            if tenant and tenant.logo_url
            else f"{str(settings.FRONTEND_APP_URL).rstrip('/')}/icons/weave-email-icon.png"
        )
        student_photo = card.student_passport_photo_url

        rows = "".join(
            "<tr>"
            f"<td class='subject'>{ReportCardPrintService._text(line.subject_name)}</td>"
            f"<td>{ReportCardPrintService._text(line.subject_code)}</td>"
            f"<td>{ReportCardPrintService._score(line.test_score)}</td>"
            f"<td>{ReportCardPrintService._score(line.assessment_score)}</td>"
            f"<td>{ReportCardPrintService._score(line.exam_score)}</td>"
            f"<td class='total'>{ReportCardPrintService._score(line.total_score)}</td>"
            f"<td>{ReportCardPrintService._text(line.grade)}</td>"
            f"<td class='remark'>{ReportCardPrintService._text(line.remark, '')}</td>"
            "</tr>"
            for line in card.lines
        )

        teacher_comment = ReportCardPrintService._text(
            card.class_teacher_comment,
            "No class teacher comment provided.",
        )
        principal_comment = ReportCardPrintService._text(
            card.principal_comment,
            "No principal comment provided.",
        )
        status_value = getattr(card.status, "value", card.status)
        status_label = ReportCardPrintService._text(
            str(status_value).replace("_", " ").title()
        )
        position = (
            f"{card.position} of {card.position_out_of}"
            if card.position is not None and card.position_out_of is not None
            else "—"
        )
        photo_markup = (
            f"<img class='student-photo' src='{html.escape(student_photo)}' alt='Student passport photograph'>"
            if student_photo
            else "<div class='student-photo placeholder'>No photo</div>"
        )

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{school_name} — Report Card</title>
  <style>
    :root {{ color-scheme: light; --ink:#172033; --muted:#667085; --line:#cbd5e1; --brand:#1d4ed8; --brand-soft:#eff6ff; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:#e8edf5; color:var(--ink); font-family:Arial,Helvetica,sans-serif; line-height:1.35; }}
    .page {{ width:min(100% - 24px, 900px); margin:24px auto; background:#fff; border:1px solid #d8e0ec; box-shadow:0 20px 55px rgba(15,23,42,.14); }}
    .sheet {{ padding:28px; }}
    .school-header {{ display:grid; grid-template-columns:88px 1fr auto; gap:18px; align-items:center; border-bottom:3px solid var(--brand); padding-bottom:18px; }}
    .school-logo {{ width:82px; height:82px; object-fit:contain; border:1px solid #dbe4f0; border-radius:16px; padding:8px; background:#fff; }}
    .school-name {{ margin:0; font-size:27px; line-height:1.1; color:#0f2454; }}
    .school-meta {{ margin:6px 0 0; color:var(--muted); font-size:12px; }}
    .document-title {{ text-align:right; }}
    .document-title h2 {{ margin:0; font-size:19px; text-transform:uppercase; letter-spacing:.08em; }}
    .document-title p {{ margin:6px 0 0; color:var(--muted); font-size:12px; }}
    .student-panel {{ display:grid; grid-template-columns:84px 1fr; gap:16px; margin-top:20px; border:1px solid var(--line); border-radius:16px; padding:16px; background:#f8fafc; }}
    .student-photo {{ width:80px; height:94px; object-fit:cover; border:1px solid var(--line); border-radius:10px; background:#fff; }}
    .student-photo.placeholder {{ display:flex; align-items:center; justify-content:center; color:var(--muted); font-size:11px; text-align:center; }}
    .student-name {{ margin:0 0 10px; font-size:21px; }}
    .meta-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }}
    .field {{ border-left:3px solid #bfdbfe; padding-left:9px; min-width:0; }}
    .field span {{ display:block; color:var(--muted); font-size:9px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
    .field strong {{ display:block; margin-top:3px; font-size:12px; overflow-wrap:anywhere; }}
    .summary {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; margin:18px 0; }}
    .metric {{ border:1px solid #bfdbfe; border-radius:12px; background:var(--brand-soft); padding:10px; text-align:center; }}
    .metric span {{ display:block; color:#475569; font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
    .metric strong {{ display:block; margin-top:5px; color:#0f2454; font-size:17px; }}
    .table-wrap {{ overflow:visible; }}
    table {{ width:100%; border-collapse:collapse; table-layout:fixed; font-size:10px; }}
    thead {{ display:table-header-group; }}
    tr {{ break-inside:avoid; page-break-inside:avoid; }}
    th,td {{ border:1px solid var(--line); padding:7px 6px; text-align:center; vertical-align:middle; overflow-wrap:anywhere; }}
    th {{ background:#eaf1ff; color:#173a77; font-size:8px; letter-spacing:.04em; text-transform:uppercase; }}
    td.subject, td.remark {{ text-align:left; }}
    td.total {{ font-weight:700; }}
    .comments {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:18px; break-inside:avoid; }}
    .comment {{ min-height:98px; border:1px solid var(--line); border-radius:12px; padding:12px; }}
    .comment h3 {{ margin:0 0 8px; color:#173a77; font-size:11px; text-transform:uppercase; letter-spacing:.06em; }}
    .comment p {{ margin:0; font-size:11px; white-space:pre-wrap; }}
    .signatures {{ display:grid; grid-template-columns:1fr 1fr; gap:70px; margin-top:34px; break-inside:avoid; }}
    .signature {{ border-top:1px solid #475569; padding-top:6px; text-align:center; color:var(--muted); font-size:10px; }}
    footer {{ display:flex; justify-content:space-between; gap:16px; margin-top:20px; border-top:1px solid #dbe4f0; padding-top:10px; color:var(--muted); font-size:9px; }}
    @page {{ size:A4 portrait; margin:10mm; }}
    @media print {{
      body {{ background:#fff; }}
      .page {{ width:100%; margin:0; border:0; box-shadow:none; }}
      .sheet {{ padding:0; }}
    }}
    @media (max-width:700px) {{
      .sheet {{ padding:16px; }}
      .school-header {{ grid-template-columns:64px 1fr; }}
      .school-logo {{ width:60px; height:60px; }}
      .document-title {{ grid-column:1/-1; text-align:left; }}
      .meta-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      .summary {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      .comments {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="sheet">
      <header class="school-header">
        <img class="school-logo" src="{html.escape(logo_url)}" alt="{school_name} logo">
        <div>
          <h1 class="school-name">{school_name}</h1>
          <p class="school-meta">{school_address}</p>
          <p class="school-meta">{school_contact}</p>
        </div>
        <div class="document-title">
          <h2>Termly Academic Report</h2>
          <p>{ReportCardPrintService._text(card.academic_session_name)} · {ReportCardPrintService._text(card.academic_term_name)}</p>
        </div>
      </header>

      <section class="student-panel">
        {photo_markup}
        <div>
          <h2 class="student-name">{ReportCardPrintService._text(card.student_name, card.admission_number or "Student")}</h2>
          <div class="meta-grid">
            <div class="field"><span>Admission number</span><strong>{ReportCardPrintService._text(card.admission_number, "Not assigned")}</strong></div>
            <div class="field"><span>Class</span><strong>{ReportCardPrintService._class_label(card)}</strong></div>
            <div class="field"><span>Session</span><strong>{ReportCardPrintService._text(card.academic_session_name)}</strong></div>
            <div class="field"><span>Term</span><strong>{ReportCardPrintService._text(card.academic_term_name)}</strong></div>
            <div class="field"><span>Status</span><strong>{status_label}</strong></div>
            <div class="field"><span>Published</span><strong>{ReportCardPrintService._date(card.published_at)}</strong></div>
            <div class="field"><span>Version</span><strong>{card.version}</strong></div>
            <div class="field"><span>Report ID</span><strong>{str(card.id)[:8].upper()}</strong></div>
          </div>
        </div>
      </section>

      <section class="summary">
        <div class="metric"><span>Total score</span><strong>{ReportCardPrintService._score(card.total_score)}</strong></div>
        <div class="metric"><span>Average</span><strong>{ReportCardPrintService._score(card.average_score)}</strong></div>
        <div class="metric"><span>Position</span><strong>{position}</strong></div>
        <div class="metric"><span>Subjects</span><strong>{len(card.lines)}</strong></div>
        <div class="metric"><span>Term</span><strong>{ReportCardPrintService._text(card.academic_term_name)}</strong></div>
      </section>

      <div class="table-wrap">
        <table>
          <colgroup>
            <col style="width:23%"><col style="width:8%"><col style="width:8%"><col style="width:10%"><col style="width:8%"><col style="width:8%"><col style="width:8%"><col style="width:27%">
          </colgroup>
          <thead><tr><th>Subject</th><th>Code</th><th>Test</th><th>Assessment</th><th>Exam</th><th>Total</th><th>Grade</th><th>Remark</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>

      <section class="comments">
        <article class="comment"><h3>Class teacher's comment</h3><p>{teacher_comment}</p></article>
        <article class="comment"><h3>Principal's comment</h3><p>{principal_comment}</p></article>
      </section>

      <section class="signatures">
        <div class="signature">Class teacher signature</div>
        <div class="signature">Principal signature</div>
      </section>

      <footer>
        <span>{school_name}</span>
        <span>Generated securely by Weave · Report {str(card.id)}</span>
      </footer>
    </section>
  </main>
</body>
</html>"""
