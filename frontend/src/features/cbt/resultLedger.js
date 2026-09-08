export const RESULT_ITEM_OUTCOMES = ["applied", "unchanged", "rejected"];

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export class ResultLedgerFilterError extends Error {
  constructor(message) {
    super(message);
    this.name = "ResultLedgerFilterError";
  }
}

const optionalUuid = (value, label) => {
  const normalized = String(value || "").trim();
  if (!normalized) return undefined;
  if (!UUID_PATTERN.test(normalized)) {
    throw new ResultLedgerFilterError(
      `The selected ${label} is no longer valid. Refresh the filter options and try again.`,
    );
  }
  return normalized;
};

const startOfLocalDay = (value) =>
  value ? new Date(`${value}T00:00:00`).toISOString() : undefined;

const endOfLocalDay = (value) =>
  value ? new Date(`${value}T23:59:59.999`).toISOString() : undefined;

export function buildResultLedgerQuery({
  filters = {},
  page = 1,
  pageSize = 25,
  role = "admin",
} = {}) {
  if (filters.createdFrom && filters.createdTo && filters.createdFrom > filters.createdTo) {
    throw new ResultLedgerFilterError("From date cannot be after to date.");
  }

  const query = {
    skip: Math.max(0, Number(page) - 1) * Number(pageSize),
    limit: Number(pageSize),
  };
  const sourceExamId = optionalUuid(filters.sourceExamId, "exam");
  const academicSessionId = optionalUuid(filters.academicSessionId, "academic session");
  const academicTermId = optionalUuid(filters.academicTermId, "academic term");
  const academicLevelId = optionalUuid(filters.academicLevelId, "academic level");
  const curriculumSubjectId = optionalUuid(filters.curriculumSubjectId, "subject");
  const assessmentComponentId = optionalUuid(
    filters.assessmentComponentId,
    "assessment component",
  );

  if (sourceExamId) query.source_exam_id = sourceExamId;
  if (academicSessionId) query.academic_session_id = academicSessionId;
  if (academicTermId) query.academic_term_id = academicTermId;
  if (academicLevelId) query.academic_level_id = academicLevelId;
  if (curriculumSubjectId) query.curriculum_subject_id = curriculumSubjectId;
  if (assessmentComponentId) {
    query.assessment_component_id = assessmentComponentId;
  }
  if (filters.ingestionReference?.trim()) {
    query.ingestion_reference = filters.ingestionReference.trim();
  }
  if (filters.status) query.status = filters.status;
  if (filters.createdFrom) query.created_from = startOfLocalDay(filters.createdFrom);
  if (filters.createdTo) query.created_to = endOfLocalDay(filters.createdTo);

  const serverId = optionalUuid(filters.serverId, "CBT server");
  if (serverId) query.cbt_server_id = serverId;

  if (role === "superadmin") {
    const tenantId = optionalUuid(filters.tenantId, "tenant");
    if (tenantId) query.tenant_id = tenantId;
  }

  return query;
}

export function summarizeResultBatches(items = [], total = 0) {
  return items.reduce(
    (summary, batch) => ({
      ...summary,
      received: summary.received + Number(batch.received_count || 0),
      applied: summary.applied + Number(batch.applied_count || 0),
      rejected: summary.rejected + Number(batch.rejected_count || 0),
    }),
    {
      total: Number(total || 0),
      received: 0,
      applied: 0,
      rejected: 0,
    },
  );
}
