# relay

Forwards support tickets from the shop's webhook to the helpdesk API, and shows the
open tickets on a small dashboard.

- `src/forward.ts`: one webhook delivery, from claim to settle
- `src/ledger.ts`: the record of which webhook ids were already forwarded
- `routes.yaml`: which team receives which ticket category, checked at build time
- `src/dashboard/`: the ticket list

Decisions and their reasons are in `docs/DECISIONS.md`.
