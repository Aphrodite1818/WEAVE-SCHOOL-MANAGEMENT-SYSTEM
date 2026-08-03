const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const formatDate = (value) => {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export const createStudentSlipPrintWindow = () => {
  const printWindow = window.open("", "_blank", "width=980,height=760");
  if (!printWindow) {
    throw new Error("The browser blocked the print window. Allow pop-ups for Weave and try again.");
  }
  printWindow.document.write(`<!doctype html><html><head><title>Preparing student slips</title></head><body style="font-family:system-ui;padding:32px"><p>Preparing student slips...</p></body></html>`);
  printWindow.document.close();
  return printWindow;
};

export const renderStudentSlipPrintDocument = (
  printWindow,
  payload,
  { layout = "two" } = {},
) => {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  const schoolName = escapeHtml(payload?.school_name || "School");
  const logoUrl = payload?.school_logo_url ? escapeHtml(payload.school_logo_url) : "";
  const columns = layout === "one" ? 1 : 2;
  const slips = items.map((item) => `
    <article class="slip">
      <header class="slip__header">
        <div class="brand">
          ${logoUrl ? `<img src="${logoUrl}" alt="" />` : `<span class="brand__mark">W</span>`}
          <div>
            <p class="school">${schoolName}</p>
            <p class="eyebrow">Student login credentials</p>
          </div>
        </div>
        <span class="badge">Initial setup</span>
      </header>
      <div class="slip__body">
        <dl>
          <div><dt>Student</dt><dd>${escapeHtml(item.full_name)}</dd></div>
          <div><dt>Class</dt><dd>${escapeHtml(item.class_name)}</dd></div>
          <div><dt>Admission number</dt><dd class="strong">${escapeHtml(item.admission_number)}</dd></div>
          <div><dt>Temporary access code</dt><dd class="code">${escapeHtml(item.setup_code)}</dd></div>
          <div><dt>Login address</dt><dd class="url">${escapeHtml(item.login_url || payload?.login_url)}</dd></div>
          <div><dt>Code expires</dt><dd>${escapeHtml(formatDate(item.access_code_expires_at))}</dd></div>
        </dl>
        <p class="instructions">Use the admission number and temporary access code for the first login. The student must create a new password immediately.</p>
        <p class="security">Private credential: give this slip only to the student or their guardian.</p>
      </div>
      <footer>Generated ${escapeHtml(formatDate(item.generated_at))} · Import row ${escapeHtml(item.row_number)}</footer>
    </article>
  `).join("");

  const documentHtml = `<!doctype html>
  <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>${schoolName} student access slips</title>
      <style>
        :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        * { box-sizing: border-box; }
        body { margin: 0; background: #f8fafc; color: #111827; }
        .print-toolbar { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 20px; border-bottom: 1px solid #d1d5db; background: rgba(255,255,255,.96); }
        .print-toolbar strong { display: block; }
        .print-toolbar span { color: #6b7280; font-size: 13px; }
        .print-toolbar button { border: 0; border-radius: 10px; background: #2563eb; color: white; cursor: pointer; font: inherit; font-weight: 800; padding: 10px 16px; }
        main { display: grid; grid-template-columns: repeat(${columns}, minmax(0, 1fr)); gap: 12px; max-width: 1180px; margin: 0 auto; padding: 20px; }
        .slip { break-inside: avoid; overflow: hidden; border: 1px solid #cbd5e1; border-radius: 16px; background: white; box-shadow: 0 10px 25px rgba(15,23,42,.08); }
        .slip__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 15px; border-bottom: 1px solid #dbeafe; background: linear-gradient(135deg, #eff6ff, #fff); }
        .brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
        .brand img, .brand__mark { width: 38px; height: 38px; flex: 0 0 auto; border-radius: 10px; object-fit: contain; }
        .brand__mark { display: grid; place-items: center; background: #2563eb; color: white; font-weight: 900; }
        .school { overflow: hidden; margin: 0; font-size: 14px; font-weight: 900; text-overflow: ellipsis; white-space: nowrap; }
        .eyebrow { margin: 2px 0 0; color: #2563eb; font-size: 10px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
        .badge { flex: 0 0 auto; border-radius: 999px; background: #2563eb; color: white; font-size: 10px; font-weight: 900; padding: 5px 8px; }
        .slip__body { padding: 14px 15px; }
        dl { display: grid; gap: 0; margin: 0; }
        dl > div { display: grid; grid-template-columns: minmax(110px, 36%) 1fr; gap: 12px; padding: 7px 0; border-bottom: 1px solid #e5e7eb; }
        dt { color: #64748b; font-size: 11px; font-weight: 800; }
        dd { min-width: 0; margin: 0; overflow-wrap: anywhere; font-size: 12px; font-weight: 700; }
        .strong { font-weight: 900; }
        .code { color: #1d4ed8; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 16px; font-weight: 900; letter-spacing: .08em; }
        .url { font-size: 10px; }
        .instructions, .security { margin: 10px 0 0; font-size: 10px; line-height: 1.45; }
        .instructions { color: #475569; }
        .security { border-radius: 8px; background: #fef3c7; color: #92400e; font-weight: 800; padding: 8px; }
        footer { padding: 8px 15px; border-top: 1px solid #e5e7eb; color: #64748b; font-size: 9px; }
        @media print {
          @page { size: A4; margin: 9mm; }
          body { background: white; }
          .print-toolbar { display: none; }
          main { grid-template-columns: repeat(${columns}, minmax(0, 1fr)); gap: 6mm; max-width: none; padding: 0; }
          .slip { box-shadow: none; }
        }
        @media screen and (max-width: 760px) { main { grid-template-columns: 1fr; padding: 12px; } }
      </style>
    </head>
    <body>
      <div class="print-toolbar">
        <div><strong>${schoolName} student slips</strong><span>${items.length} printable slip${items.length === 1 ? "" : "s"}</span></div>
        <button type="button" onclick="window.print()">Print</button>
      </div>
      <main>${slips}</main>
    </body>
  </html>`;

  printWindow.document.open();
  printWindow.document.write(documentHtml);
  printWindow.document.close();
  printWindow.focus();
  window.setTimeout(() => printWindow.print(), 250);
};
