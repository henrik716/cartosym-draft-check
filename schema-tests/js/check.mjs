// Validate out/rows.json (written by run.py) against the Part 1 and Part 3 schemas with Ajv and Hyperjump,
// and compare with the expected outcomes and with python-jsonschema (out/python.json).
// Usage: node schema-tests/js/check.mjs [path to a cartographic-symbology checkout]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import { registerSchema, validate } from "@hyperjump/json-schema/draft-2020-12";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(process.argv[2] || path.join(here, "..", "..", "..", "cartographic-symbology"));
const out = path.join(here, "..", "out");
const BASE = "https://cartosym.test/"; // base URI for the relative $ref from Part 3 to Part 1; test only
const SCHEMAS = { part1: "1-core/schemas/CartoSym-JSON.schema.json", part3: "3-geometry/schemas/CartoSym-JSON-3-geometry.schema.json" };
const load = (rel) => ({ ...JSON.parse(fs.readFileSync(path.join(repo, rel), "utf8")), $id: BASE + rel });
const rows = JSON.parse(fs.readFileSync(path.join(out, "rows.json"), "utf8"));
const python = JSON.parse(fs.readFileSync(path.join(out, "python.json"), "utf8"));
const version = (p) => JSON.parse(fs.readFileSync(path.join(here, "node_modules", p, "package.json"), "utf8")).version;

const results = {};
const ajv = new Ajv2020({ strict: false, validateFormats: false, logger: false });
for (const rel of Object.values(SCHEMAS)) ajv.addSchema(load(rel));
results.ajv = Object.fromEntries(Object.entries(SCHEMAS).map(([k, rel]) => [k, rows.map((r) => ajv.getSchema(BASE + rel)(r.doc))]));

for (const rel of Object.values(SCHEMAS)) registerSchema(load(rel));
results.hyperjump = {};
for (const [k, rel] of Object.entries(SCHEMAS)) {
  results.hyperjump[k] = [];
  for (const r of rows) results.hyperjump[k].push((await validate(BASE + rel, r.doc)).valid);
}
fs.writeFileSync(path.join(out, "js.json"), JSON.stringify(results));

let bad = 0;
const n1 = rows.filter((r) => !r.part3_op).length;
for (const [name, res] of Object.entries(results)) {
  const v = name === "ajv" ? `Ajv ${version("ajv")}` : `Hyperjump ${version("@hyperjump/json-schema")}`;
  const p3 = rows.filter((r, i) => res.part3[i] !== r.valid);
  const p1 = rows.filter((r, i) => res.part1[i] !== r.valid && !r.part3_op);
  const differ = ["part1", "part3"].map((k) => rows.filter((r, i) => res[k][i] !== python[k][i]).length);
  console.log(`${v}: Part 3: ${p3.length} wrong of ${rows.length} | Part 1: ${p1.length} wrong of ${n1} documents without Part 3 operations | differs from python-jsonschema on ${differ[0]} (Part 1) and ${differ[1]} (Part 3) documents`);
  for (const r of p3.slice(0, 20)) console.log(`   Part 3 wrong: [${r.set}] ${r.name}`);
  for (const r of p1.slice(0, 20)) console.log(`   Part 1 wrong: [${r.set}] ${r.name}`);
  bad += p3.length + p1.length + differ[0] + differ[1];
}
process.exit(bad ? 1 : 0);
