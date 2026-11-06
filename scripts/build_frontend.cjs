// Development only: commit the generated assets; PythonAnywhere needs no Node.js.
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
process.chdir(root);
const output = path.join(root, "app/static/vendor");
fs.mkdirSync(output, { recursive: true });
const result = spawnSync(
  process.execPath,
  [
    require.resolve("tailwindcss/lib/cli.js"),
    "--input",
    "frontend/tailwind.css",
    "--output",
    "app/static/vendor/tailwind.min.css",
    "--content",
    "./app/templates/**/*.html",
    "--minify",
  ],
  { stdio: "inherit" },
);
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status || 1);
fs.copyFileSync(
  require.resolve("htmx.org/dist/htmx.min.js"),
  path.join(output, "htmx.min.js"),
);
for (const dependency of ["htmx.org", "tailwindcss"]) {
  const packageRoot = path.dirname(
    require.resolve(`${dependency}/package.json`),
  );
  fs.copyFileSync(
    path.join(packageRoot, "LICENSE"),
    path.join(output, `${dependency}-LICENSE.txt`),
  );
}
