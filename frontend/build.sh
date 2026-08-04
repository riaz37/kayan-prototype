#!/usr/bin/env bash
# Build the Kayan console: compile JSX -> JS (IIFE-wrapped), generate Tailwind CSS.
set -e
cd "$(dirname "$0")"
[ -d node_modules ] || npm install --no-audit --no-fund
mkdir -p dist/vendor

# Vendor React locally. index.html used to pull both UMD bundles from unpkg at
# runtime, so a CDN hiccup (or an offline demo) rendered a blank console.
echo "vendoring react..."
cp node_modules/react/umd/react.production.min.js dist/vendor/react.js
cp node_modules/react-dom/umd/react-dom.production.min.js dist/vendor/react-dom.js

echo "compiling JSX..."
npx babel js --out-dir dist --extensions .jsx --out-file-extension .js --quiet
echo "wrapping bundles..."
node -e '
const fs=require("fs");
for (const f of ["ui.js","pages.js","app.js"]) {
  const p="dist/"+f;
  let s=fs.readFileSync(p,"utf8");
  if (!s.startsWith("(function()")) fs.writeFileSync(p,"(function(){\n"+s+"\n})();\n");
}
console.log("  wrapped 3 bundles");
'
echo "building CSS..."
npx tailwindcss -i src.css -o dist/app.css --minify 2>/dev/null
echo "done -> dist/"
