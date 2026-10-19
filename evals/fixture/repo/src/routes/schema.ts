import { z } from "zod";

// Strict objects: an unknown key such as a misspelled "catgory" fails the
// build instead of being dropped silently (D-04).
export const routeSchema = z.strictObject({
  category: z.string().min(1),
  team: z.string().min(1),
});

export const routesFileSchema = z.strictObject({
  routes: z.array(routeSchema),
  fallback: z.string().min(1),
});

export type RoutesFile = z.infer<typeof routesFileSchema>;
