import { api } from "../../../services/api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
  rememberById,
  rememberRecord,
} from "../../../services/patchPayload";

const geofenceSnapshots = new Map();
let settingsSnapshot = null;

const compactParams = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  return query.toString();
};

const withQuery = (endpoint, params) => {
  const query = compactParams(params);
  return query ? `${endpoint}?${query}` : endpoint;
};

const locationPayload = (position) => ({
  latitude: Number(position.coords.latitude).toFixed(6),
  longitude: Number(position.coords.longitude).toFixed(6),
  accuracy_m: Math.round(position.coords.accuracy || 0),
  provided_at: new Date(position.timestamp || Date.now()).toISOString(),
  device_context: {
    source: "browser_geolocation",
    user_agent: navigator.userAgent,
  },
});

const rememberGeofence = (response) =>
  rememberRecord(geofenceSnapshots, response);

export const getBrowserLocation = () =>
  new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("This browser does not support location permission."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve(locationPayload(position)),
      () => reject(new Error("Location permission was denied or unavailable.")),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  });

export const attendanceService = {
  admin: {
    getSettings: async (options) => {
      const response = await api.get("/tenant-admin/attendance/settings", options);
      settingsSnapshot = response;
      return response;
    },
    updateSettings: async (payload) => {
      const changes = buildChangedPatch(settingsSnapshot, payload);
      if (!hasPatchChanges(changes)) return settingsSnapshot;

      const response = await api.put(
        "/tenant-admin/attendance/settings",
        changes,
      );
      settingsSnapshot = mergePatchResult(settingsSnapshot, changes, response);
      return response;
    },
    listGeofences: async (params = {}, options) => {
      const response = await api.get(
        withQuery("/tenant-admin/attendance/geofences", params),
        options,
      );
      return rememberById(geofenceSnapshots, response);
    },
    createGeofence: async (payload) => {
      const response = await api.post(
        "/tenant-admin/attendance/geofences",
        payload,
      );
      return rememberGeofence(response);
    },
    updateGeofence: async (geofenceId, payload) => {
      const key = String(geofenceId);
      const current = geofenceSnapshots.get(key);
      const changes = buildChangedPatch(current, payload);
      if (!hasPatchChanges(changes)) return current;

      const response = await api.patch(
        `/tenant-admin/attendance/geofences/${geofenceId}`,
        changes,
      );
      geofenceSnapshots.set(key, mergePatchResult(current, changes, response));
      return response;
    },
    activateGeofence: async (geofenceId) =>
      rememberGeofence(
        await api.post(
          `/tenant-admin/attendance/geofences/${geofenceId}/activate`,
        ),
      ),
    deactivateGeofence: async (geofenceId) =>
      rememberGeofence(
        await api.post(
          `/tenant-admin/attendance/geofences/${geofenceId}/deactivate`,
        ),
      ),
    archiveGeofence: async (geofenceId) =>
      rememberGeofence(
        await api.post(
          `/tenant-admin/attendance/geofences/${geofenceId}/archive`,
        ),
      ),
    previewGeofence: (payload) =>
      api.post("/tenant-admin/attendance/geofences/preview", payload),
    listSheets: (params = {}, options) =>
      api.get(
        withQuery("/tenant-admin/attendance/student-sheets", params),
        options,
      ),
    openSheet: (payload) =>
      api.post("/tenant-admin/attendance/student-sheets", payload),
    markRecords: (sheetId, payload) =>
      api.patch(
        `/tenant-admin/attendance/student-sheets/${sheetId}/records`,
        payload,
      ),
    approveSheet: (sheetId) =>
      api.post(`/tenant-admin/attendance/student-sheets/${sheetId}/approve`),
    lockSheet: (sheetId) =>
      api.post(`/tenant-admin/attendance/student-sheets/${sheetId}/lock`),
    listWorkforce: (params = {}, options) =>
      api.get(withQuery("/tenant-admin/attendance/workforce", params), options),
    getAnalytics: (params = {}, options) =>
      api.get(withQuery("/tenant-admin/attendance/analytics", params), options),
    getReadiness: (params = {}, options) =>
      api.get(withQuery("/tenant-admin/attendance/readiness", params), options),
  },
  teacher: {
    listSheets: (params = {}) =>
      api.get(withQuery("/teacher/attendance/student-sheets", params)),
    openSheet: (payload) =>
      api.post("/teacher/attendance/student-sheets", payload),
    markRecords: (sheetId, payload) =>
      api.patch(
        `/teacher/attendance/student-sheets/${sheetId}/records`,
        payload,
      ),
    submitSheet: (sheetId, payload = {}) =>
      api.post(`/teacher/attendance/student-sheets/${sheetId}/submit`, payload),
    checkIn: (payload) =>
      api.post("/teacher/attendance/workforce/check-in", payload),
    checkOut: (payload) =>
      api.post("/teacher/attendance/workforce/check-out", payload),
    myWorkforce: (params = {}) =>
      api.get(withQuery("/teacher/attendance/workforce/me", params)),
  },
  student: {
    myRecords: (params = {}) =>
      api.get(withQuery("/student/attendance/me", params)),
  },
  parent: {
    studentRecords: (studentId, params = {}) =>
      api.get(withQuery(`/parent/attendance/students/${studentId}`, params)),
  },
};
