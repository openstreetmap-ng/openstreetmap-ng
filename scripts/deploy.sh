#!/usr/bin/env bash
set -euxo pipefail

: Parse input
if [ $# -ge 1 ]; then
  SHA="$1"
elif [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
  read -r SHA <<<"${SSH_ORIGINAL_COMMAND}"
else
  echo "Usage: $0 <commit-sha>" >&2
  exit 2
fi

: Fetch changes
cd /media/data/osm-ng
git fetch origin

: Setup build environment
WORKTREE=$(mktemp -d .deploy.XXXXXXXXXX)
cleanup() {
  cd /media/data/osm-ng
  git worktree remove --force "$WORKTREE" || true
}
trap cleanup EXIT
git worktree add --detach "$WORKTREE" "$SHA"

: Build the new configuration
cd "$WORKTREE"
cp config/services-test.nix /etc/nixos/services-ng.nix
nixos-rebuild build

: Stop services
systemctl stop osm-ng-dev osm-ng-replication-download

: Synchronize changes
cd /media/data/osm-ng
FILES=$(git diff --name-only --diff-filter=d "HEAD..$SHA")
sudo -u osm-ng \
  git reset --hard "$SHA"
echo "$FILES" | sudo -u osm-ng \
  nix-shell -p gitMinimal --run \
  'nix-shell --arg shellHook false --run git-restore-mtimes'

: Activate the new configuration
"$WORKTREE/result/bin/switch-to-configuration" switch
