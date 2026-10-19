import { useTickets } from "./use-tickets";
import strings from "../i18n/en.json";

export function TicketList() {
  const { data, isError, refetch } = useTickets();

  if (!data) return <p>{isError ? strings.loadFailed : strings.loading}</p>;

  // A failed refresh keeps the list already on screen and says so (D-05).
  return (
    <section>
      {isError && (
        <div role="status">
          {strings.refreshFailed} <button onClick={() => refetch()}>{strings.retry}</button>
        </div>
      )}
      <ul>
        {data.map((ticket) => (
          <li key={ticket.id}>{ticket.subject}</li>
        ))}
      </ul>
    </section>
  );
}
