const PROTECTED_AUTH_PATHS = new Set([
  "/api/v1/auth/refresh",
  "/api/v1/auth/logout",
]);

const INSTALL_FLAG = "__weaveCookieCsrfFetchGuardInstalled";

const resolveRequestUrl = (input) => {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();
  return input?.url || "";
};

const resolveRequestMethod = (input, init) =>
  String(init?.method || input?.method || "GET").toUpperCase();

const resolveRequestPathname = (requestUrl) => {
  try {
    return new URL(requestUrl, window.location.origin).pathname;
  } catch {
    return null;
  }
};

export function installCookieCsrfFetchGuard() {
  if (typeof window === "undefined" || window[INSTALL_FLAG]) return;

  const nativeFetch = window.fetch.bind(window);

  window.fetch = (input, init = {}) => {
    const requestUrl = resolveRequestUrl(input);
    const method = resolveRequestMethod(input, init);
    const pathname = resolveRequestPathname(requestUrl);

    if (
      pathname === null ||
      method !== "POST" ||
      !PROTECTED_AUTH_PATHS.has(pathname)
    ) {
      return nativeFetch(input, init);
    }

    const headers = new Headers(input?.headers || undefined);
    new Headers(init.headers || undefined).forEach((value, key) => {
      headers.set(key, value);
    });
    headers.set("X-Weave-CSRF", "1");

    return nativeFetch(input, {
      ...init,
      headers,
    });
  };

  window[INSTALL_FLAG] = true;
}
