const copy = {
  dashboard: ["Your everyday starting point", "Get an overview of your school day and pick up where you left off.", ["Your overview", "Recent activity", "Quick access"]],
  analytics: ["See the bigger picture", "Explore the summaries available to your role and follow progress over time.", ["Clear summaries", "Progress over time", "A closer look"]],
  calendar: ["Keep school dates close", "Find the term dates, school events, holidays, and closures shared with you.", ["School dates", "Events", "Holidays & closures"]],
  academic: ["Give your school its structure", "Start with a session, term, and calendar. Return here for levels, departments, classes, and curriculum when you need them.", ["School year", "Classes & levels", "Curriculum"]],
  students: ["Know your students", "Find student records and manage enrolment in your school.", ["Student directory", "Student records", "Enrolments"]],
  teachers: ["Meet your teaching team", "Find your teachers and manage their school memberships.", ["Teacher directory", "Teacher records", "School memberships"]],
  parents: ["Connect school and home", "Find parent records and review their links to students.", ["Parent directory", "Parent records", "Student links"]],
  imports: ["Bring your records together", "Import supported school records in batches when you are ready to add your data.", ["Prepare a file", "Review records", "Import results"]],
  classes: ["Find your classes", "Organise class arms and view the classes in your school.", ["Class arms", "Academic levels", "Class records"]],
  subjects: ["Find your subjects", "Explore the subjects available in your school workspace.", ["Subject list", "Subject details", "Academic context"]],
  attendance: ["Follow school attendance", "Review the attendance information and actions available to your role.", ["School days", "Attendance records", "Attendance summaries"]],
  inbox: ["Keep up with updates", "Find notifications and updates that need your attention.", ["New updates", "Read notifications", "Open related work"]],
  messages: ["Stay in touch", "Open the conversations available in your school workspace.", ["Conversations", "Read messages", "Replies"]],
  notices: ["Stay informed", "Read school notices and open the details of an announcement.", ["School notices", "Notice details", "Shared information"]],
  received: ["Find notices sent to you", "Read the notices shared directly with your workspace.", ["Received notices", "Notice details", "School updates"]],
  "report-cards": ["Find published report cards", "View report cards when the school has published them.", ["Choose a term", "Published reports", "Print a report"]],
  results: ["Follow academic results", "Review the results the school makes available for your linked children.", ["Linked children", "Term results", "Subject results"]],
  billing: ["Manage your school plan", "Review your term plan and payment history when you need them.", ["Term plan", "Plan options", "Payment history"]],
  cbt: ["Connect computer-based testing", "Manage the CBT server connections available to your school.", ["School servers", "Pairing", "Connection status"]],
  usage: ["Understand your plan usage", "Check the usage information available for your school plan.", ["Current usage", "Plan limits", "School resources"]],
  settings: ["Make your workspace yours", "Find your profile and the settings available to your role.", ["Profile", "Preferences", "Workspace settings"]],
  "student-linking": ["Connect with your children", "Review your student links and follow the school's linking process.", ["Linked students", "Linking requests", "School connections"]],
  "parent-linking": ["Connect with your parent", "Review your parent links and the linking options provided by your school.", ["Parent links", "Linking requests", "School connections"]],
  "student-comments": ["Support your class at report time", "If you are a class teacher, review academic performance and prepare student comments when results are ready.", ["Your class", "Student comments", "Submission status"]],
  "comment-templates": ["Keep useful wording handy", "Find your saved comment templates to help with class-teacher comments.", ["Saved templates", "Reusable wording", "Your collection"]],
  schools: ["Move between your schools", "Select a school membership to open that school's workspace.", ["Your memberships", "Select a school", "School workspace"]],
};

export function tourContentForItem(role, item) {
  const segment = item.to.split("/").filter(Boolean).at(-1);
  let entry = copy[segment] || copy.dashboard;
  if (role === "teacher" && segment === "students") entry = ["Meet the students you teach", "Find the students in your teaching rosters and their class context.", ["Teaching rosters", "Your students", "Class context"]];
  if (role === "teacher" && segment === "subjects") entry = ["See your teaching assignments", "Find the subjects assigned to you and open the teaching work available for each one.", ["Assigned subjects", "Class assignments", "Teaching work"]];
  if (role === "teacher" && segment === "classes") entry = ["Your class-teacher workspace", "If you are assigned as a class teacher, find your class and the duties available to you here.", ["Your assigned class", "Class roster", "Class-teacher duties"]];
  if (role === "admin" && segment === "report-cards") entry = ["Bring term reports together", "Review your school's report-card workflow when you are ready to work with results.", ["Term reports", "Report review", "Publication"]];
  return { ...item, title: entry[0], description: entry[1], preview: entry[2] };
}
