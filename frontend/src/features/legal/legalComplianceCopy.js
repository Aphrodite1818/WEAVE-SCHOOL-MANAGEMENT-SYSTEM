export const LEGAL_POLICY_VERSION = "weave-legal-compliance-v1";

export const legalComplianceSections = [
  {
    title: "What Weave Is",
    body:
      "Weave is a school management workspace for administrators, teachers, students, and parents. It supports school setup, student records, attendance, class and subject management, academic results, report cards, communications, subscriptions, and related operational workflows.",
  },
  {
    title: "Data Weave Handles",
    body:
      "Weave stores account details, school profile data, student academic records, class assignments, attendance records, result and report-card data, parent-student links, messages, announcements, notifications, uploaded profile media, billing metadata, security events, and audit information needed to run the school workspace.",
  },
  {
    title: "How Data Is Used",
    body:
      "Data is used to authenticate users, authorize role-based access, provide school workflows, generate operational reports, deliver communications, protect accounts, investigate abuse, maintain service reliability, and meet school administration responsibilities.",
  },
  {
    title: "Access And Privacy",
    body:
      "Users only see data permitted by their role and school membership. Tenant administrators manage school-owned records. Teachers access assigned academic work. Students access their own school records. Parents access linked student information approved for their account. Weave does not authorize users to browse another school tenant's data.",
  },
  {
    title: "Security Responsibilities",
    body:
      "Keep passwords, access codes, verification codes, and session devices private. Report suspicious access immediately. Do not share another user's credentials, attempt to bypass role permissions, scrape data, probe the platform, or upload harmful files.",
  },
  {
    title: "School And User Responsibilities",
    body:
      "Schools are responsible for entering accurate records, inviting the right users, maintaining lawful consent for student and parent data, correcting inaccurate records, and using exports or reports responsibly. Users must only enter truthful information and use Weave for legitimate school purposes.",
  },
  {
    title: "Communications",
    body:
      "Messages, announcements, and notifications may be visible to intended school recipients and authorized administrators. Do not use Weave to harass, impersonate, spam, share illegal content, or disclose sensitive information to people who should not receive it.",
  },
  {
    title: "Student Data",
    body:
      "Student data must be handled with extra care. Do not post student information outside Weave unless your school policy and applicable law allow it. Parents and students should use their access only for their own linked records.",
  },
  {
    title: "Billing And Platform Operations",
    body:
      "Subscription and payment workflows may use third-party payment processors. Weave may record plan, entitlement, verification, and transaction metadata needed to keep the workspace active and enforce selected limits.",
  },
  {
    title: "Acceptance",
    body:
      "By accepting, you agree to use Weave according to these rules and your school's policies. If you reject, your account remains signed in but onboarding and guided setup will not continue until you accept.",
  },
];

export const legalComplianceChecklist = [
  "I will use Weave only for legitimate school, teaching, student, parent, or platform administration work.",
  "I will protect login credentials, access codes, verification codes, and devices used to access Weave.",
  "I will not try to access another school, account, role, student, parent, teacher, or admin record without permission.",
  "I will handle student and parent data carefully and share it only through approved school processes.",
  "I understand that accepting is required before onboarding and guided setup can continue.",
];

export const roleLegalCompliance = {
  admin: {
    label: "Tenant administrator",
    sections: [
      {
        title: "Your Role On Weave",
        body:
          "Tenant administrators manage the school workspace. This includes school setup, student records, staff records, class and subject setup, academic sessions, terms, calendars, invitations, announcements, report-card workflows, subscription settings, and school branding where available.",
      },
      {
        title: "Do",
        items: [
          "Create and update school records only from verified school information.",
          "Invite teachers, parents, and students only when the school has authority to do so.",
          "Review academic lifecycle actions carefully before opening sessions, activating calendars, opening terms, closing terms, or progressing classes.",
          "Use subscription and branding settings only for the school tenant you administer.",
          "Correct inaccurate records promptly when the school becomes aware of an error.",
        ],
      },
      {
        title: "Do Not",
        items: [
          "Do not create fake students, parents, teachers, classes, results, attendance, or report cards.",
          "Do not share student or parent data outside approved school processes.",
          "Do not invite users to records they should not access.",
          "Do not bypass lifecycle warnings, audit expectations, role permissions, or subscription limits.",
          "Do not use Weave subscription settings as a student fee billing system; Weave subscription billing is for the school's access to Weave.",
        ],
      },
    ],
    checklist: [
      "I understand I am responsible for school-owned records I create or approve in Weave.",
      "I will invite only authorized users and protect student and parent information.",
      "I will use lifecycle, subscription, branding, and communication tools only for legitimate school administration.",
    ],
  },
  teacher: {
    label: "Teacher",
    sections: [
      {
        title: "Your Role On Weave",
        body:
          "Teachers use Weave for assigned teaching work. This may include assigned classes, attendance, score entry, student academic context, report inputs, school calendar visibility, messages, announcements, and notifications.",
      },
      {
        title: "Do",
        items: [
          "Use Weave only for classes, subjects, students, and tasks assigned to you.",
          "Enter attendance and scores accurately and submit them according to school policy.",
          "Protect student academic information and discuss it only through approved school channels.",
          "Report incorrect class assignments, student records, or suspicious access to the school administrator.",
          "Use communication tools professionally and only for school-related work.",
        ],
      },
      {
        title: "Do Not",
        items: [
          "Do not view, copy, or share student information outside your authorized teaching responsibility.",
          "Do not enter false attendance, scores, comments, or academic records.",
          "Do not impersonate another teacher, parent, student, or administrator.",
          "Do not use messages or announcements to harass, pressure, spam, or disclose sensitive information.",
          "Do not share your teacher account or allow students or parents to use it.",
        ],
      },
    ],
    checklist: [
      "I will use Weave only for my assigned school teaching responsibilities.",
      "I will enter attendance, scores, and comments truthfully.",
      "I will protect student information and communicate professionally.",
    ],
  },
  parent: {
    label: "Parent or guardian",
    sections: [
      {
        title: "Your Role On Weave",
        body:
          "Parents and guardians use Weave to view information for linked children approved by the school. This may include attendance, report cards, school announcements, calendar information, messages, and parent-student link requests.",
      },
      {
        title: "Do",
        items: [
          "Access only the child or children linked to your parent account.",
          "Review attendance, report cards, and announcements for your own family context.",
          "Keep your login private and report any wrong child link immediately.",
          "Use parent communication tools respectfully and for school-related matters.",
          "Tell the school when your contact details or relationship to a student changes.",
        ],
      },
      {
        title: "Do Not",
        items: [
          "Do not try to access another child's record or another parent's account.",
          "Do not share screenshots or reports containing student information with people who should not see them.",
          "Do not use Weave to harass staff, students, parents, or administrators.",
          "Do not submit false link requests or misrepresent your relationship to a student.",
          "Do not treat Weave as an official fee-payment portal unless the school separately tells you a supported payment workflow exists.",
        ],
      },
    ],
    checklist: [
      "I will access only my approved linked child records.",
      "I will protect student information I can view as a parent or guardian.",
      "I will use Weave communication tools respectfully and for school matters.",
    ],
  },
  student: {
    label: "Student",
    sections: [
      {
        title: "Your Role On Weave",
        body:
          "Students use Weave to view their own school information. This may include profile details, class context, assigned subjects, attendance visibility, report cards, announcements, calendar information, and notifications shared by the school.",
      },
      {
        title: "Do",
        items: [
          "Use only your own student account and keep your password private.",
          "Review your class, attendance, report cards, announcements, and school updates responsibly.",
          "Tell a teacher, parent, or administrator if your record looks wrong.",
          "Use communication and account features respectfully and only for school purposes.",
          "Follow your school's technology and conduct rules while using Weave.",
        ],
      },
      {
        title: "Do Not",
        items: [
          "Do not try to access another student's account, report card, attendance, or profile.",
          "Do not share your access code, password, verification code, or session device.",
          "Do not upload harmful content, impersonate another person, or attempt to bypass permissions.",
          "Do not use Weave to bully, harass, threaten, or embarrass another student or staff member.",
          "Do not change or submit information that you know is false.",
        ],
      },
    ],
    checklist: [
      "I will use only my own student account.",
      "I will keep my login details private.",
      "I will use Weave respectfully and follow school rules.",
    ],
  },
  superadmin: {
    label: "Platform administrator",
    sections: [
      {
        title: "Your Role On Weave",
        body:
          "Platform administrators support Weave operations across tenants. This role is for platform maintenance, tenant support, security review, subscription support, and service reliability.",
      },
      {
        title: "Do",
        items: [
          "Access tenant information only when needed for platform support, security, compliance, or authorized operations.",
          "Keep operational access limited, auditable, and tied to legitimate support work.",
          "Handle tenant and school data with strict confidentiality.",
        ],
      },
      {
        title: "Do Not",
        items: [
          "Do not browse tenant data without a legitimate operational reason.",
          "Do not alter school records unless the action is authorized and necessary.",
          "Do not disclose tenant information outside approved platform operations.",
        ],
      },
    ],
    checklist: [
      "I will use platform access only for legitimate Weave operations.",
      "I will keep tenant data confidential.",
      "I will avoid unnecessary access to school-owned records.",
    ],
  },
};

export function normalizeLegalRole(role) {
  const value = String(role || "").trim().toLowerCase();
  if (value === "tenant_admin") return "admin";
  if (roleLegalCompliance[value]) return value;
  return "admin";
}

export function getRoleLegalCompliance(role) {
  return roleLegalCompliance[normalizeLegalRole(role)] || roleLegalCompliance.admin;
}
