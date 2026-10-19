# 12. Answer-language order

- Status: accepted
- Date: 2026-10-19

## Context

The explainer answered in Turkish by default. A question asked in English got a
Turkish answer, partly because of that default and partly because the user's own
Claude Code `language` setting loads into every session.

## Decision

Answer in `EXPLAINER_LANG` when it is set; otherwise in the `language` from the user's
Claude Code settings; otherwise in the language of the question. Technical terms stay
in English in every case. Only the first step is resolved by the explainer; Claude
Code already applies its own setting.

## Consequences

The agent's instructions no longer name their user, which had pulled answers toward
one language.
