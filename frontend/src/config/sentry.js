const SENTRY_BROWSER_SDK_URL =
  "https://browser.sentry-cdn.com/10.68.0/bundle.min.js";
const SENTRY_SCRIPT_ATTRIBUTE = "data-weave-sentry-sdk";
const FILTERED = "[Filtered]";
const MAX_PENDING_ERRORS = 20;

const SENSITIVE_KEYS = new Set([
  "access_token",
  "authorization",
  "cookie",
  "cookies",
  "email",
  "ip_address",
  "otp",
  "parent_email",
  "password",
  "phone",
  "phone_number",
  "refresh_token",
  "secret",
  "set_cookie",
  "setup_code",
  "student_email",
  "token",
  "username",
]);

const SENSITIVE_SUFFIXES = [
  "_access_code",
  "_api_key",
  "_otp",
  "_password",
  "_secret",
  "_setup_code",
  "_token",
];

let initializationPromise = null;
let sentryConfigured = false;
let pendingErrors = [];
let earlyErrorCleanup = null;
const queuedErrorObjects = new WeakSet();

const normalizeKey = (key) =>
  String(key ?? "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");

const isSensitiveKey = (key) => {
  const normalized = normalizeKey(key);
  return (
    SENSITIVE_KEYS.has(normalized) ||
    SENSITIVE_SUFFIXES.some((suffix) => normalized.endsWith(suffix))
  );
};

const scrubString = (value) =>
  String(value)
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[Filtered email]")
    .replace(/Bearer\s+[^\s]+/gi, "Bearer [Filtered token]");

const scrubValue = (value) => {
  if (typeof value === "string") return scrubString(value);

  if (Array.isArray(value)) {
    return value.map(scrubValue);
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        isSensitiveKey(key) ? FILTERED : scrubValue(item),
      ]),
    );
  }

  return value;
};

const sanitizeRequestUrl = (value) => {
  if (!value) return value;

  try {
    const baseOrigin =
      typeof window !== "undefined"
        ? window.location.origin
        : "https://weave.invalid";
    const url = new URL(value, baseOrigin);
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return undefined;
  }
};

export const sanitizeSentryEvent = (event) => {
  try {
    const sanitized = scrubValue({ ...event });

    if (sanitized.request && typeof sanitized.request === "object") {
      delete sanitized.request.data;
      delete sanitized.request.cookies;
      delete sanitized.request.query_string;

      const safeUrl = sanitizeRequestUrl(sanitized.request.url);
      if (safeUrl) sanitized.request.url = safeUrl;
      else delete sanitized.request.url;
    }

    if (sanitized.user && typeof sanitized.user === "object") {
      delete sanitized.user.email;
      delete sanitized.user.ip_address;
      delete sanitized.user.username;
    }

    return sanitized;
  } catch (error) {
    console.warn("Sentry event sanitization failed; dropping event", {
      message: error?.message || "unknown error",
    });
    return null;
  }
};

export const parseSentrySampleRate = (value, fallback = 1) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) return fallback;
  return parsed;
};

const readBoolean = (value) => String(value ?? "").toLowerCase() === "true";

const getSentryConfig = () => {
  const env = import.meta.env || {};
  return {
    dsn: String(env.VITE_SENTRY_DSN || "").trim(),
    environment: String(env.VITE_SENTRY_ENVIRONMENT || env.MODE || "unknown").trim(),
    release: String(env.VITE_SENTRY_RELEASE || "").trim(),
    errorSampleRate: parseSentrySampleRate(env.VITE_SENTRY_ERROR_SAMPLE_RATE, 1),
    debug: readBoolean(env.VITE_SENTRY_DEBUG),
  };
};

const getDisplayMode = () => {
  if (typeof window === "undefined") return "unknown";

  const standalone = Boolean(
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
      window.navigator?.standalone === true,
  );
  return standalone ? "standalone" : "browser";
};

const getSdk = () => {
  if (typeof window === "undefined") return null;
  return window.Sentry || null;
};

const setScopeContext = (scope, context) => {
  if (!scope || !context) return;

  if (context.kind) scope.setTag?.("frontend_error_kind", String(context.kind));
  if (context.componentStack) {
    scope.setContext?.("react", {
      component_stack: scrubString(context.componentStack),
    });
  }
};

const sendException = (error, context = {}) => {
  const sdk = getSdk();
  if (!sdk?.captureException) return null;

  if (sdk.withScope) {
    let eventId = null;
    sdk.withScope((scope) => {
      setScopeContext(scope, context);
      eventId = sdk.captureException(error);
    });
    return eventId;
  }

  return sdk.captureException(error);
};

const enqueueException = (error, context = {}) => {
  if (error && typeof error === "object") {
    if (queuedErrorObjects.has(error)) return;
    queuedErrorObjects.add(error);
  }

  pendingErrors.push({ error, context });
  if (pendingErrors.length > MAX_PENDING_ERRORS) pendingErrors.shift();
};

export const captureFrontendException = (error, context = {}) => {
  if (!sentryConfigured) return null;

  const normalizedError =
    error instanceof Error ? error : new Error("Unexpected frontend error");

  if (getSdk()?.captureException) {
    return sendException(normalizedError, context);
  }

  enqueueException(normalizedError, context);
  return null;
};

const flushPendingErrors = () => {
  const queued = pendingErrors;
  pendingErrors = [];

  queued.forEach(({ error, context }) => {
    sendException(error, context);
  });
};

const installEarlyErrorBuffer = () => {
  if (typeof window === "undefined") return null;

  const onError = (event) => {
    if (event.error instanceof Error) {
      enqueueException(event.error, { kind: "window_error" });
    }
  };

  const onUnhandledRejection = (event) => {
    const error =
      event.reason instanceof Error
        ? event.reason
        : new Error("Unhandled promise rejection");
    enqueueException(error, { kind: "unhandled_rejection" });
  };

  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onUnhandledRejection);

  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onUnhandledRejection);
  };
};

const loadSentrySdk = () =>
  new Promise((resolve, reject) => {
    if (typeof document === "undefined") {
      reject(new Error("Sentry browser SDK requires a document"));
      return;
    }

    const existingSdk = getSdk();
    if (existingSdk?.init) {
      resolve(existingSdk);
      return;
    }

    const existingScript = document.querySelector(
      `script[${SENTRY_SCRIPT_ATTRIBUTE}="true"]`,
    );
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(getSdk()), {
        once: true,
      });
      existingScript.addEventListener(
        "error",
        () => reject(new Error("Sentry browser SDK failed to load")),
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.src = SENTRY_BROWSER_SDK_URL;
    script.async = true;
    script.crossOrigin = "anonymous";
    script.setAttribute(SENTRY_SCRIPT_ATTRIBUTE, "true");
    script.addEventListener(
      "load",
      () => {
        const sdk = getSdk();
        if (sdk?.init) resolve(sdk);
        else reject(new Error("Sentry SDK loaded without a global client"));
      },
      { once: true },
    );
    script.addEventListener(
      "error",
      () => reject(new Error("Sentry browser SDK failed to load")),
      { once: true },
    );

    document.head.appendChild(script);
  });

export const initializeSentry = () => {
  if (initializationPromise) return initializationPromise;

  const config = getSentryConfig();
  if (!config.dsn) {
    console.info("Sentry disabled: no frontend DSN configured");
    return Promise.resolve(false);
  }

  sentryConfigured = true;
  earlyErrorCleanup = installEarlyErrorBuffer();

  initializationPromise = loadSentrySdk()
    .then((sdk) => {
      sdk.init({
        dsn: config.dsn,
        environment: config.environment,
        release: config.release || undefined,
        sampleRate: config.errorSampleRate,
        enableLogs : true,
        sendDefaultPii: false,
        debug: config.debug,
        beforeSend: sanitizeSentryEvent,
      });

      sdk.setTag?.("service", "frontend");
      sdk.setTag?.("display_mode", getDisplayMode());

      earlyErrorCleanup?.();
      earlyErrorCleanup = null;
      flushPendingErrors();

      console.info("Sentry initialized for frontend error monitoring", {
        environment: config.environment,
        release: config.release || null,
      });
      return true;
    })
    .catch((error) => {
      earlyErrorCleanup?.();
      earlyErrorCleanup = null;
      pendingErrors = [];
      console.warn("Sentry initialization failed; continuing without Sentry", {
        message: error?.message || "unknown error",
      });
      return false;
    });

  return initializationPromise;
};
