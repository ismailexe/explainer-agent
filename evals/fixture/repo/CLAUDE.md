# relay

- Record every decision in `docs/DECISIONS.md` with its reason before building it.
- Never forward a ticket twice. Every delivery goes through `src/ledger.ts`.
- Routing rules live in `routes.yaml`, not in the database.
