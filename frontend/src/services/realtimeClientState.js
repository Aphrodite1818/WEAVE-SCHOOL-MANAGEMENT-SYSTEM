export const resetAuthenticationLifecycle = (client) => {
  client.authenticatedOnce = false;
  client.reconnectAttempt = 0;
  client.lastAuthenticatedToken = null;
};

export const markConnectionReady = (client) => {
  const status = client.authenticatedOnce ? "reconnected" : "ready";
  client.authenticatedOnce = true;
  return status;
};
