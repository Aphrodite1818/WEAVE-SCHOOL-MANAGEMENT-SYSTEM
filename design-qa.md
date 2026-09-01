# Academic Hub desktop-first redesign visual QA

- Source visual truth: two user-provided Academic Hub and Classes reference screenshots in the conversation.
- Source pixels: 1680 x 945 and 1680 x 945.
- Implementation screenshot: unavailable.
- Intended desktop viewport: 1680 x 945 CSS pixels at density 1.
- Intended mobile viewport: existing responsive Weave breakpoints from 320 CSS pixels upward.
- State: authenticated tenant-admin Academic Hub with representative sessions, levels, classes, curriculum, lifecycle states, and metrics.
- Full-view comparison evidence: blocked because this session does not expose the user's in-app browser or an authenticated browser-rendered implementation capture.
- Focused region comparison evidence: blocked for the same reason.

## Findings

- [P1] Browser-rendered desktop comparison is unavailable.
  - Location: `/admin/academic` and `/admin/academic/:workflow`.
  - Evidence: both reference screenshots are visible in the conversation, but there is no authenticated implementation screenshot from the same viewport and state.
  - Impact: lint, tests, and a successful production build do not prove final table density, tab overflow, wrapping, sticky shell behavior, or modal placement in a real browser.
  - Fix: open the tenant-admin Academic Hub at 1680 x 945, capture the directory, classes, curriculum subjects, department lifecycle, calendar, progression, and session-closing views, then compare the captures with the references in one visual input.

## Required fidelity surfaces

- Fonts and typography: existing Weave typography tokens, weights, and responsive sizes are preserved; visual comparison is blocked.
- Spacing and layout rhythm: the card grid has been replaced by a desktop table directory, workspace side navigation was removed, and record lists now use desktop tables with mobile rows; visual comparison is blocked.
- Colors and visual tokens: only existing Weave surface, border, semantic status, and primary tokens are used; no new gradients or decorative effects were introduced.
- Image quality and asset fidelity: the references contain interface icons but no required raster content. The existing Lucide icon system is preserved.
- Copy and content: entity scope, state, and lifecycle labels are grounded in current backend metrics and supported transition services. Unsupported readiness percentages and invented record counts were not added.

## Primary interactions to test

- Search the Academic Hub entity directory and open each workflow.
- Switch entities with the shared academic entity selector.
- Filter levels, arm labels, classes, and departments by lifecycle tab.
- Run typed confirmation flows for level, arm-label, and department lifecycle transitions.
- Switch Curriculum between Curriculum Subjects and Term Offerings.
- Exercise session closing, progression, calendar, results, and report-card purpose-built pages.
- Check browser console errors for every route above.

## Comparison history

- Pass 1: no browser-rendered evidence was available, so no valid side-by-side comparison or visual fix iteration could be performed.

## Implementation checklist

- Capture the authenticated directory and record-list views at 1680 x 945.
- Capture responsive rows and tab wrapping at 390 x 844 and 320 pixels wide.
- Verify lifecycle confirmation dialogs and empty/loading/error states.
- Fix all visible P0, P1, and P2 mismatches before changing the final result.

final result: blocked
