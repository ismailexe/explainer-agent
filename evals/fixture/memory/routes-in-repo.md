---
name: routes-in-repo
description: Why routing rules left the database for routes.yaml
metadata:
  type: project
---

Routing rules were first planned as a database table. On 2026-10-17 the user asked
to keep them out of the database: a change to who receives which ticket should go
through review and keep its history. They now live in `routes.yaml`, checked at build
time by `scripts/check-routes.ts` (D-04).

**Why:** a misrouted ticket is silent; a failed build is loud.
