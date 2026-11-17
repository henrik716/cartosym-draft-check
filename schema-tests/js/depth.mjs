// Time Ajv and Hyperjump on the nested expressions written by `python schema-tests/depth.py --write`.
// Usage: node schema-tests/js/depth.mjs [checkout] [--timeout S]
// Each validation runs in its own process with a time limit (a synchronous validator cannot be interrupted).
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = "https://cartosym.test/";
const SCHEMAS = { part1: "1-core/schemas/CartoSym-JSON.schema.json", part3: "3-geometry/schemas/CartoSym-JSON-3-geometry.schema.json" };
const docs = JSON.parse(fs.readFileSync(path.join(here, "..", "out", "depth-docs.json"), "utf8"));
const expected = { and: true, junk: false, mixed: true };

if (process.argv[2] === "--child") {
  const [, , , repo, validator, key, kind, d] = process.argv;
  const load = (rel) => ({ ...JSON.parse(fs.readFileSync(path.join(repo, rel), "utf8")), $id: BASE + rel });
  const doc = { stylingRules: [{ selector: docs[d][kind] }] };
  let ok, t;
  if (validator === "ajv") {
    const { default: Ajv2020 } = await import("ajv/dist/2020.js");
    const ajv = new Ajv2020({ strict: false, validateFormats: false, logger: false, allErrors: process.env.ALL_ERRORS === "1" });
    for (const rel of Object.values(SCHEMAS)) ajv.addSchema(load(rel));
    const v = ajv.getSchema(BASE + SCHEMAS[key]);
    t = performance.now(); ok = v(doc); t = performance.now() - t;
  } else {
    const { registerSchema, validate } = await import("@hyperjump/json-schema/draft-2020-12");
    for (const rel of Object.values(SCHEMAS)) registerSchema(load(rel));
    await validate(BASE + SCHEMAS[key], { stylingRules: [] }); // compile first
    t = performance.now(); ok = (await validate(BASE + SCHEMAS[key], doc)).valid; t = performance.now() - t;
  }
  console.log(JSON.stringify({ ok, t }));
  process.exit(0);
}

const args = process.argv.slice(2);
const repo = path.resolve(args.find((a) => !a.startsWith("--") && isNaN(a)) || path.join(here, "..", "..", "..", "cartographic-symbology"));
const ti = args.indexOf("--timeout");
const timeout = ti >= 0 ? Number(args[ti + 1]) : 30;
console.log(`Schemas from ${repo}; time limit ${timeout} s${process.env.ALL_ERRORS === "1" ? "; Ajv with allErrors" : ""}`);
let bad = 0;
for (const validator of ["ajv", "hyperjump"]) {
  for (const key of ["part1", "part3"]) {
    for (const kind of ["and", "junk", "mixed"]) {
      const cells = [];
      for (const d of [1, 2, 3, 4, 6, 8, 12, 16]) {
        if (!docs[d]) break;
        const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), "--child", repo, validator, key, kind, String(d)],
          { timeout: timeout * 1000, encoding: "utf8", cwd: here });
        if (r.error || r.status !== 0) { cells.push(`${d}: ${r.error ? `>${timeout}s` : "error"}`); bad++; break; }
        const { ok, t } = JSON.parse(r.stdout.trim().split("\n").pop());
        if (ok !== expected[kind]) bad++;
        cells.push(`${d}: ${t.toFixed(1)}ms${ok === expected[kind] ? "" : " WRONG"}`);
      }
      console.log(`${validator.padEnd(9)} ${key} ${kind.padEnd(5)} | ${cells.join(" | ")}`);
    }
  }
}
process.exit(bad ? 1 : 0);
