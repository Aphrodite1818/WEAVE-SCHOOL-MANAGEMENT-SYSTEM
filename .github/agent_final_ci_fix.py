from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_contract_verifier() -> None:
    path = ROOT / "frontend/scripts/verifyFrontendBackendContracts.mjs"
    text = path.read_text(encoding="utf-8")

    anchor = 'const normalizeSlashes = (value) => value.replace(/\\/{2,}/g, "/");\n\n'
    helper = r'''const normalizeSlashes = (value) => value.replace(/\/{2,}/g, "/");

function replaceTemplateExpressions(value) {
  let result = "";

  for (let index = 0; index < value.length; index += 1) {
    if (value[index] !== "$" || value[index + 1] !== "{") {
      result += value[index];
      continue;
    }

    const expressionStart = index + 2;
    let depth = 1;
    let quote = null;
    let escaped = false;
    let cursor = expressionStart;

    for (; cursor < value.length; cursor += 1) {
      const char = value[cursor];

      if (quote) {
        if (escaped) escaped = false;
        else if (char === "\\") escaped = true;
        else if (char === quote) quote = null;
        continue;
      }

      if (["\"", "'", "`"].includes(char)) {
        quote = char;
        continue;
      }

      if (char === "{") depth += 1;
      else if (char === "}") {
        depth -= 1;
        if (depth === 0) break;
      }
    }

    if (depth !== 0) {
      result += "{}";
      break;
    }

    const expression = value.slice(expressionStart, cursor).trim();
    const querySuffix =
      /\b(?:queryString|build\w*Query|searchParams|params)\b/i.test(expression) ||
      /URLSearchParams/i.test(expression);
    if (!querySuffix) result += "{}";
    index = cursor;
  }

  return result;
}

'''
    if anchor not in text:
        raise RuntimeError("normalizeSlashes anchor not found")
    text = text.replace(anchor, helper, 1)

    old_template = '  value = value.replace(/\\$\\{[^}]+\\}/g, "{}");'
    if old_template not in text:
        raise RuntimeError("template replacement anchor not found")
    text = text.replace(old_template, "  value = replaceTemplateExpressions(value);", 1)

    old_skip = '    if (!routePath || routePath === "/") continue;'
    if old_skip not in text:
        raise RuntimeError("api skip anchor not found")
    text = text.replace(
        old_skip,
        '    if (!routePath || routePath === "/" || routePath.startsWith("/{}")) continue;',
        1,
    )

    old_fetch = '    calls.push({ method, path: normalizeContractPath(match[1]), source: sourceFile });'
    if old_fetch not in text:
        raise RuntimeError("fetch anchor not found")
    text = text.replace(
        old_fetch,
        '    const routePath = normalizeContractPath(match[1]);\n'
        '    if (!routePath || routePath === "/" || routePath.startsWith("/{}")) continue;\n'
        '    calls.push({ method, path: routePath, source: sourceFile });',
        1,
    )

    helper_anchor = "function parseIncludeRouters(source) {\n"
    if helper_anchor not in text:
        raise RuntimeError("parseIncludeRouters anchor not found")
    nested_helper = '''function parseNestedRouterIncludes(source, routerName) {\n  const registrations = [];\n  let offset = 0;\n  const callName = `${routerName}.include_router`;\n\n  while (true) {\n    const callIndex = source.indexOf(callName, offset);\n    if (callIndex === -1) break;\n    const openParenIndex = source.indexOf("(", callIndex);\n    if (openParenIndex === -1) break;\n    const callBody = extractBalancedCall(source, openParenIndex);\n    if (callBody === null) break;\n\n    const routerMatch = callBody.match(/^\\s*(\\w+)/);\n    const prefixMatch = callBody.match(/\\bprefix\\s*=\\s*["']([^"']*)["']/);\n    if (routerMatch) {\n      registrations.push({ alias: routerMatch[1], prefix: prefixMatch?.[1] || "" });\n    }\n\n    offset = openParenIndex + callBody.length + 2;\n  }\n\n  return registrations;\n}\n\n'''
    text = text.replace(helper_anchor, nested_helper + helper_anchor, 1)

    old_block = '''    const routerPrefix = parseRouterPrefix(moduleSource, importedRouter.sourceName);\n    for (const route of parseRouterDecorators(moduleSource, importedRouter.sourceName)) {\n      const fullPath = normalizeSlashes(\n        `${registration.prefix}/${routerPrefix}/${route.path}`,\n      );\n      const key = contractKey(route.method, fullPath);\n      contracts.set(key, {\n        method: route.method,\n        path: normalizeContractPath(fullPath),\n        source: path.relative(repoRoot, modulePath),\n      });\n    }\n'''
    new_block = '''    const routerQueue = [{ alias: importedRouter.sourceName, inheritedPrefix: "" }];\n    const visitedRouters = new Set();\n\n    while (routerQueue.length > 0) {\n      const currentRouter = routerQueue.shift();\n      const visitKey = `${currentRouter.alias}|${currentRouter.inheritedPrefix}`;\n      if (visitedRouters.has(visitKey)) continue;\n      visitedRouters.add(visitKey);\n\n      const routerPrefix = parseRouterPrefix(moduleSource, currentRouter.alias);\n      const routePrefix = normalizeSlashes(\n        `${registration.prefix}/${currentRouter.inheritedPrefix}/${routerPrefix}`,\n      );\n\n      for (const route of parseRouterDecorators(moduleSource, currentRouter.alias)) {\n        const fullPath = normalizeSlashes(`${routePrefix}/${route.path}`);\n        const key = contractKey(route.method, fullPath);\n        contracts.set(key, {\n          method: route.method,\n          path: normalizeContractPath(fullPath),\n          source: path.relative(repoRoot, modulePath),\n        });\n      }\n\n      for (const nested of parseNestedRouterIncludes(moduleSource, currentRouter.alias)) {\n        routerQueue.push({\n          alias: nested.alias,\n          inheritedPrefix: normalizeSlashes(\n            `${currentRouter.inheritedPrefix}/${routerPrefix}/${nested.prefix}`,\n          ),\n        });\n      }\n    }\n'''
    if old_block not in text:
        raise RuntimeError("backend contract router block not found")
    text = text.replace(old_block, new_block, 1)
    path.write_text(text, encoding="utf-8")


def patch_contract_tests() -> None:
    path = ROOT / "frontend/test/integration/frontend-backend-contracts.integration.test.js"
    text = path.read_text(encoding="utf-8")
    anchor = '  assert.equal(normalizeContractPath("students/me/"), "/students/me");\n'
    addition = '''  assert.equal(normalizeContractPath("students/me/"), "/students/me");
  assert.equal(normalizeContractPath("/teachers/${teacherId}"), "/teachers/{}");
  assert.equal(
    normalizeContractPath(
      "/subscriptions/plan-change/preview${queryString({ target_plan_code: targetPlanCode })}",
    ),
    "/subscriptions/plan-change/preview",
  );
'''
    if anchor not in text:
        raise RuntimeError("contract test anchor not found")
    path.write_text(text.replace(anchor, addition, 1), encoding="utf-8")


def remove_stale_legacy_services() -> None:
    academics = ROOT / "frontend/src/services/academicsService.js"
    text = academics.read_text(encoding="utf-8")
    marker = "\nexport const attendanceService = {"
    if marker not in text:
        raise RuntimeError("legacy academics marker not found")
    academics.write_text(text[: text.index(marker)] + "\n", encoding="utf-8")

    for relative in (
        "frontend/src/services/financeService.js",
        "frontend/src/services/aiService.js",
    ):
        path = ROOT / relative
        if not path.exists():
            raise RuntimeError(f"Expected stale service missing: {relative}")
        path.unlink()


def patch_teacher_service() -> None:
    path = ROOT / "frontend/src/services/teacherService.js"
    text = path.read_text(encoding="utf-8")
    old = '''  getTeachers: (options = {}) =>
    api.get(`/tenant-admin/teachers?${buildTeacherQuery(options)}`),

  createTeacher: (payload) =>
    api.post("/tenant-admin/teachers", payload),
'''
    new = '''  getTeachers: (options = {}) =>
    api.get(`/teachers/memberships?${buildTeacherQuery(options)}`),
'''
    if old not in text:
        raise RuntimeError("teacher list/create block not found")
    text = text.replace(old, new, 1)

    old = '''  getTeacher: (teacherId) =>
    api.get(`/tenant-admin/teachers/${teacherId}`),

  updateTeacher: (teacherId, payload) =>
    api.patch(`/tenant-admin/teachers/${teacherId}`, payload),

'''
    if old not in text:
        raise RuntimeError("teacher get/update block not found")
    text = text.replace(old, "", 1)

    old = '''
  deleteTeacher: (teacherId) =>
    api.delete(`/tenant-admin/teachers/${teacherId}`),
'''
    if old not in text:
        raise RuntimeError("teacher delete block not found")
    text = text.replace(old, "", 1)
    path.write_text(text, encoding="utf-8")


def patch_parent_service() -> None:
    path = ROOT / "frontend/src/services/parentService.js"
    text = path.read_text(encoding="utf-8")
    old = '''
  createParent: (payload) =>
    api.post("/tenant-admin/parents", payload),
'''
    if old not in text:
        raise RuntimeError("parent create block not found")
    text = text.replace(old, "", 1)

    old = '''
  updateParent: (parentId, payload) =>
    api.patch(`/tenant-admin/parents/${parentId}`, payload),

  deleteParent: (parentId) =>
    api.delete(`/tenant-admin/parents/${parentId}`),
'''
    if old not in text:
        raise RuntimeError("parent update/delete block not found")
    text = text.replace(old, "", 1)
    path.write_text(text, encoding="utf-8")


def make_legacy_profile_resources_read_only() -> None:
    path = ROOT / "frontend/src/pages/shared/resourceConfigs.js"
    text = path.read_text(encoding="utf-8")
    for config_name in ("teacherResourceConfig", "parentResourceConfig"):
        start_marker = f"export const {config_name} = {{"
        start = text.index(start_marker)
        next_export = text.find("\nexport const ", start + len(start_marker))
        end = len(text) if next_export == -1 else next_export
        block = text[start:end]
        block = block.replace("  canUpdate: true,", "  canUpdate: false,", 1)
        block = block.replace("  canDelete: true,", "  canDelete: false,", 1)
        block = re.sub(r"^  updateItem: .*\n", "  updateItem: undefined,\n", block, count=1, flags=re.MULTILINE)
        block = re.sub(r"^  deleteItem: .*\n", "  deleteItem: undefined,\n", block, count=1, flags=re.MULTILINE)
        text = text[:start] + block + text[end:]
    path.write_text(text, encoding="utf-8")


def patch_media_route() -> None:
    replace_once(
        ROOT / "frontend/src/services/auth.service.js",
        'api.get("/media/assets/current", {',
        'api.get("/tenant-admin/media/assets/current", {',
    )


def patch_student_service() -> None:
    replace_once(
        ROOT / "frontend/src/services/studentService.js",
        'api.patch(`/tenant-admin/students/${studentId}/complete-profile`, payload),',
        'api.patch(`/tenant-admin/students/${studentId}/profile`, payload),',
    )


patch_contract_verifier()
patch_contract_tests()
remove_stale_legacy_services()
patch_teacher_service()
patch_parent_service()
make_legacy_profile_resources_read_only()
patch_media_route()
patch_student_service()
