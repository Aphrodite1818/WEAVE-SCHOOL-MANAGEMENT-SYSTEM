import assert from "node:assert/strict";
import test from "node:test";

import {
  TENANT_BRANDING_TOKEN_KEYS,
  applyBranding,
  clearAppliedBranding,
  validateBrandingResponse,
  validateBrandingTokens,
} from "./tenantBranding.js";

const tokens = Object.fromEntries(TENANT_BRANDING_TOKEN_KEYS.map((key) => [key, "1 2 3"]));

function fakeElement() {
  const values = new Map();
  return {
    dataset: {},
    style: {
      setProperty: (key, value) => values.set(key, value),
      removeProperty: (key) => values.delete(key),
      getPropertyValue: (key) => values.get(key) || "",
    },
  };
}

test("strict allow-list rejects unknown, missing, and invalid token values", () => {
  assert.deepEqual(validateBrandingTokens(tokens), tokens);
  assert.equal(validateBrandingTokens({ ...tokens, "--evil": "1 2 3" }), null);
  assert.equal(validateBrandingTokens({ ...tokens, "--color-primary": "url(evil)" }), null);
  const missing = { ...tokens };
  delete missing["--color-primary"];
  assert.equal(validateBrandingTokens(missing), null);
});

test("tenant response validation prevents cross-tenant cache use", () => {
  const response = { tenant_id: "school-a", token_schema_version: 2, light_tokens: tokens, dark_tokens: tokens };
  assert.ok(validateBrandingResponse(response, "school-a"));
  assert.equal(validateBrandingResponse(response, "school-b"), null);
  assert.equal(validateBrandingResponse({ ...response, token_schema_version: 1 }, "school-a"), null);
});

test("appearance switches token sets without retaining previous variables", () => {
  const element = fakeElement();
  const dark = { ...tokens, "--color-primary": "9 8 7" };
  const response = {
    tenant_id: "school-a", theme_version: 2, token_schema_version: 2, is_enabled: true,
    is_default_theme: false, light_tokens: tokens, dark_tokens: dark,
  };
  applyBranding(element, response, "light");
  assert.equal(element.style.getPropertyValue("--color-primary"), "1 2 3");
  assert.equal(element.style.getPropertyValue("--color-background"), "");
  applyBranding(element, response, "dark");
  assert.equal(element.style.getPropertyValue("--color-primary"), "9 8 7");
  clearAppliedBranding(element);
  assert.equal(element.style.getPropertyValue("--color-primary"), "");
});
