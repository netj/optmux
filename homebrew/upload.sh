#!/usr/bin/env bash
# Upload homebrew/optmux.rb to the netj/homebrew-tap repo (no-op when unchanged)
# Usage: homebrew/upload.sh [COMMIT_MESSAGE]
set -euo pipefail
formula="$(dirname "$0")/optmux.rb"
api=repos/netj/homebrew-tap/contents/optmux.rb
message=${1:-"optmux $(sed -n 's/^  version "\(.*\)"$/\1/p' "$formula")"}

ruby -c "$formula" >/dev/null
sha=$(gh api "$api" --jq .sha)
if gh api "$api" --jq .content | base64 -d | cmp -s - "$formula"; then
    echo "netj/homebrew-tap: optmux.rb already up to date"
    exit
fi
gh api "$api" --method PUT -f message="$message" -f sha="$sha" \
    -f content="$(base64 <"$formula" | tr -d '\n')" --jq .commit.html_url
