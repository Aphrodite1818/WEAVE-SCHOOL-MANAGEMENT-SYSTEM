export const BULK_IMPORT_REALTIME_EVENTS = [
  "bulk_import.started",
  "bulk_import.progress",
  "bulk_import.completed",
  "bulk_import.partially_completed",
  "bulk_import.failed",
  "bulk_import.cancelled",
];

export const SESSION_PROGRESSION_REALTIME_EVENTS = [
  "academic_session.progression.started",
  "academic_session.progression.completed",
  "academic_session.progression.failed",
];

export const matchesBulkImportEvent = (jobId, message) =>
  Boolean(jobId) && String(message?.data?.job_id || "") === String(jobId);

export const matchesSessionProgressionEvent = (sessionId, message) =>
  Boolean(sessionId) && String(message?.data?.session_id || "") === String(sessionId);

export const matchesCbtPairingEvent = (pairingRequestId, message) =>
  Boolean(pairingRequestId) &&
  String(message?.data?.pairing_request_id || "") === String(pairingRequestId);
