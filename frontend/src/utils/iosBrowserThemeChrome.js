const IOS_USER_AGENT_PATTERN = /iPad|iPhone|iPod/i;

export const isIosLikePlatform = (navigatorLike = {}) => {
  const userAgent = String(navigatorLike.userAgent || "");
  const platform = String(
    navigatorLike.userAgentData?.platform || navigatorLike.platform || "",
  );
  const iPadDesktopMode =
    platform === "MacIntel" && Number(navigatorLike.maxTouchPoints || 0) > 1;

  return IOS_USER_AGENT_PATTERN.test(userAgent) || iPadDesktopMode;
};

export const isStandalonePresentation = ({
  navigatorLike = {},
  displayModeStandalone = false,
} = {}) =>
  Boolean(displayModeStandalone || navigatorLike.standalone === true);

export const isIosBrowserMode = ({
  navigatorLike = {},
  displayModeStandalone = false,
} = {}) =>
  isIosLikePlatform(navigatorLike) &&
  !isStandalonePresentation({ navigatorLike, displayModeStandalone });

export const selectThemeBackgroundChannels = ({
  rootChannels = "",
  dashboardChannels = "",
  iosBrowser = false,
} = {}) => {
  const normalizedRoot = String(rootChannels || "").trim();
  const normalizedDashboard = String(dashboardChannels || "").trim();

  return iosBrowser && normalizedDashboard
    ? normalizedDashboard
    : normalizedRoot;
};