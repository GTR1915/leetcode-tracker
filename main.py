import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


DATA_DIR = Path("data")
LOG_FILE = Path("app.log")
LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

PROFILE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile {
      ranking
      reputation
    }
    submitStats {
      acSubmissionNum {
        difficulty
        count
      }
    }
  }
}
"""


def setup_logging() -> None:
    """Configure file and console logging for scheduled runs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def get_monthly_json_path(run_date: datetime | None = None) -> Path:
    """Return the JSON file path for the run month."""
    current_date = run_date or datetime.now()
    return DATA_DIR / f"profile_history_{current_date:%Y_%m}.json"


def create_json_store(file_path: Path) -> None:
    """Create the data directory and monthly JSON file if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not file_path.exists():
        file_path.write_text("[]\n", encoding="utf-8")
        logging.info("Created JSON history file: %s", file_path)
    else:
        logging.info("Using existing JSON history file: %s", file_path)


def load_entries(file_path: Path) -> list[dict[str, Any]]:
    """Load saved entries from a monthly JSON file."""
    create_json_store(file_path)

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logging.exception("Could not read JSON history because it is invalid: %s", file_path)
        raise

    if not isinstance(data, list):
        raise ValueError(f"JSON history must contain a list of entries: {file_path}")

    logging.info("Loaded %s entries from %s", len(data), file_path)
    return data


def write_entries(file_path: Path, entries: list[dict[str, Any]]) -> None:
    """Write entries back to the monthly JSON file."""
    file_path.write_text(json.dumps(entries, indent=4) + "\n", encoding="utf-8")
    logging.info("Wrote %s entries to %s", len(entries), file_path)


def fetch_profile_details(username: str) -> dict[str, Any]:
    """Fetch ranking, solved counts, and reputation for a LeetCode profile."""
    logging.info("Fetching profile details for username: %s", username)
    response = requests.post(
        LEETCODE_GRAPHQL_URL,
        json={
            "query": PROFILE_QUERY,
            "variables": {"username": username},
        },
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])

    matched_user = payload.get("data", {}).get("matchedUser")
    if not matched_user:
        logging.error("LeetCode user not found: %s", username)
        raise ValueError(f"LeetCode user not found: {username}")

    profile = matched_user.get("profile") or {}
    solved_counts = {
        item["difficulty"].lower(): item["count"]
        for item in matched_user.get("submitStats", {}).get("acSubmissionNum", [])
    }

    profile_details = {
        "username": matched_user["username"],
        "ranking": profile.get("ranking"),
        "reputation": profile.get("reputation"),
        "total": solved_counts.get("all", 0),
        "easy": solved_counts.get("easy", 0),
        "medium": solved_counts.get("medium", 0),
        "hard": solved_counts.get("hard", 0),
    }

    logging.info("Fetched profile details: %s", profile_details)
    return profile_details


def build_entry(profile_details: dict[str, Any], entry_id: int) -> dict[str, Any]:
    """Build one history entry with the same fields as the database table."""
    return {
        "id": entry_id,
        "date": datetime.now().isoformat(timespec="seconds"),
        "username": profile_details["username"],
        "ranking": profile_details["ranking"],
        "reputation": profile_details["reputation"],
        "easy": profile_details["easy"],
        "medium": profile_details["medium"],
        "hard": profile_details["hard"],
        "total": profile_details["total"],
    }


def is_same_profile(entry: dict[str, Any], profile_details: dict[str, Any]) -> bool:
    """Compare profile values while ignoring entry metadata such as id and date."""
    comparable_fields = ("username", "ranking", "reputation", "easy", "medium", "hard", "total")
    return all(entry.get(field) == profile_details.get(field) for field in comparable_fields)


def get_latest_saved_entry() -> dict[str, Any] | None:
    """Return the latest entry from all monthly JSON files."""
    if not DATA_DIR.exists():
        logging.info("No data directory found while checking latest saved entry.")
        return None

    latest_entry = None
    for file_path in sorted(DATA_DIR.glob("profile_history_*.json")):
        entries = load_entries(file_path)
        if entries:
            latest_entry = entries[-1]

    if latest_entry:
        logging.info("Latest saved entry found: %s", latest_entry)
    else:
        logging.info("No saved entries found in JSON history files.")

    return latest_entry


def get_next_entry_id() -> int:
    """Return the next id across all monthly JSON files."""
    if not DATA_DIR.exists():
        return 1

    last_id = 0
    for file_path in sorted(DATA_DIR.glob("profile_history_*.json")):
        entries = load_entries(file_path)
        file_last_id = max((entry.get("id", 0) for entry in entries), default=0)
        last_id = max(last_id, file_last_id)

    return last_id + 1


def save_profile_details(profile_details: dict[str, Any]) -> bool:
    """Save fetched profile details into the current monthly JSON file."""
    file_path = get_monthly_json_path()
    entries = load_entries(file_path)
    latest_entry = get_latest_saved_entry()

    if latest_entry and is_same_profile(latest_entry, profile_details):
        logging.info("No changes found. Skipping duplicate entry: %s", profile_details)
        return False

    new_entry = build_entry(profile_details, get_next_entry_id())
    entries.append(new_entry)
    write_entries(file_path, entries)
    logging.info("Saved new profile entry: %s", new_entry)
    return True


def main() -> None:
    setup_logging()
    username = "vAa8FNas4h"
    logging.info("Starting LeetCode profile tracker run.")

    try:
        profile_details = fetch_profile_details(username)
        saved = save_profile_details(profile_details)
        if saved:
            logging.info("Tracker run completed with a new saved entry.")
            print(f"Saved profile details for {profile_details['username']}: {profile_details}")
        else:
            logging.info("Tracker run completed without saving because data is unchanged.")
            print(f"No changes found for {profile_details['username']}. Entry was not saved.")
    except Exception:
        logging.exception("Tracker run failed.")
        raise


if __name__ == "__main__":
    main()
