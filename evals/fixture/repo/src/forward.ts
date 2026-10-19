import type { Database } from "./db";
import { claim, settle } from "./ledger";
import { createTicket, type Ticket } from "./helpdesk";
import { withRetry } from "./retry";
import { teamFor } from "./routes/routes";

export async function forward(db: Database, webhookId: string, ticket: Ticket): Promise<void> {
  if (!(await claim(db, webhookId))) return; // already forwarded once
  try {
    await withRetry(() => createTicket(ticket, teamFor(ticket.category)));
  } catch (error) {
    console.error("helpdesk refused ticket", ticket, error);
    throw error;
  }
  await settle(db, webhookId);
}
