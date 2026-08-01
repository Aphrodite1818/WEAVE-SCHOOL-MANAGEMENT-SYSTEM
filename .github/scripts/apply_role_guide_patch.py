from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:120]!r}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")


# Register the guide router.
replace_once(
    "backend/app/main.py",
    'from app.modules.subscriptions.router import router as subscriptions_router\n',
    'from app.modules.subscriptions.router import router as subscriptions_router\n'
    'from app.modules.user_guides.router import router as user_guides_router\n',
)
replace_once(
    "backend/app/main.py",
    '    app.include_router(subscriptions_router, prefix="/api/v1")\n',
    '    app.include_router(subscriptions_router, prefix="/api/v1")\n'
    '    app.include_router(user_guides_router, prefix="/api/v1")\n',
)

# Make shared academic controls searchable without changing every call site.
replace_once(
    "frontend/src/features/academic-admin/AcademicWorkspacePrimitives.jsx",
    'import Input from "../../components/ui/Input";\n',
    'import Input from "../../components/ui/Input";\n'
    'import SearchableSelect from "../../components/ui/SearchableSelect";\n',
)
replace_once(
    "frontend/src/features/academic-admin/AcademicWorkspacePrimitives.jsx",
    '''export function SelectControl({
  label,
  value,
  onChange,
  options,
  placeholder = "Select an option",
  required = false,
  disabled = false,
  error,
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-text-soft">
        {label}
      </span>
      <select
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
        className="input-base"
        required={required}
        disabled={disabled}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error ? <span className="mt-1 block text-xs text-error">{error}</span> : null}
    </label>
  );
}
''',
    '''export function SelectControl({
  label,
  value,
  onChange,
  options,
  placeholder = "Select an option",
  required = false,
  disabled = false,
  error,
  searchPlaceholder,
  searchable = true,
  clearable = false,
}) {
  return (
    <SearchableSelect
      label={label}
      value={value || ""}
      onChange={onChange}
      options={options}
      placeholder={placeholder}
      searchPlaceholder={
        searchPlaceholder || `Search ${String(label || "options").toLowerCase()}`
      }
      required={required}
      disabled={disabled}
      error={error}
      searchable={searchable}
      clearable={clearable}
    />
  );
}
''',
)

# Mobile Academic Hub workspace selection should use the same combobox.
replace_once(
    "frontend/src/features/academic-admin/AcademicWorkflowShell.jsx",
    'import Card from "../../components/ui/Card";\n',
    'import Card from "../../components/ui/Card";\n'
    'import SearchableSelect from "../../components/ui/SearchableSelect";\n',
)
replace_once(
    "frontend/src/features/academic-admin/AcademicWorkflowShell.jsx",
    '''            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">
                Workspace
              </span>
              <select
                value={workflow}
                onChange={(event) => selectWorkflow(event.target.value)}
                className="input-base"
              >
                {academicWorkflowOrder.map((key) => {
                  const item = academicWorkflowConfig[key];
                  return (
                    <option key={key} value={key}>
                      {item.title}
                    </option>
                  );
                })}
              </select>
            </label>
''',
    '''            <SearchableSelect
              label="Workspace"
              value={workflow}
              onChange={selectWorkflow}
              searchPlaceholder="Search academic workspaces"
              options={academicWorkflowOrder.map((key) => ({
                value: key,
                label: academicWorkflowConfig[key].title,
                description: academicWorkflowConfig[key].description,
              }))}
            />
''',
)

# Install role guides after profile onboarding is complete.
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    'import ProfileCompletionForm from "../shared/ProfileCompletionForm";\n',
    'import ProfileCompletionForm from "../shared/ProfileCompletionForm";\n'
    'import RoleGuideModal from "../guides/RoleGuideModal";\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    'import useOnboardingGate from "./useOnboardingGate";\n',
    'import useOnboardingGate from "./useOnboardingGate";\n'
    'import useRoleGuide from "../../features/guides/useRoleGuide";\n',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '''  } = useOnboardingGate({ role, enabled: onboardingModalEnabled });

  useEffect(() => {
''',
    '''  } = useOnboardingGate({ role, enabled: onboardingModalEnabled });
  const roleGuide = useRoleGuide({
    role,
    enabled:
      onboardingModalEnabled &&
      !onboardingState.loading &&
      !onboardingState.required &&
      !profileModalOpen,
  });

  useEffect(() => {
''',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '''      {shouldRenderAiLauncher ? <AiChatLauncher role={role} /> : null}
''',
    '''      <RoleGuideModal guide={roleGuide} />

      {shouldRenderAiLauncher ? <AiChatLauncher role={role} /> : null}
''',
)

# Add the persistent admin setup progress card.
replace_once(
    "frontend/src/pages/admin/AdminDashboardPage.jsx",
    'import LoadingState from "../../components/shared/LoadingState";\n',
    'import LoadingState from "../../components/shared/LoadingState";\n'
    'import AdminSetupProgressCard from "../../components/guides/AdminSetupProgressCard";\n',
)
replace_once(
    "frontend/src/pages/admin/AdminDashboardPage.jsx",
    '''          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
''',
    '''          <AdminSetupProgressCard stats={stats} />

          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
''',
)

# Teacher result entry: searchable roster that preserves unsaved drafts.
replace_once(
    "frontend/src/pages/teacher/ResultsPage.jsx",
    'import { Calculator, ClipboardList, Save, Send, Users } from "lucide-react";\n',
    'import { Calculator, ClipboardList, Save, Search, Send, Users } from "lucide-react";\n',
)
replace_once(
    "frontend/src/pages/teacher/ResultsPage.jsx",
    '  const [students, setStudents] = useState([]);\n',
    '  const [students, setStudents] = useState([]);\n'
    '  const [studentSearch, setStudentSearch] = useState("");\n',
)
replace_once(
    "frontend/src/pages/teacher/ResultsPage.jsx",
    '''  useEffect(() => {
    setDrafts({});
  }, [selectedAssignmentId, academicSessionId, academicTermId]);
''',
    '''  useEffect(() => {
    setDrafts({});
    setStudentSearch("");
  }, [selectedAssignmentId, academicSessionId, academicTermId]);
''',
)
replace_once(
    "frontend/src/pages/teacher/ResultsPage.jsx",
    '''  const resultByStudent = useMemo(
    () =>
      Object.fromEntries(
        results.map((result) => [result.student_id, result]),
      ),
    [results],
  );

  const maximumFor = (field) => {
''',
    '''  const resultByStudent = useMemo(
    () =>
      Object.fromEntries(
        results.map((result) => [result.student_id, result]),
      ),
    [results],
  );
  const visibleStudents = useMemo(() => {
    const query = studentSearch.trim().toLowerCase();
    if (!query) return students;
    return students.filter((student) =>
      `${displayStudent(student)} ${student.admission_number || ""}`
        .toLowerCase()
        .includes(query),
    );
  }, [studentSearch, students]);

  const maximumFor = (field) => {
''',
)
replace_once(
    "frontend/src/pages/teacher/ResultsPage.jsx",
    '''      <section className="mobile-scroll-list grid gap-3">
''',
    '''      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <label className="block min-w-0 flex-1">
            <span className="mb-1.5 block text-sm font-semibold text-text-soft">
              Search roster
            </span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-faint" />
              <input
                type="search"
                value={studentSearch}
                onChange={(event) => setStudentSearch(event.target.value)}
                placeholder="Student name or admission number"
                className="input-base pl-10"
              />
            </div>
          </label>
          <p className="text-sm font-medium text-text-muted">
            {visibleStudents.length} of {students.length} students
          </p>
        </div>
      </Card>

      <section className="mobile-scroll-list grid gap-3">
''',
)
replace_once(
    "frontend/src/pages/teacher/ResultsPage.jsx",
    '''        ) : (
          students.map((student) => {
''',
    '''        ) : visibleStudents.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No matching students"
            description="Try another student name or admission number. Unsaved scores remain in place."
          />
        ) : (
          visibleStudents.map((student) => {
''',
)

# Report-card readiness, generation, and lists support name/admission search.
replace_once(
    "frontend/src/features/academic-admin/ReportCardsWorkspace.jsx",
    'import { CheckCircle2, Eye, FileText, RefreshCw, TriangleAlert } from "lucide-react";\n',
    'import { CheckCircle2, Eye, FileText, RefreshCw, Search, TriangleAlert } from "lucide-react";\n',
)
replace_once(
    "frontend/src/features/academic-admin/ReportCardsWorkspace.jsx",
    'import { SelectControl, WorkspacePanel } from "./AcademicWorkspacePrimitives";\n',
    'import { Input, SelectControl, WorkspacePanel } from "./AcademicWorkspacePrimitives";\n',
)
replace_once(
    "frontend/src/features/academic-admin/ReportCardsWorkspace.jsx",
    '  const [selectedStudentId, setSelectedStudentId] = useState("");\n',
    '  const [selectedStudentId, setSelectedStudentId] = useState("");\n'
    '  const [studentQuery, setStudentQuery] = useState("");\n',
)
replace_once(
    "frontend/src/features/academic-admin/ReportCardsWorkspace.jsx",
    '''  const rows = overview?.items || [];
  const readyRows = rows.filter(
''',
    '''  const rows = overview?.items || [];
  const normalizedStudentQuery = studentQuery.trim().toLowerCase();
  const filteredRows = normalizedStudentQuery
    ? rows.filter((item) => studentLabel(item).toLowerCase().includes(normalizedStudentQuery))
    : rows;
  const filteredCards = normalizedStudentQuery
    ? cards.filter((item) =>
        `${item.student_name || ""} ${item.admission_number || ""}`
          .toLowerCase()
          .includes(normalizedStudentQuery),
      )
    : cards;
  const readyRows = rows.filter(
''',
)
replace_once(
    "frontend/src/features/academic-admin/ReportCardsWorkspace.jsx",
    '''        <WorkspacePanel title="Student readiness" description="Students require every expected subject result to be locked before generation.">
          <div className="space-y-3">
            {rows.map((item) => {
''',
    '''        <WorkspacePanel title="Student readiness" description="Students require every expected subject result to be locked before generation.">
          <div className="mb-4">
            <Input
              label="Search students"
              value={studentQuery}
              placeholder="Student name or admission number"
              onChange={(event) => setStudentQuery(event.target.value)}
            />
          </div>
          <div className="space-y-3">
            {filteredRows.map((item) => {
''',
)
replace_once(
    "frontend/src/features/academic-admin/ReportCardsWorkspace.jsx",
    '''            {generationTarget === "student" ? <SelectControl label="Student" value={selectedStudentId} onChange={setSelectedStudentId} options={rows.map((item) => ({ value: item.student_id, label: `${studentLabel(item)} · ${item.expected_count > 0 && item.submitted_count >= item.expected_count ? "Ready" : "Incomplete"}` }))} required /> : <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">{readyRows.length} of {rows.length} students are ready.</div>}
''',
    '''            {generationTarget === "student" ? (
              <div className="space-y-3">
                <Input
                  label="Search students"
                  value={studentQuery}
                  placeholder="Student name or admission number"
                  onChange={(event) => setStudentQuery(event.target.value)}
                />
                <SelectControl
                  label="Student"
                  value={selectedStudentId}
                  onChange={setSelectedStudentId}
                  searchPlaceholder="Search name or admission number"
                  options={filteredRows.map((item) => ({
                    value: item.student_id,
                    label: studentLabel(item),
                    description:
                      item.expected_count > 0 && item.submitted_count >= item.expected_count
                        ? "Ready for generation"
                        : "Incomplete results",
                    keywords: item.admission_number,
                  }))}
                  required
                />
              </div>
            ) : (
              <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
                {readyRows.length} of {rows.length} students are ready.
              </div>
            )}
''',
)
replace_once(
    "frontend/src/features/academic-admin/ReportCardsWorkspace.jsx",
    '''        <WorkspacePanel title={`${String(activeTab).replaceAll("-", " ")} report cards`} description={`${cards.length} matching report card${cards.length === 1 ? "" : "s"}.`}>
          {cards.length === 0 ? <div className="rounded-2xl border border-dashed border-border p-6 text-center"><FileText className="mx-auto h-7 w-7 text-text-muted" /><p className="mt-3 text-sm font-semibold text-text">No matching report cards</p></div> : <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">{cards.map((card) => <div key={card.id} className="flex min-h-[14rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4">''',
    '''        <WorkspacePanel title={`${String(activeTab).replaceAll("-", " ")} report cards`} description={`${filteredCards.length} matching report card${filteredCards.length === 1 ? "" : "s"}.`}>
          <div className="mb-4">
            <Input
              label="Search report cards"
              value={studentQuery}
              placeholder="Student name or admission number"
              onChange={(event) => setStudentQuery(event.target.value)}
            />
          </div>
          {filteredCards.length === 0 ? <div className="rounded-2xl border border-dashed border-border p-6 text-center"><Search className="mx-auto h-7 w-7 text-text-muted" /><p className="mt-3 text-sm font-semibold text-text">No matching report cards</p></div> : <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">{filteredCards.map((card) => <div key={card.id} className="flex min-h-[14rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4">''',
)

print("Role guide and searchable-filter patch applied.")
