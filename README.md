# Secure Messenger

A secure REST API for private messaging, built with FastAPI and SQLite.
Users can register, log in, send encrypted messages, and read them back.
Nothing sensitive is ever stored in plain text — not passwords, not messages.

---

## How it works

### Registration & Login
When a user registers, their password is run through **bcrypt** — a one-way hashing function.
The original password is never stored anywhere. Only the hash (a fingerprint) is saved.

At login, the typed password is hashed again and compared to the stored fingerprint.
If they match, the server issues a **JWT token** — a signed badge the client must include in every future request.
The server can verify the token's authenticity purely from its signature, no database lookup needed.

### Sending & Reading Messages
Every message is encrypted with **AES-256-GCM** before being written to the database.
What gets stored is unreadable ciphertext. The original text is only recovered at read time, in memory, and only for the user who is the sender or recipient.

A thief who steals the database gets:
- bcrypt fingerprints (cannot be reversed)
- AES ciphertext (cannot be read without the key)

---

## Tech stack

- **FastAPI** — web framework
- **SQLAlchemy** — ORM, SQLite database
- **bcrypt** — password hashing
- **python-jose** — JWT token creation and validation
- **cryptography** — AES-256-GCM encryption

---

## Project structure

```
server/
  main.py       # App entry point, wires everything together
  models.py     # Database tables (User, Message)
  schemas.py    # Request/response shapes (Pydantic)
  auth.py       # Password hashing + JWT logic
  crypto.py     # AES-256-GCM encrypt/decrypt
  routes.py     # The four API endpoints
tests/
  test_app.py   # Full test suite (17 tests)
```

---

## API endpoints

| Method | Route | Auth required | Description |
|--------|-------|---------------|-------------|
| POST | `/register` | No | Create a new user account |
| POST | `/login` | No | Get a JWT token |
| POST | `/messages` | Yes | Send an encrypted message |
| GET | `/messages` | Yes | Read your messages (decrypted) |

---

## Running locally

```bash
pip install -r requirements.txt
uvicorn server.main:app --reload --port 8001
```

Open http://localhost:8001/docs for the interactive Swagger UI.

```bash
pytest tests/ -v
```

---

## What's next — Stage 2

Stage 1 is request/response only. Stage 2 will add **real-time messaging** using Server-Sent Events (SSE).

Instead of polling for new messages, a connected client will receive them instantly the moment they are sent — no asking, just listening. A terminal CLI client (`client.py`) will make it possible to run two side-by-side terminals and chat live.
