import { api } from "../../services/api";

const basePath = "/subscriptions/simulations/subscriptions";

export const simulationService = {
  getSubscriptionState: (tenantId, requestOptions) =>
    api.get(`${basePath}/${tenantId}`, requestOptions),

  runSubscriptionSimulation: (tenantId, payload) =>
    api.post(`${basePath}/${tenantId}`, payload),

  reconcileSubscription: (tenantId) =>
    api.post(`${basePath}/${tenantId}/reconcile`, {}),

  resetSubscription: (tenantId) =>
    api.post(`${basePath}/${tenantId}/reset`, {}),
};
