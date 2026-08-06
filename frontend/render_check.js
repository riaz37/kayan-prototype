/* Render every console page in Node and fail on an undefined component.
 *
 * A page that references a component which does not exist compiles fine,
 * passes every Python test, and then throws at render time — React unmounts
 * the whole tree and the user gets a blank white screen with no clue why.
 * That shipped once (a `<PageHeader>` that was really `<PageHead>`), so the
 * build now catches it.
 *
 * Only ReferenceErrors fail the build. Pages that need props they are not
 * given here throw for uninteresting reasons and are reported, not fatal.
 */
const fs = require("fs");
const path = require("path");
const React = require("react");
const { renderToString } = require("react-dom/server");

const dist = path.join(__dirname, "dist");

// Just enough browser for the bundles to evaluate.
const store = {};
global.window = {
  localStorage: { getItem: (k) => (k in store ? store[k] : null),
                  setItem: (k, v) => { store[k] = v; } },
  location: { search: "", hostname: "localhost", pathname: "/" },
  AudioContext: function () {},
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
  addEventListener() {}, removeEventListener() {},
};
global.document = {
  documentElement: { setAttribute() {}, style: {} },
  addEventListener() {}, removeEventListener() {},
  querySelector: () => null,
  createElement: () => ({ style: {} }),
};
global.navigator = { language: "ar", mediaDevices: {} };
global.localStorage = global.window.localStorage;
global.React = React;
global.fetch = () => Promise.resolve({ ok: true, json: async () => ({}) });

eval(fs.readFileSync(path.join(dist, "ui.js"), "utf8"));
eval(fs.readFileSync(path.join(dist, "pages.js"), "utf8"));

const PAGES = global.window.PAGES || {};
const names = Object.keys(PAGES).filter((n) => typeof PAGES[n] === "function");
if (!names.length) {
  console.error("  render check: no pages exported — did the build run?");
  process.exit(1);
}

const fatal = [];
const skipped = [];
for (const name of names) {
  try {
    renderToString(React.createElement(PAGES[name], {}));
  } catch (e) {
    // "X is not defined" is the bug this check exists for.
    if (e instanceof ReferenceError) fatal.push(`${name}: ${e.message}`);
    else skipped.push(`${name}: ${e.message.split("\n")[0].slice(0, 70)}`);
  }
}

if (skipped.length) {
  console.log(`  render check: ${skipped.length} page(s) need props, not checked`);
}
if (fatal.length) {
  console.error("  render check FAILED — these would render a blank screen:");
  for (const line of fatal) console.error("    " + line);
  process.exit(1);
}
console.log(`  render check: ${names.length - skipped.length}/${names.length} pages render`);
