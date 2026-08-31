# People directory design QA

- Source visual truth: conversation attachments supplied by the user: the people-directory reference (1536 x 1024 px) plus the CBT KPI-card and green action-button references (no local filesystem paths available).
- Implementation screenshot: unavailable because this session does not expose a browser or screenshot surface.
- Intended desktop viewport: 1536 x 1024 CSS px at device scale factor 1.
- Intended mobile viewport: 390 x 844 CSS px at device scale factor 1.
- State: populated admin student, teacher, and parent directories plus a populated teacher student roster.
- Density normalization: not performed; the implementation could not be captured.

**Findings**

- [P1] Browser-rendered comparison is unavailable.
  Location: `/admin/students`, `/admin/teachers`, `/admin/parents`, and `/teacher/students`.
  Evidence: the reference image is visible in the conversation, but no browser-rendered implementation screenshot can be produced in this session.
  Impact: typography, responsive wrapping, dropdown placement, and final spacing cannot be approved from source and build output alone.
  Fix: open the three authenticated routes in the supported browser, capture desktop and mobile views, and compare each capture with the supplied reference.

**Required fidelity surfaces**

- Fonts and typography: code uses Weave's existing Inter/system font stack and established text tokens; browser rendering not verified.
- Spacing and layout rhythm: compact shared KPI cards, desktop tables, compact mobile cards, and desktop non-sticky pagination are implemented; visual comparison is blocked.
- Colors and visual tokens: implementation reuses the CBT server KPI palette (violet, emerald, amber, and semantic fallbacks) plus Weave's green success action; rendered contrast and balance are not verified.
- Image quality and asset fidelity: no new raster imagery or custom image assets are required by these directory views; existing Lucide iconography is reused consistently with the application.
- Copy and content: labels describe student, class, employment, lifecycle, profile, and access states without copying the reference product's wording.

**Interaction verification**

- Source-level wiring retained for search, filters, pagination, selection, batch class placement, profile editing, access reset, history, teacher subject capabilities, and lifecycle actions.
- Production build: passed.
- Primary interactions in a browser: not tested.
- Browser console errors: not checked.

**Full-view comparison evidence**

- Blocked: no implementation screenshot is available.

**Focused region comparison evidence**

- Blocked: table rows, mobile cards, filter controls, and action menus could not be captured.

**Comparison history**

- Initial pass: blocked before visual comparison because no browser-rendered evidence could be created.

**Implementation checklist**

- Capture all four authenticated routes at desktop width.
- Capture student and teacher lists at mobile width.
- Exercise search, filters, row selection, pagination, and overflow action menus.
- Check browser console output.
- Fix any P0/P1/P2 visual differences and repeat the comparison.

final result: blocked
