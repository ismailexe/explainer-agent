import type { Database } from "../src/db";

// Just enough of the ledger table for its tests.
export function memoryDatabase(): Database & { state(id: string): string | undefined } {
  const rows = new Map<string, string>();
  return {
    async run(sql, [id]) {
      const key = String(id);
      if (sql.startsWith("INSERT")) {
        if (rows.has(key)) return { changes: 0 };
        rows.set(key, "claimed");
        return { changes: 1 };
      }
      rows.set(key, "settled");
      return { changes: 1 };
    },
    state: (id) => rows.get(id),
  };
}
