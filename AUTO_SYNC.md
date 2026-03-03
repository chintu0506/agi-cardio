# Auto GitHub Sync (Laptop)

This repo now includes an optional auto-sync daemon that commits and pushes local changes to GitHub on an interval.

## Start

```bash
cd /Users/chintuboppana/Downloads/agi-cardio
AUTO_SYNC_INTERVAL=30 ./scripts/start-auto-sync.sh
```

## Check status

```bash
./scripts/auto-sync-status.sh
```

## Stop

```bash
./scripts/stop-auto-sync.sh
```

## Pause without stopping

```bash
touch .autosync.pause   # pause
rm -f .autosync.pause   # resume
```

## Notes

- Commits are automatic and use message prefix: `chore(auto-sync): laptop update`.
- Only tracked/untracked files that are not ignored by `.gitignore` are committed.
- Auto-sync skips while merge/rebase is in progress.
