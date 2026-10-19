# Contributing

Issues are welcome. For anything bigger than a small fix, please open an issue before
a pull request, so we can agree on the approach first.

## Running the tests

```sh
python3 -m unittest discover -s tests
```

No packages are needed. The tests build their own git repositories and Claude Code
directory trees in temporary folders and never touch your `~/.claude`.

## Running the evals

```sh
./install.sh
evals/run.sh
```

The eval suite asks the real explainer questions about a synthetic session and grades
the answers; see [`evals/README.md`](evals/README.md). It needs Claude Code signed in
and Node for `npx`, and a full run spends your own Claude usage — about eight minutes
for three runs of every case. Changes to `agents/explainer.md` should come with a
before-and-after run.

## Working on it

`install.sh` symlinks the repository into `~/.claude/`, so your edits are live in every
explainer you start. Two rules keep the design intact:

- Claude Code's on-disk layout is known only to `bin/explainer_layout.py`.
- Worked examples in `agents/explainer.md` stay off the topics the eval asks about,
  so a passing case reflects behaviour, not recall.

## Out of scope

- Writing into the working session, or editing files.
- Background processes that watch sessions continuously.
- Harnesses other than Claude Code.

The reasons are recorded in [`docs/decisions/`](docs/decisions/README.md).
