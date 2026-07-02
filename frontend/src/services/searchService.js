import { api } from "./api";

const workspaceSearchPaths = {
  admin: "/tenant-admin/search",
  teacher: "/teachers/me/search",
  superadmin: "/superadmin/search",
};

const buildSearchPath = (role) => workspaceSearchPaths[String(role || "").toLowerCase()] || null;

export const searchService = {
  searchWorkspace: (role, query, limit = 20) => {
    const path = buildSearchPath(role);
    if (!path) {
      return Promise.resolve({ items: [], total: 0 });
    }

    return api.get(`${path}?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`);
  },

  searchTenant: (query, limit = 20) =>
    api.get(`/tenant-admin/search?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`),
};

export default searchService;
