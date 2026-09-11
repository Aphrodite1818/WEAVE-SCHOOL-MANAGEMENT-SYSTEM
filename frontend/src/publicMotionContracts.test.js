import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import postcss from "postcss";

const css = postcss.parse(readFileSync(new URL("./index.css", import.meta.url), "utf8"));

test("public entrance animations finish with visible content", () => {
  for (const name of ["landing-headline-reveal", "public-panel-enter"]) {
    const animation = css.nodes.find((node) => node.type === "atrule" && node.name === "keyframes" && node.params === name);
    assert.ok(animation, `${name} must exist`);
    const end = animation.nodes.find((node) => node.selector === "to");
    assert.ok(end.nodes.some((node) => node.prop === "opacity" && node.value === "1"));
    assert.ok(end.nodes.some((node) => node.prop === "transform" && node.value === "translateY(0)"));
  }
});

test("Weave reduced-motion preference explicitly keeps public content visible", () => {
  for (const selector of [".landing-headline-word", ".public-panel-reveal"]) {
    const rule = css.nodes.find((node) => node.type === "rule" && node.selector.includes(`html[data-reduced-motion="true"] ${selector}`));
    assert.ok(rule, `${selector} needs an application preference override`);
    assert.ok(rule.nodes.some((node) => node.prop === "animation" && node.value === "none" && node.important));
    assert.ok(rule.nodes.some((node) => node.prop === "opacity" && node.value === "1"));
  }
});
