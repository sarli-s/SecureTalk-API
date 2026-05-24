# Secure Messenger

A secure, real-time messaging system built with FastAPI and SQLite.
Users can register, log in, send encrypted messages, and receive them instantly — no polling, no browser needed.

---

## How it works

### Registration & Login
When a user registers, their password is run through **bcrypt** — a one-way hashing function.
The original password is never stored anywhere. Only the hash (a fingerprint) is saved.

At login, the typed password is hashed again and compared to the stored fingerprint.
If they match, the server issues a **JWT token** — a signed badge the client must include in every future request.

### Sending & Reading Messages
Every message is encrypted with **AES-256-GCM** before being written to the database.
What gets stored is unreadable ciphertext. The original text is only recovered at read time, in memory, and only for the user who is the sender or recipient.

A thief who steals the database gets:
- bcrypt fingerprints (cannot be reversed)
- AES ciphertext (cannot be read without the key)

### Real-Time Messaging (Stage 2)
When a message is sent, the server instantly **pushes** it to all connected clients via **Server-Sent Events (SSE)**.
No polling. No page refresh. The recipient sees the message the moment it is saved.

Each user connects once to `GET /stream` and keeps the connection open.
The server broadcasts only the messages relevant to that user (sender or recipient).

---

## Tech stack

- **FastAPI** — web framework
- **SQLAlchemy** — ORM, SQLite database
- **bcrypt** — password hashing
- **python-jose** — JWT token creation and validation
- **cryptography** — AES-256-GCM encryption
- **sse-starlette** — Server-Sent Events support
- **httpx** — HTTP client used in CLI and tests

---

## Project structure

```
server/
  main.py           # App entry point
  models.py         # Database tables (User, Message)
  schemas.py        # Request/response shapes (Pydantic)
  auth.py           # Password hashing + JWT logic
  crypto.py         # AES-256-GCM encrypt/decrypt
  routes.py         # API endpoints + SSE stream
  broadcaster.py    # Real-time pub/sub manager
client/
  client.py         # Terminal CLI client
tests/
  test_app.py       # Full test suite (22 tests)
seed.py             # Populates DB with test users and messages
```

---

## API endpoints

| Method | Route | Auth required | Description |
|--------|-------|---------------|-------------|
| POST | `/register` | No | Create a new user account |
| POST | `/login` | No | Get a JWT token |
| POST | `/messages` | Yes | Send an encrypted message |
| GET | `/messages` | Yes | Read your messages (decrypted) |
| GET | `/stream` | Yes | SSE stream — receive messages in real time |

---

## Running locally

**Terminal 1 — start the server:**
```bash
pip install -r requirements.txt
uvicorn server.main:app --reload --port 8001
```

**Terminal 2 — seed the database (optional):**
```bash
python seed.py
```

This creates 3 users (`alice`, `bob`, `charlie`) with passwords `alice-secret`, `bob-secret`, `charlie-secret`.

**Terminal 3 & 4 — run the CLI client:**
```bash
python -m client.client
```

Login as different users in each terminal. To send a message:
```
> bob:hello, can you see this?
```

The message appears instantly in Bob's terminal — no refresh needed.

---

## Running tests

```bash
pytest tests/ -v
```

22 tests covering authentication, encryption, messaging, and the broadcaster.

---

## What's in the database

| Table | Column | Stored as |
|-------|--------|-----------|
| users | username | plain text (not secret) |
| users | password_hash | bcrypt fingerprint — irreversible |
| messages | sender / recipient | plain text (not secret) |
| messages | ciphertext | AES-256-GCM encrypted — unreadable without key |

To inspect:
```bash
python -c "import sqlite3; c=sqlite3.connect('messenger.db'); print('USERS:', c.execute('SELECT id, username FROM users').fetchall()); print('MESSAGES:', c.execute('SELECT id, sender, recipient FROM messages').fetchall())"
```
