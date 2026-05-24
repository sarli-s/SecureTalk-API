"""
seed.py — Populate the database with test users and messages.

Usage:
    python seed.py
"""

import httpx

BASE_URL = "http://localhost:8001"

USERS = [
    {"username": "alice", "password": "alice-secret"},
    {"username": "bob",   "password": "bob-secret"},
    {"username": "charlie", "password": "charlie-secret"},
]

MESSAGES = [
    ("alice", "bob",     "Hey Bob, the server is up!"),
    ("bob",   "alice",   "Nice, I can see your message."),
    ("alice", "charlie", "Charlie, encryption is working!"),
    ("charlie", "alice", "Confirmed — messages are safe at rest."),
    ("bob",   "charlie", "Let's sync later today."),
]


def register_and_login(user: dict) -> str:
    r = httpx.post(f"{BASE_URL}/register", json=user)
    if r.status_code == 201:
        print(f"  [+] Registered:  {user['username']}")
    elif r.status_code == 400:
        print(f"  [~] Already exists: {user['username']}")
    else:
        print(f"  [!] Register error for {user['username']}: {r.text}")

    r = httpx.post(f"{BASE_URL}/login", json=user)
    if r.status_code != 200:
        raise RuntimeError(f"Login failed for {user['username']}: {r.text}")
    print(f"  [+] Logged in:   {user['username']}")
    return r.json()["access_token"]


def main():
    print("\n=== Seeding database ===\n")

    tokens = {}
    print("Registering & logging in users...")
    for user in USERS:
        tokens[user["username"]] = register_and_login(user)

    print("\nSending seed messages...")
    for sender, recipient, content in MESSAGES:
        r = httpx.post(
            f"{BASE_URL}/messages",
            json={"content": content, "recipient": recipient},
            headers={"Authorization": f"Bearer {tokens[sender]}"},
        )
        if r.status_code == 201:
            print(f"  [+] {sender} → {recipient}: '{content}'")
        else:
            print(f"  [!] Failed: {r.text}")

    print("\nDone! Database is seeded.\n")


if __name__ == "__main__":
    main()
