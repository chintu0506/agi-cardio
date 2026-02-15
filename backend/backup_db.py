import argparse
import json
import sys

from storage import backup_database, DB_PATH


def main():
    parser = argparse.ArgumentParser(description="Create a timestamped SQLite backup for AGI CardioSense.")
    parser.add_argument("--label", default="manual", help="Backup label (e.g., manual/startup/pre-migration).")
    parser.add_argument("--max-backups", type=int, default=30, help="Maximum backup files to retain.")
    args = parser.parse_args()

    try:
        result = backup_database(label=args.label, max_backups=args.max_backups)
    except Exception as e:
        print(json.dumps({"status": "error", "db_path": DB_PATH, "error": str(e)}))
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "db_path": DB_PATH,
                "backup_path": result["backup_path"],
                "removed_count": len(result["removed"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
