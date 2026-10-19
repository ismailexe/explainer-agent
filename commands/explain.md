---
description: Hand the user the command that opens the explainer chat for this conversation
argument-hint: (nothing — or the question they want to take over there)
---

The explainer is a chat the user keeps open in another terminal, beside this one,
and returns to while you keep working. This command does not answer anything; it
tells them how to open that chat for **this** conversation.

Print the working directory this session is in, and give them exactly this to run
in a new terminal window:

```
cd <this session's working directory>
explainer
```

Say it in one or two lines, nothing more. If `explainer` is not on their `PATH`, the
full form is `~/.claude/bin/explainer`.

If arguments were given, they are the question the user wants to ask it. **Do not answer
it and do not research it** — say in the same breath that they should type it into
that window. Isolating that research from this conversation is the entire point.

Rules for you, the main agent:

- **Do not explain anything yourself.** No Read, Grep, Bash or WebSearch, and no
  subagent. If you answer it here, the explanation lands in this context
  permanently, which is exactly what the explainer exists to prevent.
- **Do not open the window for them.** Spawning a terminal from here succeeds
  silently while the window appears behind a full-screen workspace, or on another
  Space, and they are left staring at a shell that looks like it did nothing. A
  command they paste themselves is a window they can see.
- **Do not summarise the conversation for it.** It reads this session's transcript
  off disk by itself, and it is required to read the source rather than trust a
  summary.
- Then carry on with the work exactly where it stood. A question is not a change
  of direction and does not need acknowledging.

The explainer cannot talk back into this conversation. If it tells them something
you need to know, they will paste it here themselves.
