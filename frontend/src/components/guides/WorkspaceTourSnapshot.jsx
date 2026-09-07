const segmentFor = (step) => step?.to?.split("/").filter(Boolean).at(-1) || "dashboard";

const MiniRow = ({ label, wide = false }) => (
  <div className="workspace-tour-snapshot-row">
    <span className="workspace-tour-snapshot-dot" />
    <span className={wide ? "workspace-tour-snapshot-line wide" : "workspace-tour-snapshot-line"}>{label}</span>
  </div>
);

const visibleLabels = (visibleRoutes = []) => {
  const labels = [];
  const add = (route, label) => {
    if (visibleRoutes.some((item) => item === route || item.endsWith(route))) labels.push(label);
  };
  add("/students", "Students");
  add("/teachers", "Teachers");
  add("/report-cards", "Reports");
  add("/calendar", "Calendar");
  add("/attendance", "Attendance");
  return labels.slice(0, 4);
};

export default function WorkspaceTourSnapshot({ step, visibleRoutes = [] }) {
  const segment = segmentFor(step);

  if (segment === "calendar") {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <div className="workspace-tour-snapshot-top"><span /><span /><span /></div>
        <div className="workspace-tour-mini-calendar">
          {Array.from({ length: 28 }, (_, index) => <span key={index} className={index === 10 ? "active" : ""} />)}
        </div>
      </div>
    );
  }

  if (segment === "analytics" || segment === "usage") {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <div className="workspace-tour-snapshot-top"><span /><span /><span /></div>
        <div className="workspace-tour-mini-bars">
          {[42, 68, 54, 82, 61, 74].map((height, index) => <span key={index} style={{ height: `${height}%` }} />)}
        </div>
      </div>
    );
  }

  if (["academic", "classes", "subjects"].includes(segment)) {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <div className="workspace-tour-snapshot-top"><span /><span /><span /></div>
        <div className="workspace-tour-mini-flow">
          <span>Session</span><i />
          <span>Term</span><i />
          <span>{segment === "subjects" ? "Subjects" : "Classes"}</span>
        </div>
        <MiniRow label="Curriculum" wide />
      </div>
    );
  }

  if (["students", "teachers", "parents", "student-linking", "parent-linking", "classes", "subjects"].includes(segment)) {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <div className="workspace-tour-snapshot-search" />
        <MiniRow label="Record one" wide />
        <MiniRow label="Record two" />
        <MiniRow label="Record three" wide />
      </div>
    );
  }

  if (["inbox", "messages", "notices", "received"].includes(segment)) {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <div className="workspace-tour-snapshot-top"><span /><span /><span /></div>
        <MiniRow label="Latest update" wide />
        <MiniRow label="School message" />
        <MiniRow label="Another update" wide />
      </div>
    );
  }

  if (["billing", "cbt"].includes(segment)) {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <div className="workspace-tour-mini-plan">
          <span className="workspace-tour-mini-badge">{segment === "billing" ? "Plan" : "Server"}</span>
          <strong>{segment === "billing" ? "Current term" : "Connected"}</strong>
          <div className="workspace-tour-snapshot-meter"><span /></div>
        </div>
      </div>
    );
  }

  if (["report-cards", "results", "student-comments", "comment-templates"].includes(segment)) {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <div className="workspace-tour-mini-document">
          <span className="workspace-tour-mini-document-title" />
          <span /><span /><span /><span />
        </div>
      </div>
    );
  }

  if (segment === "settings") {
    return (
      <div className="workspace-tour-snapshot" aria-hidden="true">
        <MiniRow label="Profile" wide />
        <div className="workspace-tour-mini-setting"><span>Workspace preferences</span><i /></div>
        <div className="workspace-tour-mini-setting"><span>Workspace tour</span><i className="on" /></div>
      </div>
    );
  }

  const labels = visibleLabels(visibleRoutes);
  return (
    <div className="workspace-tour-snapshot" aria-hidden="true">
      <div className="workspace-tour-snapshot-top"><span /><span /><span /></div>
      <div className="workspace-tour-mini-kpis">
        {(labels.length ? labels : ["Overview", "Calendar", "Reports"]).map((label) => (
          <div key={label}><strong>{label}</strong><span /></div>
        ))}
      </div>
      <MiniRow label="Recent activity" wide />
    </div>
  );
}
