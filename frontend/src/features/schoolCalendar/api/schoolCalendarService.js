import { api } from "../../../services/api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
  rememberById,
  rememberRecord,
} from "../../../services/patchPayload";

const daySnapshots = new Map();
const eventSnapshots = new Map();
let configurationSnapshot = null;

const queryString = (params = {}) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
};

const normalizeList = (response) => ({
  ...response,
  items: Array.isArray(response?.items) ? response.items : [],
  total: Number.isFinite(response?.total) ? response.total : response?.items?.length ?? 0,
});

const daySnapshotKey = (calendarId, calendarDate) =>
  `${String(calendarId || "")}:${String(calendarDate || "")}`;

const rememberDays = (response) => {
  const normalized = normalizeList(response);
  normalized.items.forEach((day) => {
    daySnapshots.set(daySnapshotKey(day.calendar_id, day.calendar_date), day);
  });
  return normalized;
};

const rememberEvents = (response) => {
  const normalized = normalizeList(response);
  rememberById(eventSnapshots, normalized);
  return normalized;
};

export const schoolCalendarService = {
  getToday: (params = {}, options = {}) =>
    api.get(`/school-calendar/today${queryString(params)}`, options),

  getRange: (params = {}, options = {}) =>
    api
      .get(`/school-calendar/range${queryString(params)}`, options)
      .then(normalizeList),

  getEvents: (params = {}, options = {}) =>
    api
      .get(`/school-calendar/events${queryString(params)}`, options)
      .then(normalizeList),

  getAdminEvents: (params = {}, options = {}) =>
    api
      .get(`/tenant-admin/school-calendar/events${queryString(params)}`, options)
      .then(rememberEvents),

  getUpcoming: (params = {}, options = {}) =>
    api.get(`/school-calendar/upcoming${queryString(params)}`, options),

  getConfiguration: async (options = {}) => {
    const response = await api.get(
      "/tenant-admin/school-calendar/configuration",
      options,
    );
    configurationSnapshot = response;
    return response;
  },

  updateConfiguration: async (payload) => {
    const changes = buildChangedPatch(configurationSnapshot, payload);
    if (!hasPatchChanges(changes)) return configurationSnapshot;

    const response = await api.put(
      "/tenant-admin/school-calendar/configuration",
      changes,
    );
    configurationSnapshot = mergePatchResult(
      configurationSnapshot,
      changes,
      response,
    );
    return response;
  },

  listAdminCalendars: (params = {}, options = {}) =>
    api
      .get(`/tenant-admin/school-calendar${queryString(params)}`, options)
      .then(normalizeList),

  generateCalendar: (payload) =>
    api.post("/tenant-admin/school-calendar/generate", payload),

  activateCalendar: (calendarId) =>
    api.post(`/tenant-admin/school-calendar/${calendarId}/activate`, {
      confirmation: "ACTIVATE_SCHOOL_CALENDAR",
    }),

  archiveCalendar: (calendarId, payload = {}) =>
    api.post(`/tenant-admin/school-calendar/${calendarId}/archive`, {
      confirmation: "ARCHIVE_SCHOOL_CALENDAR",
      ...payload,
    }),

  getDays: (params = {}, options = {}) =>
    api
      .get(`/tenant-admin/school-calendar/days${queryString(params)}`, options)
      .then(rememberDays),

  updateDay: async (calendarDate, payload) => {
    const key = daySnapshotKey(payload?.calendar_id, calendarDate);
    const current = daySnapshots.get(key);
    const changes = buildChangedPatch(current, payload);
    if (!hasPatchChanges(changes)) return current;

    const response = await api.patch(
      `/tenant-admin/school-calendar/days/${calendarDate}`,
      changes,
    );
    daySnapshots.set(key, mergePatchResult(current, changes, response));
    return response;
  },

  updateDateRange: (payload) =>
    api.patch("/tenant-admin/school-calendar/date-range", payload),

  emergencyClosure: (payload) =>
    api.post("/tenant-admin/school-calendar/emergency-closure", payload),

  createEvent: async (payload) => {
    const response = await api.post(
      "/tenant-admin/school-calendar/events",
      payload,
    );
    return rememberRecord(eventSnapshots, response);
  },

  updateEvent: async (eventId, payload) => {
    const key = String(eventId);
    const current = eventSnapshots.get(key);
    const changes = buildChangedPatch(current, payload);
    if (!hasPatchChanges(changes)) return current;

    const response = await api.patch(
      `/tenant-admin/school-calendar/events/${eventId}`,
      changes,
    );
    eventSnapshots.set(key, mergePatchResult(current, changes, response));
    return response;
  },

  publishEvent: (eventId) =>
    api.post(`/tenant-admin/school-calendar/events/${eventId}/publish`, {
      confirmation: "PUBLISH_SCHOOL_CALENDAR_EVENT",
    }),

  cancelEvent: (eventId, reason) =>
    api.post(`/tenant-admin/school-calendar/events/${eventId}/cancel`, {
      confirmation: "CANCEL_SCHOOL_CALENDAR_EVENT",
      reason,
    }),
};
