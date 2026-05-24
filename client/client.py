"""
client.py — Terminal CLI client for Secure Messenger.

Usage:
    python -m client.client
"""

import json
import threading
import getpass
import httpx

BASE_URL = "http://localhost:8001"


def prompt_auth() -> tuple[str, str]:
    print("\n=== Secure Messenger ===")
    print("1) Register")
    print("2) Login")
    choice = input("Choose (1/2): ").strip()

    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    if choice == "1":
        r = httpx.post(f"{BASE_URL}/register", json={"username": username, "password": password})
        if r.status_code != 201:
            print(f"Registration failed: {r.json().get('detail')}")
            return prompt_auth()
        print("Registered successfully! Logging in...")

    r = httpx.post(f"{BASE_URL}/login", json={"username": username, "password": password})
    if r.status_code != 200:
        print(f"Login failed: {r.json().get('detail')}")
        return prompt_auth()

    token = r.json()["access_token"]
    return username, token


def load_history(token: str, my_username: str):
    r = httpx.get(f"{BASE_URL}/messages", headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        return
    messages = r.json()
    if not messages:
        return
    print("\n--- message history ---")
    for m in messages:
        print(f"  [{m['sender']} → {m['recipient']}]: {m['content']}")
    print("-----------------------\n")


def listen_for_messages(token: str, my_username: str):
    """Background thread — opens SSE stream and prints incoming messages."""
    with httpx.stream("GET", f"{BASE_URL}/stream",
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=None) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                raw = line[len("data:"):].strip()
                try:
                    msg = json.loads(raw)
                    print(f"\n  [{msg['sender']} → {msg['recipient']}]: {msg['content']}")
                    print("  > ", end="", flush=True)
                except json.JSONDecodeError:
                    pass


def main():
    username, token = prompt_auth()
    print(f"\nWelcome, {username}!  (type your message and press Enter, or 'quit' to exit)")
    print("Format: recipient:message  (e.g.  bob:hello!)\n")

    load_history(token, username)

    listener = threading.Thread(target=listen_for_messages, args=(token, username), daemon=True)
    listener.start()

    while True:
        try:
            text = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if text.lower() == "quit":
            print("Goodbye!")
            break

        if ":" not in text:
            print("  Format: recipient:message")
            continue

        recipient, _, content = text.partition(":")
        recipient = recipient.strip()
        content = content.strip()

        if not recipient or not content:
            print("  Format: recipient:message")
            continue

        r = httpx.post(
            f"{BASE_URL}/messages",
            json={"content": content, "recipient": recipient},
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code != 201:
            print(f"  Error: {r.json().get('detail')}")


if __name__ == "__main__":
    main()
