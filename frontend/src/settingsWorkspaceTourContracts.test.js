import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (relativePath) =>
  readFileSync(new URL(relativePath, import.meta.url), "utf8");

test("profile page no longer owns institution transition or tour replay actions", () => {
  const source = read("./pages/shared/ProfileSettingsPage.jsx");
  assert.doesNotMatch(source, /InstitutionTypeSetting/);
  assert.doesNotMatch(source, /ReplayWorkspaceTourSetting/);
  assert.match(source, /institutionTypeReadOnly/);
});

test("completed admin profile exposes institution type as read-only context", () => {
  const source = read("./components/shared/ProfileCompletionForm.jsx");
  assert.match(source, /institutionTypeReadOnly/);
  assert.match(source, /statusData\?\.onboarding_required === false/);
  assert.match(source, /Use Settings → Institution type/);
  assert.match(source, /readOnly: true/);
});

test("settings page owns both institution-type navigation and workspace-tour replay", () => {
  const source = read("./pages/shared/RoleSettingsPage.jsx");
  assert.match(source, /\/admin\/settings\/institution-type/);
  assert.match(source, /requestWorkspaceTour\(normalizedRole\)/);
  assert.match(source, /Workspace tour/);
  assert.match(source, /title="Guidance"/);
});

test("institution type has a dedicated admin settings route", () => {
  const routes = read("./routes/adminRoutes.jsx");
  const page = read("./pages/admin/InstitutionTypeSettingsPage.jsx");
  assert.match(routes, /path="\/admin\/settings\/institution-type"/);
  assert.match(routes, /InstitutionTypeSettingsPage/);
  assert.match(page, /InstitutionTypeSetting role="admin"/);
  assert.match(page, /Back to settings/);
});

test("tour css preserves primary button backgrounds in light mode", () => {
  const source = read("./components/guides/workspaceTour.css");
  assert.doesNotMatch(
    source,
    /\.workspace-tour button\s*\{[^}]*background-image:\s*none/,
  );
  assert.match(
    source,
    /\.workspace-tour-close,\s*\.workspace-tour-secondary-action,\s*\.workspace-tour-dismiss-action\s*\{\s*background-image:\s*none;\s*\}/,
  );
});
