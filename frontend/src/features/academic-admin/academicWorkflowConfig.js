import { BarChart3, BookOpen, CalendarDays, FileText, Layers3, Pencil, Ruler, School, Users } from "lucide-react";

export const academicWorkflowOrder = [
  "sessions", "terms", "levels", "arm-labels", "classes", "departments",
  "subjects", "curriculum", "assignments", "school-calendar", "grading", "results",
  "report-cards", "progression",
];

export const academicWorkflowConfig = {
  levels:{title:"Academic Levels",shortTitle:"Levels",description:"Define curriculum levels with institution-valid categories and progression positions.",icon:Layers3,tone:"primary",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"create",label:"Create Level"},{id:"manage",label:"Manage Levels"}]},
  progression:{title:"Automatic Progression",shortTitle:"Progression",description:"Review level transitions and terminal levels before session closure.",icon:Layers3,tone:"success",defaultTab:"transitions",tabs:[{id:"transitions",label:"Level Transitions"}]},
  "arm-labels":{title:"Arm Labels",shortTitle:"Arm Labels",description:"Manage reusable labels such as A, B and C. Labels do not carry academic meaning.",icon:School,tone:"accent",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"create",label:"Add Arm Label"}]},
  classes:{title:"Classes",shortTitle:"Classes",description:"Create concrete class arms from a level and arm label; specialization is configured per term.",icon:School,tone:"primary",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"create",label:"Create Class"},{id:"active",label:"Active Classes"},{id:"inactive",label:"Inactive Classes"},{id:"archived",label:"Archived Classes"}]},
  departments:{title:"Departments",shortTitle:"Departments",description:"Configure specializations for levels whose institution category supports departments.",icon:Users,tone:"warning",defaultTab:"overview",tabs:[{id:"overview",label:"Level Departments"}]},
  subjects:{title:"Subjects",shortTitle:"Subjects",description:"Manage the school-wide subject pool. Curriculum decides where each subject is taught.",icon:BookOpen,tone:"success",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"create",label:"Create Subject"},{id:"active",label:"Active Subjects"},{id:"inactive",label:"Inactive Subjects"},{id:"archived",label:"Archived Subjects"}]},
  curriculum:{title:"Curriculum",shortTitle:"Curriculum",description:"Attach subjects to academic levels. Subjects are compulsory unless explicitly marked elective.",icon:BookOpen,tone:"accent",defaultTab:"subjects",tabs:[{id:"subjects",label:"Curriculum Subjects"}]},
  assignments:{title:"Teacher Assignments",shortTitle:"Assignments",description:"Assign teachers to the subjects they are authorized to teach in concrete class arms.",icon:Users,tone:"warning",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"assign",label:"Assign Teacher"},{id:"reassign",label:"Reassign Teacher"},{id:"end",label:"End Assignment"},{id:"history",label:"Assignment History"}]},
  sessions:{title:"Academic Sessions",shortTitle:"Sessions",description:"Create school years, open the current year, and close a completed year with explicit readiness checks.",icon:CalendarDays,tone:"primary",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"create",label:"Create Session"},{id:"draft",label:"Draft Sessions"},{id:"open",label:"Open Session"},{id:"closing",label:"Closing"},{id:"closed",label:"Closed Sessions"}]},
  terms:{title:"Academic Terms",shortTitle:"Terms",description:"Create, edit, open and close academic terms.",icon:CalendarDays,tone:"success",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"create",label:"Create Term"},{id:"draft",label:"Draft Terms"},{id:"open",label:"Open Term"},{id:"closing",label:"Closing Terms"},{id:"closed",label:"Closed Terms"}]},
  grading:{title:"Grading Configuration",shortTitle:"Grading",description:"Set assessment components and grading rules before processing results.",icon:Ruler,tone:"warning",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"assessment-schemes",label:"Assessment Scheme"},{id:"create",label:"Create Rule"},{id:"active",label:"Active Rules"},{id:"inactive",label:"Inactive Rules"}]},
  results:{title:"Results Management",shortTitle:"Results",description:"Manage assessment scores and result lifecycle states.",icon:Pencil,tone:"accent",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"entry",label:"Score Entry"},{id:"bulk-actions",label:"Bulk Actions"},{id:"draft",label:"Draft"},{id:"submitted",label:"Submitted"},{id:"approved",label:"Approved"},{id:"locked",label:"Locked"}]},
  "report-cards":{title:"Report Cards",shortTitle:"Reports",description:"Review readiness, generate student report cards and publish completed records.",icon:FileText,tone:"primary",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"ready",label:"Student Readiness"},{id:"generate",label:"Generate"},{id:"bulk-actions",label:"Bulk Actions"},{id:"draft",label:"Draft Cards"},{id:"published",label:"Published Cards"},{id:"outdated",label:"Outdated Cards"},{id:"archived",label:"Archived Versions"}]},
  "school-calendar":{title:"School Calendar",shortTitle:"Calendar",description:"Set school days, holidays, events and closures for the selected term.",icon:CalendarDays,tone:"success",defaultTab:"overview",tabs:[{id:"overview",label:"Overview"},{id:"setup",label:"Setup"},{id:"calendar",label:"Calendar"},{id:"events",label:"Events"},{id:"closures",label:"Closures"},{id:"history",label:"History"}]},
};

export const academicToneStyles={primary:"bg-primary-soft text-primary",success:"bg-success-soft text-success",warning:"bg-warning-soft text-amber-900",accent:"bg-accent-soft text-accent",neutral:"bg-surface-muted text-text-muted"};
export const academicWorkflowSummaryCards=[
 {label:"Sessions",description:"School year lifecycle",to:"/admin/academic/sessions",icon:CalendarDays},
 {label:"Terms",description:"Term lifecycle and opening",to:"/admin/academic/terms",icon:CalendarDays},
 {label:"Levels",description:"Curriculum category and progression",to:"/admin/academic/levels",icon:Layers3},
 {label:"Arm Labels",description:"Reusable class arm labels",to:"/admin/academic/arm-labels",icon:School},
 {label:"Classes",description:"Level + arm class groups",to:"/admin/academic/classes",icon:School},
 {label:"Departments",description:"Level specialization",to:"/admin/academic/departments",icon:Users},
 {label:"Subjects",description:"School subject pool",to:"/admin/academic/subjects",icon:BookOpen},
 {label:"Curriculum",description:"Subjects taught at each level",to:"/admin/academic/curriculum",icon:BookOpen},
 {label:"Assignments",description:"Who teaches each class subject",to:"/admin/academic/assignments",icon:Users},
 {label:"Calendar",description:"Term days and school events",to:"/admin/academic/school-calendar",icon:CalendarDays},
 {label:"Grading",description:"Assessment and score rules",to:"/admin/academic/grading",icon:Ruler},
 {label:"Results",description:"Scores and lifecycle",to:"/admin/academic/results",icon:BarChart3},
 {label:"Reports",description:"Report card generation",to:"/admin/academic/report-cards",icon:FileText},
];
