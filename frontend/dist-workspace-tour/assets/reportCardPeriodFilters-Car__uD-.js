import{g as e,i as t,y as n}from"./Button-Dt31Dr6g.js";import{a as r}from"./academicDashboard-B6TdsVci.js";var i=n(e(),1),a=t(),o=e=>[e?.class_name,e?.class_arm].filter(Boolean).join(` `)||`Not assigned`,s=e=>e?.position===null||e?.position===void 0?`--`:e?.position_out_of?`${e.position} of ${e.position_out_of}`:String(e.position),c=e=>{if(!e)return`--`;let t=new Date(e);return Number.isNaN(t.getTime())?`--`:new Intl.DateTimeFormat(void 0,{day:`numeric`,month:`long`,year:`numeric`}).format(t)};function l({card:e,onAfterPrint:t}){if((0,i.useEffect)(()=>{if(!e)return;let n=()=>t?.();window.addEventListener(`afterprint`,n,{once:!0});let r=!1,i=window.setTimeout(async()=>{let e=document.querySelector(`.report-card-print-root`),t=e?[...e.querySelectorAll(`img`)]:[];await Promise.all(t.map(e=>e.complete?Promise.resolve():new Promise(t=>{e.addEventListener(`load`,t,{once:!0}),e.addEventListener(`error`,t,{once:!0})}))),r||window.print()},80);return()=>{r=!0,window.clearTimeout(i),window.removeEventListener(`afterprint`,n)}},[e,t]),!e)return null;let n=r(e.school_name,`Weave School`),l=e.school_logo_url||`/icons/weave-email-icon.png`,p=e.student_passport_photo_url,m=Array.isArray(e.lines)?e.lines:[],h=m[0]?.components||[];return(0,a.jsxs)(`section`,{className:`report-card-print-root`,"aria-hidden":`true`,children:[(0,a.jsx)(`style`,{children:`
          .report-card-print-root { display: none; }
          @page { size: A4 portrait; margin: 10mm; }
          @media print {
            body * { visibility: hidden; }
            .report-card-print-root,
            .report-card-print-root * { visibility: visible; }
            .report-card-print-root {
              display: block;
              position: absolute;
              inset: 0;
              color: #172033;
              background: #ffffff;
              font-family: Arial, Helvetica, sans-serif;
              line-height: 1.35;
            }
            .rc-sheet { width: 100%; }
            .rc-header {
              display: grid;
              grid-template-columns: 82px 1fr auto;
              gap: 16px;
              align-items: center;
              border-bottom: 3px solid #1d4ed8;
              padding-bottom: 16px;
            }
            .rc-school-logo {
              width: 76px;
              height: 76px;
              object-fit: contain;
              border: 1px solid #dbe4f0;
              border-radius: 14px;
              padding: 7px;
            }
            .rc-school-name { margin: 0; color: #0f2454; font-size: 25px; line-height: 1.12; }
            .rc-school-meta { margin: 4px 0 0; color: #667085; font-size: 10px; }
            .rc-title { text-align: right; }
            .rc-title h2 { margin: 0; font-size: 17px; letter-spacing: .08em; text-transform: uppercase; }
            .rc-title p { margin: 5px 0 0; color: #667085; font-size: 10px; }
            .rc-student {
              display: grid;
              grid-template-columns: 78px 1fr;
              gap: 14px;
              margin-top: 16px;
              border: 1px solid #cbd5e1;
              border-radius: 14px;
              background: #f8fafc;
              padding: 14px;
              break-inside: avoid;
            }
            .rc-student-photo {
              width: 74px;
              height: 88px;
              object-fit: cover;
              border: 1px solid #cbd5e1;
              border-radius: 9px;
              background: #ffffff;
            }
            .rc-photo-placeholder {
              display: flex;
              align-items: center;
              justify-content: center;
              color: #667085;
              font-size: 9px;
              text-align: center;
            }
            .rc-student-name { margin: 0 0 8px; font-size: 19px; }
            .rc-meta { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
            .rc-field { border-left: 3px solid #bfdbfe; padding-left: 8px; min-width: 0; }
            .rc-field span,
            .rc-metric span {
              display: block;
              color: #667085;
              font-size: 8px;
              font-weight: 700;
              letter-spacing: .06em;
              text-transform: uppercase;
            }
            .rc-field strong { display: block; margin-top: 3px; font-size: 10px; overflow-wrap: anywhere; }
            .rc-summary { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin: 14px 0; break-inside: avoid; }
            .rc-metric { border: 1px solid #bfdbfe; border-radius: 10px; background: #eff6ff; padding: 9px; text-align: center; }
            .rc-metric strong { display: block; margin-top: 4px; color: #0f2454; font-size: 15px; }
            .rc-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 9px; }
            .rc-table thead { display: table-header-group; }
            .rc-table tr { break-inside: avoid; page-break-inside: avoid; }
            .rc-table th,
            .rc-table td { border: 1px solid #cbd5e1; padding: 6px 5px; text-align: center; vertical-align: middle; overflow-wrap: anywhere; }
            .rc-table th { background: #eaf1ff; color: #173a77; font-size: 7px; letter-spacing: .04em; text-transform: uppercase; }
            .rc-table .left { text-align: left; }
            .rc-table .strong { font-weight: 700; }
            .rc-comments { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 15px; break-inside: avoid; }
            .rc-comment { min-height: 82px; border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px; }
            .rc-comment h3 { margin: 0 0 6px; color: #173a77; font-size: 9px; letter-spacing: .05em; text-transform: uppercase; }
            .rc-comment p { margin: 0; font-size: 9px; white-space: pre-wrap; }
            .rc-signatures { display: grid; grid-template-columns: 1fr 1fr; gap: 64px; margin-top: 30px; break-inside: avoid; }
            .rc-signature { border-top: 1px solid #475569; padding-top: 5px; color: #667085; font-size: 9px; text-align: center; }
            .rc-footer { display: flex; justify-content: space-between; gap: 14px; margin-top: 17px; border-top: 1px solid #dbe4f0; padding-top: 8px; color: #667085; font-size: 8px; }
          }
        `}),(0,a.jsxs)(`main`,{className:`rc-sheet`,children:[(0,a.jsxs)(`header`,{className:`rc-header`,children:[(0,a.jsx)(`img`,{className:`rc-school-logo`,src:l,alt:`School logo`}),(0,a.jsxs)(`div`,{children:[(0,a.jsx)(`h1`,{className:`rc-school-name`,children:n}),e.school_address?(0,a.jsx)(`p`,{className:`rc-school-meta`,children:e.school_address}):null,e.school_phone||e.school_email?(0,a.jsx)(`p`,{className:`rc-school-meta`,children:[e.school_phone,e.school_email].filter(Boolean).join(` · `)}):null]}),(0,a.jsxs)(`div`,{className:`rc-title`,children:[(0,a.jsx)(`h2`,{children:`Termly Academic Report`}),(0,a.jsxs)(`p`,{children:[r(e.academic_session_name),` · `,r(e.academic_term_name)]})]})]}),(0,a.jsxs)(`section`,{className:`rc-student`,children:[p?(0,a.jsx)(`img`,{className:`rc-student-photo`,src:p,alt:`Student passport`}):(0,a.jsx)(`div`,{className:`rc-student-photo rc-photo-placeholder`,children:`No photo`}),(0,a.jsxs)(`div`,{children:[(0,a.jsx)(`h2`,{className:`rc-student-name`,children:r(e.student_name,e.admission_number||`Student`)}),(0,a.jsxs)(`div`,{className:`rc-meta`,children:[(0,a.jsx)(u,{label:`Admission number`,value:r(e.admission_number,`Not assigned`)}),(0,a.jsx)(u,{label:`Class`,value:o(e)}),(0,a.jsx)(u,{label:`Session`,value:r(e.academic_session_name)}),(0,a.jsx)(u,{label:`Term`,value:r(e.academic_term_name)}),(0,a.jsx)(u,{label:`Status`,value:r(e.status)}),(0,a.jsx)(u,{label:`Published`,value:c(e.published_at)}),(0,a.jsx)(u,{label:`Version`,value:r(e.version,`1`)}),(0,a.jsx)(u,{label:`Report ID`,value:String(e.id||``).slice(0,8).toUpperCase()})]})]})]}),(0,a.jsxs)(`section`,{className:`rc-summary`,children:[(0,a.jsx)(d,{label:`Total score`,value:r(e.total_score)}),(0,a.jsx)(d,{label:`Average`,value:r(e.average_score)}),(0,a.jsx)(d,{label:`Position`,value:s(e)}),(0,a.jsx)(d,{label:`Subjects`,value:m.length}),(0,a.jsx)(d,{label:`Term`,value:r(e.academic_term_name)})]}),(0,a.jsxs)(`table`,{className:`rc-table`,children:[(0,a.jsx)(`thead`,{children:(0,a.jsxs)(`tr`,{children:[(0,a.jsx)(`th`,{children:`Subject`}),(0,a.jsx)(`th`,{children:`Code`}),h.map(e=>(0,a.jsx)(`th`,{children:e.name},e.assessment_component_id)),(0,a.jsx)(`th`,{children:`Total`}),(0,a.jsx)(`th`,{children:`Grade`}),(0,a.jsx)(`th`,{children:`Remark`})]})}),(0,a.jsx)(`tbody`,{children:m.map(e=>(0,a.jsxs)(`tr`,{children:[(0,a.jsx)(`td`,{className:`left`,children:r(e.subject_name)}),(0,a.jsx)(`td`,{children:r(e.subject_code)}),h.map(t=>(0,a.jsx)(`td`,{children:r((e.components||[]).find(e=>e.assessment_component_id===t.assessment_component_id)?.score)},t.assessment_component_id)),(0,a.jsx)(`td`,{className:`strong`,children:r(e.total_score)}),(0,a.jsx)(`td`,{children:r(e.grade)}),(0,a.jsx)(`td`,{className:`left`,children:r(e.remark,``)})]},e.id||e.subject_id))})]}),(0,a.jsxs)(`section`,{className:`rc-comments`,children:[(0,a.jsx)(f,{title:`Class teacher's comment`,value:r(e.class_teacher_comment,`No class teacher comment provided.`)}),(0,a.jsx)(f,{title:`Principal's comment`,value:r(e.principal_comment,`No principal comment provided.`)})]}),(0,a.jsxs)(`section`,{className:`rc-signatures`,children:[(0,a.jsx)(`div`,{className:`rc-signature`,children:`Class teacher signature`}),(0,a.jsx)(`div`,{className:`rc-signature`,children:`Principal signature`})]}),(0,a.jsxs)(`footer`,{className:`rc-footer`,children:[(0,a.jsx)(`span`,{children:n}),(0,a.jsxs)(`span`,{children:[`Generated securely by Weave · Report `,e.id]})]})]})]})}function u({label:e,value:t}){return(0,a.jsxs)(`div`,{className:`rc-field`,children:[(0,a.jsx)(`span`,{children:e}),(0,a.jsx)(`strong`,{children:t||`--`})]})}function d({label:e,value:t}){return(0,a.jsxs)(`div`,{className:`rc-metric`,children:[(0,a.jsx)(`span`,{children:e}),(0,a.jsx)(`strong`,{children:t??`--`})]})}function f({title:e,value:t}){return(0,a.jsxs)(`article`,{className:`rc-comment`,children:[(0,a.jsx)(`h3`,{children:e}),(0,a.jsx)(`p`,{children:t})]})}function p(e,t,n){let r=new Set;return(e||[]).reduce((e,i)=>{let a=i?.[t];return!a||r.has(a)?e:(r.add(a),e.push({value:a,label:i?.[n]||`Unknown`}),e)},[])}function m({cards:e,sessionId:t,termId:n,onSessionChange:r,onTermChange:o}){let s=(0,i.useMemo)(()=>p(e,`academic_session_id`,`academic_session_name`),[e]),c=(0,i.useMemo)(()=>p((e||[]).filter(e=>!t||e.academic_session_id===t),`academic_term_id`,`academic_term_name`),[e,t]);return(0,i.useEffect)(()=>{n&&!c.some(e=>e.value===n)&&o(``)},[o,n,c]),(0,a.jsxs)(`div`,{className:`grid gap-3 sm:grid-cols-2`,children:[(0,a.jsxs)(`label`,{className:`block text-sm font-semibold text-text-soft`,children:[(0,a.jsx)(`span`,{className:`mb-1.5 block`,children:`Academic session`}),(0,a.jsxs)(`select`,{className:`input-base`,value:t,onChange:e=>{r(e.target.value),o(``)},children:[(0,a.jsx)(`option`,{value:``,children:`All sessions`}),s.map(e=>(0,a.jsx)(`option`,{value:e.value,children:e.label},e.value))]})]}),(0,a.jsxs)(`label`,{className:`block text-sm font-semibold text-text-soft`,children:[(0,a.jsx)(`span`,{className:`mb-1.5 block`,children:`Academic term`}),(0,a.jsxs)(`select`,{className:`input-base`,value:n,onChange:e=>o(e.target.value),children:[(0,a.jsx)(`option`,{value:``,children:`All terms`}),c.map(e=>(0,a.jsx)(`option`,{value:e.value,children:e.label},e.value))]})]})]})}function h(e,t,n){return(e||[]).filter(e=>(!t||e.academic_session_id===t)&&(!n||e.academic_term_id===n))}export{m as n,l as r,h as t};