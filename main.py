import sqlite3
from typing import Any

import requests


DATABASE_NAME = "leetcode.db"
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


def create_database(db_name: str = DATABASE_NAME) -> None:
    """Create the database table if it does not already exist."""
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                username TEXT NOT NULL,
                ranking INTEGER,
                reputation INTEGER,
                easy INTEGER,
                medium INTEGER,
                hard INTEGER,
                total INTEGER
            )
            """
        )
        conn.commit()


def fetch_profile_details(username: str) -> dict[str, Any]:
    """Fetch ranking, solved counts, and reputation for a LeetCode profile."""
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
        raise ValueError(f"LeetCode user not found: {username}")

    profile = matched_user.get("profile") or {}
    solved_counts = {
        item["difficulty"].lower(): item["count"]
        for item in matched_user.get("submitStats", {}).get("acSubmissionNum", [])
    }

    return {
        "username": matched_user["username"],
        "ranking": profile.get("ranking"),
        "reputation": profile.get("reputation"),
        "total": solved_counts.get("all", 0),
        "easy": solved_counts.get("easy", 0),
        "medium": solved_counts.get("medium", 0),
        "hard": solved_counts.get("hard", 0),
    }


def save_profile_details(profile_details: dict[str, Any], db_name: str = DATABASE_NAME) -> None:
    """Save fetched profile details into the database."""
    create_database(db_name)

    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO profile_history (
                username,
                ranking,
                reputation,
                easy,
                medium,
                hard,
                total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_details["username"],
                profile_details["ranking"],
                profile_details["reputation"],
                profile_details["easy"],
                profile_details["medium"],
                profile_details["hard"],
                profile_details["total"],
            ),
        )
        conn.commit()


def main() -> None:
    username = "vAa8FNas4h"
    create_database()
    profile_details = fetch_profile_details(username)
    save_profile_details(profile_details)
    print(f"Saved profile details for {profile_details['username']}: {profile_details}")


if __name__ == "__main__":
    main()
