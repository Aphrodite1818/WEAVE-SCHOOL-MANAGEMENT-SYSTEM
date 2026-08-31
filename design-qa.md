# Analytics redesign visual QA

- Source visual truth: user-provided analytics reference image in the conversation.
- Source pixels: 1488 x 1027.
- Implementation screenshot: unavailable.
- Intended desktop viewport: 1488 x 1027 CSS pixels at density 1.
- Intended mobile viewport: responsive phone widths from 320 CSS pixels upward.
- State: authenticated actor analytics and dashboard routes with role-specific backend data.
- Full-view comparison evidence: blocked because this session does not expose a browser or a browser-rendered implementation capture.
- Focused region comparison evidence: blocked for the same reason.

## Findings

- [P1] Browser-rendered desktop and mobile comparison is unavailable.
  - Location: admin, teacher, student, parent, and superadmin dashboard/analytics routes.
  - Evidence: the reference image is visible in the conversation, but no authenticated implementation screenshot can be captured in this session.
  - Impact: build, lint, and contract tests do not prove chart-label wrapping, card density, or role-data composition in a real browser.
  - Fix: open each role with representative backend data, capture the analytics route at 1488 x 1027 and at 390 x 844, and compare those captures with the reference in one visual input.

## Required fidelity surfaces

- Fonts and typography: code inspection confirms existing Weave typography tokens and responsive sizes are preserved; visual comparison is blocked.
- Spacing and layout rhythm: responsive one-column phone KPIs, two-column tablet KPIs, and four-column desktop KPIs are implemented; visual comparison is blocked.
- Colors and visual tokens: existing theme tokens are used and the shared trend chart now uses the light analytics treatment; visual comparison is blocked.
- Image quality and asset fidelity: the analytics design contains no new raster imagery; existing product branding and Lucide icon system are preserved.
- Copy and content: labels map only to existing metrics response fields. Unsupported reference filters and actions were intentionally omitted.

## Comparison history

- Pass 1: no browser-rendered evidence was available, so no valid visual comparison or fix iteration could be performed.

## Implementation checklist

- Capture admin analytics with representative performance, report-card, class, subject, and grade data.
- Capture teacher, student, parent, and superadmin analytics with representative role data.
- Verify desktop layout at 1488 x 1027.
- Verify mobile layout at 390 x 844 and a narrow 320-pixel width.
- Test chart expansion and horizontal chart scrolling.
- Check browser console errors on every role route.

final result: blocked
