import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("password reset sends the password and reset token in the correct positions", async () => {
  const page = await read("src/pages/public/ForgotPasswordPage.jsx");
  const service = await read("src/services/auth.service.js");

  assert.match(
    page,
    /authService\.resetPassword\(resetEmail,\s*password,\s*resetToken\)/,
  );
  assert.doesNotMatch(
    page,
    /authService\.resetPassword\(resetEmail,\s*resetToken,\s*password\)/,
  );
  assert.match(
    service,
    /resetPassword:\s*\(email,\s*newPassword,\s*resetToken\)/,
  );
  assert.match(service, /new_password:\s*newPassword/);
  assert.match(service, /reset_token:\s*resetToken/);
});
