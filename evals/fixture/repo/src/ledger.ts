import type { Database } from "./db";

// One row per webhook id. A row is claimed before the ticket is forwarded and
// settled once the helpdesk has accepted it, so a webhook the shop sends twice
// is forwarded once (D-03).
export type LedgerState = "claimed" | "settled";

export async function claim(db: Database, webhookId: string): Promise<boolean> {
  const inserted = await db.run(
    "INSERT INTO ledger (webhook_id, state) VALUES (?, 'claimed') ON CONFLICT DO NOTHING",
    [webhookId],
  );
  return inserted.changes === 1;
}

export async function settle(db: Database, webhookId: string): Promise<void> {
  await db.run("UPDATE ledger SET state = 'settled' WHERE webhook_id = ?", [webhookId]);
}
