// Runs before every build: parses routes.yaml and refuses to build when it does
// not match the schema, so a broken rule never reaches production (D-04).
import { readFileSync } from "node:fs";
import { parse } from "yaml";
import { routesFileSchema } from "../src/routes/schema";

const result = routesFileSchema.safeParse(parse(readFileSync("routes.yaml", "utf8")));
if (!result.success) {
  console.error(result.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`).join("\n"));
  process.exit(1);
}
