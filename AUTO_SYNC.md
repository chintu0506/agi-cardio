# Auto GitHub Sync (Laptop)

This repo now includes an optional auto-sync daemon that commits and pushes local changes to GitHub on an interval.

## Start

```bash
cd /Users/chintuboppana/Downloads/agi-cardio
AUTO_SYNC_INTERVAL=30 ./scripts/start-auto-sync.sh
```

## Start Automatically At Login (macOS, recommended)

```bash
cd /Users/chintuboppana/Downloads/agi-cardio
AUTO_SYNC_INTERVAL=30 ./scripts/install-auto-sync-launchd.sh
```

This installs a launch agent so auto-sync restarts after reboot/login.

## Check status

```bash
./scripts/auto-sync-status.sh
./scripts/auto-sync-launchd-status.sh
```

## Stop

```bash
./scripts/stop-auto-sync.sh
```

## Remove Auto-Start Agent (macOS)

```bash
./scripts/uninstall-auto-sync-launchd.sh
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
- For deployment auto-update, keep your deploy platform (Netlify) connected to this GitHub repo branch.
