# Mobile people directory design QA

- Source visual truth: `C:\Users\taiwo\.codex\generated_images\01a058be-98d9-7630-95c3-fdc819c74f79\exec-cb3a25f1-bffc-456a-917f-6fa993516aae.png` (selected mobile Parent Directory direction, 852 x 1844 px).
- Implementation screenshot: unavailable because this session does not expose the required in-app browser or browser screenshot surface.
- Intended viewport: 390 x 844 CSS px at device scale factor 1.
- Source density: taller concept board used as structural direction rather than a 1:1 viewport capture.
- Implementation density normalization: not performed because no implementation screenshot could be captured.
- State: populated admin student, teacher, and parent directories; rows initially collapsed; user-opened row expanded; student filter sheet closed and open states required.

**Findings**

- [P1] Browser-rendered comparison is unavailable.
  Location: `/admin/students`, `/admin/teachers`, and `/admin/parents` at the mobile breakpoint.
  Evidence: the selected visual source was opened and inspected, but no browser-rendered implementation capture can be produced in this session.
  Impact: final line wrapping, safe-area clearance, PWA dock separation, filter-sheet height, and dark-theme row contrast cannot be approved from source and build output alone.
  Fix: capture the three authenticated routes at 390 x 844 in the supported in-app browser, including the expanded-row and open-filter states, then compare them with the selected visual.

**Required fidelity surfaces**

- Fonts and typography: implementation retains Weave's existing font stack, weights, and text tokens; browser rendering is not verified.
- Spacing and layout rhythm: mobile KPIs use a flatter 2 x 2 grid, filters move to a bottom sheet, people records use one grouped surface with progressive disclosure, and pagination follows the final row in normal document flow. Rendered rhythm is not verified.
- Colors and visual tokens: implementation uses existing Weave surface, primary, border, success, warning, and error tokens. Expanded rows use a solid low-opacity theme tint and slim status rail with no gradient, glow, glass, or added shadow.
- Image quality and asset fidelity: the selected direction contains no required raster imagery. Existing Lucide icons and text initials are used as interface content; no placeholder artwork or custom SVG assets were introduced.
- Copy and content: current student, teacher, parent, invitation, and request contracts and labels are retained rather than copying mock data from the visual direction.

**Interaction verification**

- Source-level wiring retained for live search, filters, pagination, student selection, invitation revocation, request approval/rejection, and membership lifecycle actions.
- Mobile row disclosure is accordion-style, initially collapsed, and resets when the list or page changes.
- Student secondary filters open in a bottom sheet and do not change page height.
- Production build: passed.
- Focused ESLint: passed.
- Primary interactions in a browser: not tested.
- Browser console errors: not checked.

**Full-view comparison evidence**

- Blocked: no implementation screenshot is available for a normalized side-by-side comparison.

**Focused region comparison evidence**

- Blocked: KPI grid, filter sheet, grouped roster, expanded row, dark theme, pagination end state, and PWA safe-area behavior could not be captured.

**Comparison history**

- Initial pass: selected source opened successfully; implementation comparison blocked by the unavailable browser surface.

**Implementation checklist**

- Capture all three authenticated directories at 390 x 844 in light and dark themes.
- Open and close the student filter sheet; change a select and checkbox.
- Expand a second record and confirm the first collapses.
- Scroll to the final row and confirm pagination appears above, not behind, the PWA dock.
- Check console output and repeat visual comparison after any P0/P1/P2 fixes.

final result: blocked
