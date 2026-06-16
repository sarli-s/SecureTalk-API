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

### Real-Time Messaging
When a message is sent, the server instantly **pushes** it to all connected clients via **Server-Sent Events (SSE)**.
No polling. No page refresh. The recipient sees the message the moment it is saved.

Each user connects once to `GET /stream` and keeps the connection open.
The server delivers only the messages relevant to that user (sender or recipient).

---

## Design Decisions & Why

### Why bcrypt and not SHA-256?
SHA-256 is fast — a modern GPU can compute billions of hashes per second. If an attacker steals the database, they can brute-force a SHA-256 hash in minutes.

bcrypt is **intentionally slow**. Its work factor means one hash attempt takes ~100ms. The same brute-force attack would take decades. The slowness is the security feature, not a bug.

Rule: use bcrypt (or Argon2/scrypt) for passwords. Never SHA-256/MD5 for passwords.

### Why AES-256-GCM and not AES-CBC?
AES-CBC provides **confidentiality only** — it hides the content, but a tampered ciphertext decrypts silently into garbage. An attacker can flip bits in the stored ciphertext and the server won't know.

AES-GCM provides **confidentiality + integrity**. It appends an authentication tag to the ciphertext. If anyone modifies even one bit in storage, decryption raises an exception instead of returning corrupted data.

Additionally, a **fresh random nonce** is generated for every message (`os.urandom(12)`). This means identical messages produce completely different ciphertexts — an attacker watching the database cannot detect repeated content.

### Why SSE and not WebSockets?
WebSockets are **bidirectional** — both sides can send at any time. That power comes with complexity: you need to manage the full connection lifecycle, handle ping/pong keepalives, and parse a binary framing protocol.

SSE is **server-to-client only**, which is all we need for message delivery. It runs over plain HTTP/1.1, reconnects automatically on drop, and is simpler to implement and test. The client sends messages via regular `POST /messages` — SSE is just the delivery channel.

Rule: use SSE when the server pushes, WebSockets when both sides need to send.

### Why JWT and not sessions?
Traditional sessions store state on the server (a lookup table of session IDs). JWT tokens are **self-contained** — the server encodes the username and expiry directly in the token and signs it. Validation is pure math: no database lookup needed.

This makes the system stateless and easy to scale horizontally — any server instance can validate any token without sharing session state.

Known trade-off: JWT tokens cannot be revoked before they expire. If a user logs out, their token remains valid until expiry (24 hours in this implementation). A production system would add a token blocklist (Redis) or use short expiry times.

### Why SQLite and not PostgreSQL?
SQLite is a single file — no server to install, no configuration, perfect for development and learning. The ORM layer (SQLAlchemy) abstracts the database entirely: switching to PostgreSQL in production requires changing one line (`DATABASE_URL`).

Known limitation: SQLite has limited concurrent write capacity. Under high load, writers queue up. For a production multi-user system, PostgreSQL is the right choice.

### Key Management
The AES encryption key and JWT secret are loaded from environment variables (`.env` file, excluded from git). This means:
- The same key survives server restarts — stored messages remain readable
- The key is never in source code — cloning the repository does not expose it
- Each deployment can have its own unique key

The `.env` file must never be committed to git (already in `.gitignore`).

---

## Known Trade-offs (What a Production Version Would Fix)

| Issue | Current state | Production fix |
|-------|--------------|----------------|
| Token revocation | JWT valid until expiry — no logout | Redis blocklist or `login_version` in DB |
| Key rotation | Changing the AES key breaks all stored messages | Envelope encryption (encrypt the key, not the data) |
| SSE auth in browser | Browser `EventSource` API cannot set headers — use `?token=` query param | Cookie-based auth or a proxy that injects the header |
| Single-server broadcaster | `Broadcaster` lives in process memory — multiple server instances can't share it | Replace with Redis pub/sub |
| bcrypt on the event loop | `bcrypt.hashpw` is blocking CPU work — in `async def` it would block the event loop | Run in `asyncio.run_in_executor` |
| No rate limiting | `POST /login` can be brute-forced | Add slowdown after failed attempts (e.g., `slowapi`) |

---

## Tech Stack

| Library | Why this one |
|---------|-------------|
| **FastAPI** | Async-first, automatic OpenAPI docs, clean dependency injection |
| **SQLAlchemy** | ORM abstracts the DB — swap SQLite for PostgreSQL with one config change |
| **bcrypt** | Intentionally slow password hashing with built-in salt |
| **python-jose** | JWT creation and validation with HS256 signing |
| **cryptography** | AES-256-GCM via the `cryptography` library's hazmat primitives |
| **sse-starlette** | SSE protocol wrapper that integrates cleanly with FastAPI async generators |
| **httpx** | Async HTTP client used in the CLI client and tests |
| **python-dotenv** | Loads `.env` file so keys survive restarts and never appear in source code |

---

## Project Structure

```
server/
  main.py           # App entry point, lifespan, logging config
  models.py         # SQLAlchemy ORM tables (User, Message)
  schemas.py        # Pydantic request/response shapes
  auth.py           # bcrypt hashing + JWT creation/validation
  crypto.py         # AES-256-GCM encrypt/decrypt
  routes.py         # All API endpoints + SSE stream
  broadcaster.py    # asyncio.Queue-based pub/sub for SSE fan-out
client/
  client.py         # Terminal CLI client (threading + httpx streaming)
tests/
  test_app.py       # Full test suite (25 tests)
seed.py             # Populates DB with test users and messages
.env                # AES_KEY + JWT_SECRET — never commit this
```

---

## API Endpoints

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| POST | `/register` | No | Create a new user account |
| POST | `/login` | No | Get a JWT token |
| POST | `/messages` | Yes | Send an encrypted message |
| GET | `/messages` | Yes | Read your messages (decrypted) |
| GET | `/stream` | Yes | SSE stream — receive messages in real time |
| GET | `/users/online` | Yes | List currently connected SSE users |

The `/stream` endpoint accepts auth via:
- `Authorization: Bearer <token>` header (CLI clients)
- `?token=<token>` query parameter (browser `EventSource`, which cannot set custom headers)

---

## Running Locally

**Step 1 — copy and configure your keys:**
```bash
# .env is already created with generated keys
# To regenerate:
python -c "import os, secrets; print('AES_KEY=' + os.urandom(32).hex()); print('JWT_SECRET=' + secrets.token_hex(32))"
```

**Terminal 1 — start the server:**
```bash
pip install -r requirements.txt
uvicorn server.main:app --reload --port 8001
```

**Terminal 2 — seed the database (optional):**
```bash
python seed.py
```

Creates 3 users: `alice` / `alice-secret`, `bob` / `bob-secret`, `charlie` / `charlie-secret`.

**Terminal 3 & 4 — run the CLI client:**
```bash
python -m client.client
```

Login as different users in each terminal. To send a message:
```
> bob:hello, can you see this?
```

To send to everyone:
```
> all:hello everyone!
```

The message appears instantly in the recipient's terminal — no refresh needed.

---

## Running Tests

```bash
pytest tests/ -v
```

25 tests covering authentication, encryption, messaging, SSE broadcasting, and the broadcaster isolation logic.

---

## What's in the Database

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
