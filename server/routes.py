"""
routes.py — All API route handlers.

╔══════════════════════════════════════════════╗
║  YOUR TASK: implement the four routes.       ║
╚══════════════════════════════════════════════╝

WHY A SEPARATE routes.py?
  In real projects, main.py only creates the app and wires things together.
  The actual logic lives in dedicated files — one per feature area.
  This keeps files small, focused, and easy to navigate.
  main.py imports this router and registers it with one line.

THE FOUR ROUTES YOU NEED TO IMPLEMENT:

  ┌─────────────────────────────────────────────────────────────────────┐
  │ POST /register                                                      │
  │   Receives: RegisterRequest (username, password)                    │
  │   1. Check if the username is already taken → return 400 if so     │
  │   2. Hash the password (NEVER store plain text)                     │
  │   3. Save the new User to the database                              │
  │   4. Return a success message                                       │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ POST /login                                                         │
  │   Receives: LoginRequest (username, password)                       │
  │   1. Find the user in the database → return 401 if not found       │
  │   2. Verify the password against the stored hash → 401 if wrong    │
  │   3. Create and return a JWT token                                  │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ POST /messages                          [requires valid JWT]        │
  │   Receives: SendMessageRequest (content, recipient)                 │
  │   1. Encrypt the content with encrypt()                             │
  │   2. Save a new Message row (sender=current user, recipient=...)    │
  │   3. Return the message as MessageResponse (with decrypted content) │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ GET /messages                           [requires valid JWT]        │
  │   1. Fetch all messages from the database                           │
  │   2. Decrypt each message's ciphertext before returning             │
  │   3. Return a list of MessageResponse objects                       │
  │                                                                     │
  │   THINK ABOUT: should a user see ALL messages, or only those        │
  │   where they are the sender or recipient?                           │
  └─────────────────────────────────────────────────────────────────────┘

USEFUL IMPORTS ALREADY PROVIDED BELOW.
USEFUL PATTERN — how to query the database:
  user = db.query(User).filter(User.username == "alice").first()
  messages = db.query(Message).order_by(Message.created_at).all()

USEFUL PATTERN — how to save a new row:
  new_user = User(username="alice", password_hash="$2b$...")
  db.add(new_user)
  db.commit()
  db.refresh(new_user)   ← fills in the auto-generated id and created_at
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from .models import User, Message, get_db
from .schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    SendMessageRequest, MessageResponse,
)
from .auth import hash_password, verify_password, create_token, require_auth
from .crypto import encrypt, decrypt
from .broadcaster import broadcaster


log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# TODO 1 — Register a new user
# ---------------------------------------------------------------------------
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="username already taken")
    db.add(User(username=body.username, password_hash=hash_password(body.password)))
    db.commit()
    return {"message": "registered successfully"}


# ---------------------------------------------------------------------------
# TODO 2 — Login and receive a JWT token
# ---------------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    return TokenResponse(access_token=create_token(user.username))


# ---------------------------------------------------------------------------
# TODO 3 — Send a message (authenticated)
# ---------------------------------------------------------------------------
@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    username: str = Depends(require_auth),
):
    msg = Message(sender=username, recipient=body.recipient, ciphertext=encrypt(body.content))
    db.add(msg)
    db.commit()
    db.refresh(msg)
    response = MessageResponse(id=msg.id, sender=msg.sender, recipient=msg.recipient, content=body.content, created_at=msg.created_at)
    await broadcaster.publish(response.model_dump(mode="json"))
    return response


# ---------------------------------------------------------------------------
# TODO 4 — Fetch messages (authenticated)
# ---------------------------------------------------------------------------
@router.get("/messages", response_model=list[MessageResponse])
def get_messages(
    db: Session = Depends(get_db),
    username: str = Depends(require_auth),
):
    rows = db.query(Message).filter(
        (Message.sender == username) | (Message.recipient == username)
    ).order_by(Message.created_at).all()
    return [
        MessageResponse(id=r.id, sender=r.sender, recipient=r.recipient, content=decrypt(r.ciphertext), created_at=r.created_at)
        for r in rows
    ]


@router.get("/stream")
async def stream(
    username: str = Depends(require_auth),
):
    q = broadcaster.subscribe(username)
    log.info("SSE CONNECT  user=%s", username)

    async def event_generator():
        try:
            while True:
                message = await q.get()
                yield {"data": json.dumps(message, default=str)}
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(username, q)
            log.info("SSE DISCONNECT  user=%s", username)

    return EventSourceResponse(event_generator())
