export type Ticket = { id: string; category: string; subject: string; body: string };

const HELPDESK_URL = process.env.HELPDESK_URL ?? "https://helpdesk.example.com/api/tickets";

export async function createTicket(ticket: Ticket, team: string): Promise<void> {
  const response = await fetch(HELPDESK_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...ticket, team }),
  });
  if (!response.ok) {
    throw new Error(`helpdesk answered ${response.status}`);
  }
}
