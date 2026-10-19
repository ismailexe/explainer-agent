import routesFile from "../../routes.yaml";
import type { RoutesFile } from "./schema";

const file = routesFile as RoutesFile;

export function teamFor(category: string): string {
  return file.routes.find((route) => route.category === category)?.team ?? file.fallback;
}
