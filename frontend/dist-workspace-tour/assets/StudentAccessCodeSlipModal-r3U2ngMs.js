import{i as e,t}from"./Button-Dt31Dr6g.js";import{V as n}from"./index-BtNx0cKy.js";var r=e(),i=e=>String(e||``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`).replace(/'/g,`&#039;`),a=(e,t)=>e?.fields.find(e=>e.label===t)?.value||`-`,o=e=>[e.title,``,...e.fields.map(e=>`${e.label}: ${e.value||`-`}`),``,`Use this access code once to create your student password.`].join(`
`),s=e=>{let t=a(e,`Student`),n=a(e,`Admission number`),r=a(e,`Access code`),o=a(e,`Expires`);return`<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Student Access Slip</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f5f7fb;
      color: #111827;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 24px;
    }
    .page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .slip {
      width: min(100%, 520px);
      border: 1px solid #d1d5db;
      border-radius: 24px;
      background: #ffffff;
      padding: 28px;
      box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12);
    }
    .eyebrow {
      margin: 0 0 8px;
      color: #6b7280;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
    }
    .subtitle {
      margin: 10px 0 0;
      color: #4b5563;
      font-size: 14px;
      line-height: 1.6;
    }
    .grid {
      display: grid;
      gap: 12px;
      margin-top: 24px;
    }
    .field {
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px 16px;
      background: #f9fafb;
    }
    .label {
      color: #6b7280;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .value {
      margin-top: 6px;
      word-break: break-word;
      font-size: 16px;
      font-weight: 700;
    }
    .code .value {
      font-size: clamp(28px, 9vw, 44px);
      letter-spacing: 0.16em;
      text-align: center;
    }
    .note {
      margin-top: 22px;
      border-radius: 16px;
      background: #eff6ff;
      color: #1e3a8a;
      padding: 14px 16px;
      font-size: 13px;
      line-height: 1.6;
    }
    .footer {
      margin-top: 20px;
      color: #6b7280;
      font-size: 12px;
      text-align: center;
    }
    .actions {
      margin-top: 18px;
      display: flex;
      gap: 10px;
      justify-content: center;
    }
    button {
      border: 0;
      border-radius: 999px;
      background: #111827;
      color: #ffffff;
      cursor: pointer;
      font-size: 14px;
      font-weight: 700;
      padding: 12px 18px;
    }
    @media (max-width: 520px) {
      body { padding: 12px; }
      .page { align-items: flex-start; padding-top: 16px; }
      .slip { border-radius: 20px; padding: 20px; }
      h1 { font-size: 21px; }
    }
    @media print {
      body { background: #fff; padding: 0; }
      .page { min-height: auto; display: block; }
      .slip { width: 100%; box-shadow: none; border-color: #111827; border-radius: 18px; }
      .actions { display: none; }
    }
  </style>
</head>
<body>
  <main class="page">
    <section class="slip" aria-label="Student access slip">
      <p class="eyebrow">Student access slip</p>
      <h1>${i(e.title)}</h1>
      <p class="subtitle">${i(e.description)}</p>
      <div class="grid">
        <div class="field"><div class="label">Student</div><div class="value">${i(t)}</div></div>
        <div class="field"><div class="label">Admission number</div><div class="value">${i(n)}</div></div>
        <div class="field code"><div class="label">Access code</div><div class="value">${i(r)}</div></div>
        <div class="field"><div class="label">Expires</div><div class="value">${i(o)}</div></div>
      </div>
      <div class="note">Use the admission number and access code to log in once. The student must create a new private password immediately after login.</div>
      <p class="footer">Give this slip only to the correct student.</p>
      <div class="actions"><button type="button" onclick="window.print()">Print slip</button></div>
    </section>
  </main>
</body>
</html>`};function c({notice:e,onClose:i,onCopied:a,onCopyFailed:c,onPrintFailed:l}){return e?(0,r.jsx)(`div`,{className:`fixed inset-0 z-50 flex items-end justify-center bg-black/40 px-3 py-4 sm:items-center sm:px-6`,children:(0,r.jsxs)(n,{className:`w-full max-w-xl p-5 shadow-xl sm:p-6`,children:[(0,r.jsxs)(`div`,{className:`flex items-start justify-between gap-4`,children:[(0,r.jsxs)(`div`,{children:[(0,r.jsx)(`h2`,{className:`text-lg font-semibold text-text`,children:e.title}),(0,r.jsx)(`p`,{className:`mt-1 text-sm text-text-muted`,children:e.description})]}),(0,r.jsx)(t,{type:`button`,variant:`outline`,size:`small`,onClick:i,children:`Close`})]}),(0,r.jsx)(`div`,{className:`mt-5 rounded-2xl border border-border bg-surface-muted/50 p-4`,children:(0,r.jsx)(`dl`,{className:`grid gap-3 sm:grid-cols-2`,children:e.fields.map(e=>(0,r.jsxs)(`div`,{children:[(0,r.jsx)(`dt`,{className:`text-xs font-semibold uppercase tracking-wide text-text-muted`,children:e.label}),(0,r.jsx)(`dd`,{className:`mt-1 break-words text-sm font-semibold text-text`,children:e.value||`-`})]},e.label))})}),(0,r.jsx)(`p`,{className:`mt-4 text-sm text-text-muted`,children:`The access code is shown once. Give it only to the correct student.`}),(0,r.jsxs)(`div`,{className:`mt-5 grid gap-2 sm:flex sm:flex-wrap`,children:[(0,r.jsx)(t,{type:`button`,onClick:async()=>{try{await navigator.clipboard.writeText(o(e)),a?.()}catch{c?.()}},className:`w-full sm:w-auto`,children:`Copy details`}),(0,r.jsx)(t,{type:`button`,variant:`outline`,onClick:()=>{let t=window.open(``,`_blank`,`width=720,height=760`);if(!t){l?.();return}t.document.open(),t.document.write(s(e)),t.document.close(),t.focus(),window.setTimeout(()=>{t.print()},300)},className:`w-full sm:w-auto`,children:`Print slip`}),(0,r.jsx)(t,{type:`button`,variant:`outline`,onClick:i,className:`w-full sm:w-auto`,children:`Done`})]})]})}):null}export{c as t};