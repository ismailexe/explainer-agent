# Decisions

| ID | Decision | Reason |
|---|---|---|
| D-01 | Settle what the relay does before choosing a stack | Requirements were still moving; a stack chosen first would have shaped them |
| D-02 | TypeScript on Node, one process | One team, one language; nothing here needs more |
| D-03 | Every webhook id is claimed in the `ledger` table before forwarding and settled after; a repeated id is skipped | The shop retries webhooks, so the same ticket can arrive twice |
| D-04 | Routing rules live in `routes.yaml` in the repository, checked at build time with a strict schema | Rule changes get review and history; a typo fails the build instead of misrouting tickets |
| D-05 | When a refresh fails, the dashboard keeps the list it already has and shows a banner | An empty screen during a short outage looked like "no tickets" |
| D-06 | Failed helpdesk calls are retried with exponential backoff, at most 5 attempts | The helpdesk rate-limits bursts; fixed-interval retries made it worse |
