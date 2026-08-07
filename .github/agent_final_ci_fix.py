from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()


def patch_contract_verifier() -> None:
    path = ROOT / "frontend/scripts/verifyFrontendBackendContracts.mjs"
    text = path.read_text(encoding="utf-8")

    helper_anchor = "function parseIncludeRouters(source) {\n"
    if helper_anchor not in text:
        raise RuntimeError("parseIncludeRouters anchor not found")

    nested_helper = '''function parseNestedRouterIncludes(source, routerName) {\n  const registrations = [];\n  let offset = 0;\n  const callName = `${routerName}.include_router`;\n\n  while (true) {\n    const callIndex = source.indexOf(callName, offset);\n    if (callIndex === -1) break;\n    const openParenIndex = source.indexOf("(", callIndex);\n    if (openParenIndex === -1) break;\n    const callBody = extractBalancedCall(source, openParenIndex);\n    if (callBody === null) break;\n\n    const routerMatch = callBody.match(/^\\s*(\\w+)/);\n    const prefixMatch = callBody.match(/\\bprefix\\s*=\\s*["']([^"']*)["']/);\n    if (routerMatch) {\n      registrations.push({\n        alias: routerMatch[1],\n        prefix: prefixMatch?.[1] || "",\n      });\n    }\n\n    offset = openParenIndex + callBody.length + 2;\n  }\n\n  return registrations;\n}\n\n'''
    text = text.replace(helper_anchor, nested_helper + helper_anchor, 1)

    old_block = '''    const routerPrefix = parseRouterPrefix(moduleSource, importedRouter.sourceName);\n    for (const route of parseRouterDecorators(moduleSource, importedRouter.sourceName)) {\n      const fullPath = normalizeSlashes(\n        `${registration.prefix}/${routerPrefix}/${route.path}`,\n      );\n      const key = contractKey(route.method, fullPath);\n      contracts.set(key, {\n        method: route.method,\n        path: normalizeContractPath(fullPath),\n        source: path.relative(repoRoot, modulePath),\n      });\n    }\n'''
    new_block = '''    const routerQueue = [{ alias: importedRouter.sourceName, inheritedPrefix: "" }];\n    const visitedRouters = new Set();\n\n    while (routerQueue.length > 0) {\n      const currentRouter = routerQueue.shift();\n      const visitKey = `${currentRouter.alias}|${currentRouter.inheritedPrefix}`;\n      if (visitedRouters.has(visitKey)) continue;\n      visitedRouters.add(visitKey);\n\n      const routerPrefix = parseRouterPrefix(moduleSource, currentRouter.alias);\n      const routePrefix = normalizeSlashes(\n        `${registration.prefix}/${currentRouter.inheritedPrefix}/${routerPrefix}`,\n      );\n\n      for (const route of parseRouterDecorators(moduleSource, currentRouter.alias)) {\n        const fullPath = normalizeSlashes(`${routePrefix}/${route.path}`);\n        const key = contractKey(route.method, fullPath);\n        contracts.set(key, {\n          method: route.method,\n          path: normalizeContractPath(fullPath),\n          source: path.relative(repoRoot, modulePath),\n        });\n      }\n\n      for (const nested of parseNestedRouterIncludes(moduleSource, currentRouter.alias)) {\n        routerQueue.push({\n          alias: nested.alias,\n          inheritedPrefix: normalizeSlashes(\n            `${currentRouter.inheritedPrefix}/${routerPrefix}/${nested.prefix}`,\n          ),\n        });\n      }\n    }\n'''
    if old_block not in text:
        raise RuntimeError("collectBackendContracts router block not found")
    text = text.replace(old_block, new_block, 1)
    path.write_text(text, encoding="utf-8")


def patch_student_service() -> None:
    path = ROOT / "frontend/src/services/studentService.js"
    text = path.read_text(encoding="utf-8")
    old = 'api.patch(`/tenant-admin/students/${studentId}/complete-profile`, payload),'
    new = 'api.patch(`/tenant-admin/students/${studentId}/profile`, payload),'
    if old not in text:
        raise RuntimeError("stale complete-profile endpoint not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


patch_contract_verifier()
patch_student_service()
