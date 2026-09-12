import { readFile, writeFile, mkdir, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const schemaDir = fileURLToPath(new URL("../../contracts/schemas/", import.meta.url));
const outputDir = fileURLToPath(new URL("../src/generated/", import.meta.url));
const check = process.argv.includes("--check");
const definitions = {};
for (const file of (await readdir(schemaDir)).filter((name) => name.endsWith(".schema.json")).sort()) {
  const schema = JSON.parse(await readFile(`${schemaDir}/${file}`, "utf8"));
  for (const [name, definition] of Object.entries(schema.$defs ?? {})) {
    if (definitions[name] && JSON.stringify(definitions[name]) !== JSON.stringify(definition)) throw new Error(`Conflicting schema: ${name}`);
    definitions[name] = definition;
  }
  const { $defs: unusedDefinitions, $schema: unusedDialect, ...definition } = schema;
  void unusedDefinitions; void unusedDialect;
  const name = file.replace(".schema.json", "");
  if (definitions[name] && JSON.stringify(definitions[name]) !== JSON.stringify(definition)) throw new Error(`Conflicting root schema: ${name}`);
  definitions[name] = definition;
}
const source = { title: "Contracts", anyOf: Object.keys(definitions).sort().map((name) => ({ $ref: `#/$defs/${name}` })), $defs: definitions };
const result = await compile(source, "Contracts", { bannerComment: "/* Generated from this project's Pydantic contracts. Run npm run contracts. */", additionalProperties: false, unreachableDefinitions: true });
const path = `${outputDir}/contracts.ts`;
if (check) {
  if ((await readFile(path, "utf8")) !== result) throw new Error("TypeScript contracts have drifted");
} else {
  await mkdir(outputDir, { recursive: true });
  await writeFile(path, result);
}
console.log(`${check ? "Checked" : "Generated"} TypeScript contracts`);
