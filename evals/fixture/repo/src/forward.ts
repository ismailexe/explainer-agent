import type { Database } from "./db";
import { claim, settle } from "./ledger";
import { createTicket, type Ticket } from "./helpdesk";
import { withRetry } from "./retry";
import { teamFor } from "./routes/routes";

export async function forward(db: Database, webhookId: string, ticket: Ticket): Promise<void> {
  if (!(await claim(db, webhookId))) return; // already forwarded once
  await withRetry(() => createTicket(ticket, teamFor(ticket.category)));
  await settle(db, webhookId);
}
