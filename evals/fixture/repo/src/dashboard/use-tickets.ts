import { useQuery } from "@tanstack/react-query";
import type { Ticket } from "../helpdesk";

export function useTickets() {
  return useQuery<Ticket[]>({
    queryKey: ["tickets"],
    queryFn: async () => {
      const response = await fetch("/api/tickets");
      if (!response.ok) throw new Error(`tickets answered ${response.status}`);
      return response.json();
    },
    refetchInterval: 30_000,
  });
}
