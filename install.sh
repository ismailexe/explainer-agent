#!/usr/bin/env bash
# Link this repository's three files into ~/.claude so the running Claude Code
# picks them up. Symlinks rather than copies: editing the repo edits the live
# agent, with no second copy to drift.
#
# Existing regular files are moved aside to <name>.pre-explainer-agent first.
# Undo with: mv ~/.claude/<path>.pre-explainer-agent ~/.claude/<path>
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
targets=(
  "bin/explainer"
  "bin/explainer-research"
  "bin/explainer_layout.py"
  "bin/explainer-glossary.py"
  "bin/transcript-tail.py"
  "agents/explainer.md"
  "agents/explainer-researcher.md"
  "commands/explain.md"
)

for rel in "${targets[@]}"; do
  src="$repo/$rel"
  dst="$HOME/.claude/$rel"
  [ -f "$src" ] || { echo "missing in repo: $rel" >&2; exit 1; }
  mkdir -p "$(dirname "$dst")"

  if [ -L "$dst" ]; then
    current="$(readlink "$dst")"
    [ "$current" = "$src" ] && { echo "ok       $rel  (already linked)"; continue; }
    rm "$dst"
  elif [ -e "$dst" ]; then
    mv "$dst" "$dst.pre-explainer-agent"
    echo "backed up $rel -> $rel.pre-explainer-agent"
  fi

  ln -s "$src" "$dst"
  echo "linked   $rel"
done

chmod +x "$repo/bin/explainer" "$repo/bin/explainer-research" \
         "$repo/bin/explainer_layout.py" \
         "$repo/bin/explainer-glossary.py" "$repo/bin/transcript-tail.py"

echo
echo "Installed. Verify with: ~/.claude/bin/transcript-tail.py --sources"
case ":$PATH:" in
  *":$HOME/.claude/bin:"*) echo "Ask a question with: explainer \"<soru>\"" ;;
  *) echo
     echo "~/.claude/bin is not on your PATH, so \`explainer\` will not resolve as a"
     echo "command. Add this to your shell profile:"
     echo
     echo "  export PATH=\"\$HOME/.claude/bin:\$PATH\""
     echo
     echo "Until then, call it by path: ~/.claude/bin/explainer \"<soru>\"" ;;
esac
