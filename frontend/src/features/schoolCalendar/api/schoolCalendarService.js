import { api } from "../../../services/api";

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

  getUpcoming: (params = {}, options = {}) =>
    api.get(`/school-calendar/upcoming${queryString(params)}`, options),

  getConfiguration: (options = {}) =>
    api.get("/tenant-admin/school-calendar/configuration", options),

  updateConfiguration: (payload) =>
    api.put("/tenant-admin/school-calendar/configuration", payload),

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
      .then(normalizeList),

  updateDay: (calendarDate, payload) =>
    api.patch(`/tenant-admin/school-calendar/days/${calendarDate}`, payload),

  updateDateRange: (payload) =>
    api.patch("/tenant-admin/school-calendar/date-range", payload),

  emergencyClosure: (payload) =>
    api.post("/tenant-admin/school-calendar/emergency-closure", payload),

  createEvent: (payload) =>
    api.post("/tenant-admin/school-calendar/events", payload),

  updateEvent: (eventId, payload) =>
    api.patch(`/tenant-admin/school-calendar/events/${eventId}`, payload),

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
