#!/usr/bin/env bash
# Run the answer-quality suite. Extra arguments go to `promptfoo eval`, e.g.
#   evals/run.sh --filter-pattern "false premise"
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_UPDATE=1
exec npx --yes promptfoo@0.124.1 eval --no-cache -j 2 "$@"
