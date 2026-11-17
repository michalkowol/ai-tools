#!/bin/bash
# PreToolUse hook for Bash: denies or asks before risky commands.
# Plugins cannot ship permission rules, so this mirrors the deny/ask lists
# of ai/config/claude/managed-settings.json, except that read-only `gh api`
# calls (GET, GraphQL queries) are allowed and only writes need confirmation.
#
# Requires only bash, grep and sed (no jq), so it runs on a bare macOS too.
# Every segment of a compound command (&&, ||, ;, |, newline) is checked.

DENY=(
  "gh repo delete"
  "gh repo archive"
  "gh repo unarchive"
  "gh repo rename"
  "gh repo edit"
  "gh repo deploy-key"
  "gh release delete"
  "gh release delete-asset"
  "gh issue delete"
  "gh issue transfer"
  "gh label delete"
  "gh secret"
  "gh variable"
  "gh ssh-key"
  "gh gpg-key"
  "gh alias"
  "gh extension"
  "gh codespace"
  "gh auth login"
  "gh auth logout"
  "gh auth refresh"
  "gh auth switch"
  "gh auth setup-git"
)

ASK=(
  "git push"
  "gh pr merge"
  "gh pr comment"
  "gh pr review"
  "gh pr create"
  "gh pr edit"
  "gh pr close"
  "gh pr reopen"
  "gh pr ready"
  "gh issue comment"
  "gh issue create"
  "gh issue edit"
  "gh issue close"
  "gh issue reopen"
  "gh release create"
  "gh release edit"
  "gh release upload"
  "gh repo create"
  "gh repo fork"
  "gh run cancel"
  "gh run rerun"
  "gh workflow run"
  "gh label create"
  "gh label edit"
)

INPUT=$(cat)

# Inside a JSON string every quote is escaped, so the first "command" key is
# the tool_input one and its value ends at the first unescaped quote.
COMMAND=$(printf '%s' "$INPUT" \
  | grep -oE '"command"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"' \
  | head -n 1 \
  | sed -E 's/^"command"[[:space:]]*:[[:space:]]*"//; s/"$//; s/\\n/\n/g; s/\\t/ /g; s/\\"/"/g; s/\\\\/\\/g')

[ -z "$COMMAND" ] && exit 0

decide() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"%s","permissionDecisionReason":"%s"}}\n' "$1" "$2"
  exit 0
}

matches() {
  local segment=$1
  shift
  local prefix
  for prefix in "$@"; do
    if [[ "$segment" == "$prefix" || "$segment" == "$prefix "* ]]; then
      MATCHED=$prefix
      return 0
    fi
  done
  return 1
}

# gh api sends GET unless -X/--method says otherwise or a body flag
# (-f/-F/--field/--raw-field/--input) switches it to POST. GraphQL always
# uses POST, so there only a mutation (or a body we cannot see) is a write.
gh_api_is_write() {
  local segment=$1
  local method
  if [[ "$segment" =~ (^|\ )graphql(\ |$) ]]; then
    printf '%s' "$COMMAND" | grep -qi 'mutation' && return 0
    [[ "$segment" =~ (^|\ )--input(\ |=) || "$segment" =~ =@ ]] && return 0
    return 1
  fi
  method=$(printf '%s' "$segment" \
    | grep -oE '(^| )(-X ?|--method[ =])[A-Za-z]+' \
    | head -n 1 \
    | sed -E 's/.*(-X ?|--method[ =])//' \
    | tr '[:lower:]' '[:upper:]')
  if [ -n "$method" ]; then
    [ "$method" != "GET" ]
    return
  fi
  [[ "$segment" =~ (^|\ )(-[fF]|--field|--raw-field|--input) ]]
}

SEGMENTS=$(printf '%s\n' "$COMMAND" | sed -E 's/(&&|\|\||[;|&(){}]|\$\(|`)/\n/g')

ASKED=""
while IFS= read -r segment; do
  segment=$(printf '%s' "$segment" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g')
  if matches "$segment" "${DENY[@]}"; then
    decide deny "'$MATCHED' is blocked by the mk plugin guard hook. Ask the user to run it themselves."
  fi
  if [ -z "$ASKED" ] && matches "$segment" "gh api" && gh_api_is_write "$segment"; then
    ASKED="gh api (write)"
  fi
  if [ -z "$ASKED" ] && matches "$segment" "${ASK[@]}"; then
    ASKED=$MATCHED
  fi
done <<< "$SEGMENTS"

if [ -n "$ASKED" ]; then
  decide ask "'$ASKED' needs confirmation (mk plugin guard hook)"
fi

exit 0
