import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HTTP_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);
const FRONTEND_EXTENSIONS = new Set([".js", ".jsx", ".mjs", ".ts", ".tsx"]);
const PYTHON_EXTENSION = ".py";
const API_PREFIX = "/api/v1";

const normalizeSlashes = (value) => value.replace(/\/{2,}/g, "/");

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

export function normalizeContractPath(rawPath) {
  if (!rawPath || typeof rawPath !== "string") return null;

  let value = rawPath.trim();
  value = value.replace(/^https?:\/\/[^/]+/i, "");
  value = value.replace(/^\$\{API_BASE_URL\}/, "");
  value = value.split("?")[0].split("#")[0];
  value = replaceTemplateExpressions(value);
  value = value.replace(/\{[^}/]+\}/g, "{}");
  value = normalizeSlashes(value);

  if (value.startsWith(API_PREFIX)) value = value.slice(API_PREFIX.length);
  if (!value.startsWith("/")) value = `/${value}`;
  if (value.length > 1) value = value.replace(/\/$/, "");

  return value;
}

const contractKey = (method, routePath) =>
  `${method.toUpperCase()} ${normalizeContractPath(routePath)}`;

async function walk(directory, predicate) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (["node_modules", "dist", "coverage", ".git"].includes(entry.name)) continue;
      files.push(...(await walk(absolutePath, predicate)));
    } else if (predicate(absolutePath)) {
      files.push(absolutePath);
    }
  }

  return files;
}

function extractBalancedCall(source, openParenIndex) {
  let depth = 0;
  let quote = null;
  let escaped = false;

  for (let index = openParenIndex; index < source.length; index += 1) {
    const char = source[index];

    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === quote) {
        quote = null;
      }
      continue;
    }

    if (["\"", "'", "`"].includes(char)) {
      quote = char;
      continue;
    }

    if (char === "(") depth += 1;
    if (char === ")") {
      depth -= 1;
      if (depth === 0) return source.slice(openParenIndex + 1, index);
    }
  }

  return null;
}

function parsePythonImports(source) {
  const aliases = new Map();
  const importPattern = /from\s+([\w.]+)\s+import\s+(\([\s\S]*?\)|[^\n]+)/g;

  for (const match of source.matchAll(importPattern)) {
    const moduleName = match[1];
    const imported = match[2]
      .replace(/[()]/g, " ")
      .replace(/#[^\n]*/g, " ")
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);

    for (const part of imported) {
      const aliasMatch = part.match(/^(\w+)(?:\s+as\s+(\w+))?$/);
      if (!aliasMatch) continue;
      const [, sourceName, alias = sourceName] = aliasMatch;
      aliases.set(alias, { moduleName, sourceName });
    }
  }

  return aliases;
}

function parseNestedRouterIncludes(source, routerName) {
  const registrations = [];
  let offset = 0;
  const callName = `${routerName}.include_router`;

  while (true) {
    const callIndex = source.indexOf(callName, offset);
    if (callIndex === -1) break;
    const openParenIndex = source.indexOf("(", callIndex);
    if (openParenIndex === -1) break;
    const callBody = extractBalancedCall(source, openParenIndex);
    if (callBody === null) break;

    const routerMatch = callBody.match(/^\s*(\w+)/);
    const prefixMatch = callBody.match(/\bprefix\s*=\s*["']([^"']*)["']/);
    if (routerMatch) {
      registrations.push({ alias: routerMatch[1], prefix: prefixMatch?.[1] || "" });
    }

    offset = openParenIndex + callBody.length + 2;
  }

  return registrations;
}

function parseIncludeRouters(source) {
  const registrations = [];
  let offset = 0;

  while (true) {
    const callIndex = source.indexOf("app.include_router", offset);
    if (callIndex === -1) break;
    const openParenIndex = source.indexOf("(", callIndex);
    if (openParenIndex === -1) break;
    const callBody = extractBalancedCall(source, openParenIndex);
    if (callBody === null) break;

    const routerMatch = callBody.match(/^\s*(\w+)/);
    const prefixMatch = callBody.match(/\bprefix\s*=\s*["']([^"']*)["']/);
    if (routerMatch) {
      registrations.push({
        alias: routerMatch[1],
        prefix: prefixMatch?.[1] || "",
      });
    }

    offset = openParenIndex + callBody.length + 2;
  }

  return registrations;
}

function parseRouterPrefix(source, routerName) {
  const assignmentPattern = new RegExp(
    `\\b${routerName}\\s*=\\s*APIRouter\\s*\\(`,
    "g",
  );
  const match = assignmentPattern.exec(source);
  if (!match) return "";

  const openParenIndex = source.indexOf("(", match.index);
  const callBody = extractBalancedCall(source, openParenIndex) || "";
  return callBody.match(/\bprefix\s*=\s*["']([^"']*)["']/)?.[1] || "";
}

function parseRouterDecorators(source, routerName) {
  const routes = [];
  const escapedRouterName = routerName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const routePattern = new RegExp(
    `@${escapedRouterName}\\.(get|post|put|patch|delete)\\s*\\(\\s*(["'])([^"']*)\\2`,
    "g",
  );

  for (const match of source.matchAll(routePattern)) {
    routes.push({ method: match[1].toUpperCase(), path: match[3] });
  }

  const apiRoutePattern = new RegExp(
    `@${escapedRouterName}\\.api_route\\s*\\(\\s*(["'])([^"']*)\\1([\\s\\S]*?)\\)`,
    "g",
  );

  for (const match of source.matchAll(apiRoutePattern)) {
    const methodsMatch = match[3].match(/methods\s*=\s*\[([^\]]+)\]/);
    if (!methodsMatch) continue;
    const methods = [...methodsMatch[1].matchAll(/["']([A-Z]+)["']/g)].map(
      (item) => item[1],
    );
    for (const method of methods.filter((item) => HTTP_METHODS.has(item))) {
      routes.push({ method, path: match[2] });
    }
  }

  return routes;
}

export async function collectBackendContracts(repoRoot) {
  const mainPath = path.join(repoRoot, "backend", "app", "main.py");
  const mainSource = await readFile(mainPath, "utf8");
  const imports = parsePythonImports(mainSource);
  const registrations = parseIncludeRouters(mainSource);
  const contracts = new Map();

  for (const registration of registrations) {
    const importedRouter = imports.get(registration.alias);
    if (!importedRouter) continue;

    const modulePath = path.join(
      repoRoot,
      "backend",
      `${importedRouter.moduleName.replace(/\./g, path.sep)}${PYTHON_EXTENSION}`,
    );

    let moduleSource;
    try {
      moduleSource = await readFile(modulePath, "utf8");
    } catch {
      continue;
    }

    const routerQueue = [{ alias: importedRouter.sourceName, inheritedPrefix: "" }];
    const visitedRouters = new Set();

    while (routerQueue.length > 0) {
      const currentRouter = routerQueue.shift();
      const visitKey = `${currentRouter.alias}|${currentRouter.inheritedPrefix}`;
      if (visitedRouters.has(visitKey)) continue;
      visitedRouters.add(visitKey);

      const routerPrefix = parseRouterPrefix(moduleSource, currentRouter.alias);
      const routePrefix = normalizeSlashes(
        `${registration.prefix}/${currentRouter.inheritedPrefix}/${routerPrefix}`,
      );

      for (const route of parseRouterDecorators(moduleSource, currentRouter.alias)) {
        const fullPath = normalizeSlashes(`${routePrefix}/${route.path}`);
        const key = contractKey(route.method, fullPath);
        contracts.set(key, {
          method: route.method,
          path: normalizeContractPath(fullPath),
          source: path.relative(repoRoot, modulePath),
        });
      }

      for (const nested of parseNestedRouterIncludes(moduleSource, currentRouter.alias)) {
        routerQueue.push({
          alias: nested.alias,
          inheritedPrefix: normalizeSlashes(
            `${currentRouter.inheritedPrefix}/${routerPrefix}/${nested.prefix}`,
          ),
        });
      }
    }
  }

  return contracts;
}

function extractLiteralApiCalls(source, sourceFile) {
  const calls = [];
  const apiPattern =
    /\bapi\.(get|post|postForm|put|patch|delete)\s*\(\s*(["'`])([\s\S]*?)\2/g;

  for (const match of source.matchAll(apiPattern)) {
    const method = match[1] === "postForm" ? "POST" : match[1].toUpperCase();
    const routePath = normalizeContractPath(match[3]);
    if (!routePath || routePath === "/" || routePath.startsWith("/{}")) continue;
    calls.push({ method, path: routePath, source: sourceFile });
  }

  const fetchPattern = /\bfetch\s*\(\s*`\$\{API_BASE_URL\}([^`]+)`/g;
  for (const match of source.matchAll(fetchPattern)) {
    const nearby = source.slice(match.index, match.index + 600);
    const method =
      nearby.match(/\bmethod\s*:\s*["'](GET|POST|PUT|PATCH|DELETE)["']/)?.[1] ||
      "GET";
    const routePath = normalizeContractPath(match[1]);
    if (!routePath || routePath === "/" || routePath.startsWith("/{}")) continue;
    calls.push({ method, path: routePath, source: sourceFile });
  }

  return calls;
}

export async function collectFrontendContracts(repoRoot) {
  const sourceRoot = path.join(repoRoot, "frontend", "src");
  const files = await walk(sourceRoot, (filePath) =>
    FRONTEND_EXTENSIONS.has(path.extname(filePath)),
  );
  const contracts = new Map();

  for (const filePath of files) {
    const source = await readFile(filePath, "utf8");
    const relativePath = path.relative(repoRoot, filePath);
    for (const call of extractLiteralApiCalls(source, relativePath)) {
      const key = contractKey(call.method, call.path);
      const existing = contracts.get(key) || { ...call, sources: [] };
      existing.sources.push(relativePath);
      contracts.set(key, existing);
    }
  }

  return contracts;
}

export async function verifyFrontendBackendContracts(repoRoot) {
  const [frontendContracts, backendContracts] = await Promise.all([
    collectFrontendContracts(repoRoot),
    collectBackendContracts(repoRoot),
  ]);

  const missing = [...frontendContracts.entries()]
    .filter(([key]) => !backendContracts.has(key))
    .map(([key, contract]) => ({ key, ...contract }))
    .sort((left, right) => left.key.localeCompare(right.key));

  return {
    frontendContracts,
    backendContracts,
    missing,
  };
}

async function main() {
  const currentFile = fileURLToPath(import.meta.url);
  const repoRoot = path.resolve(path.dirname(currentFile), "..", "..", "..");
  const result = await verifyFrontendBackendContracts(repoRoot);

  console.log(
    `Validated ${result.frontendContracts.size} frontend API contracts against ${result.backendContracts.size} FastAPI routes.`,
  );

  if (result.missing.length === 0) return;

  console.error("\nFrontend API calls without a matching backend route:");
  for (const missing of result.missing) {
    console.error(`- ${missing.key}`);
    for (const source of [...new Set(missing.sources)]) {
      console.error(`  ${source}`);
    }
  }
  process.exitCode = 1;
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  await main();
}
