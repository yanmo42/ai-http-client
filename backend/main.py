import os
import json
import yaml
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openai import OpenAI
import google.generativeai as genai
import anthropic

import storage  # storage.py from earlier




# ─── Logging & Config ─────────────────────────────────────────────────────────
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ─── Legacy conversation_history.json logic (preserved) ──────────────────────
HISTORY_FILE = "conversation_history.json"
def load_conversation_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        return json.load(open(HISTORY_FILE))
    return {}
def save_conversation_history():
    json.dump(conversation_history, open(HISTORY_FILE, "w"), indent=2)
conversation_history = load_conversation_history()

# ─── FastAPI & CORS ────────────────────────────────────────────────────────────
app = FastAPI()
origins = ["http://localhost:3000","http://127.0.0.1:3000"]
app.add_middleware(CORSMiddleware,
    allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ─── Shared model caller ───────────────────────────────────────────────────────
def call_model(messages: List[dict]) -> dict:
    provider = config.get("default_provider")
    if provider == "openai":
        client = OpenAI(api_key=config["providers"]["openai"]["api_key"])
        resp = client.chat.completions.create(
            model=config["providers"]["openai"]["model"],
            messages=messages,
        )
        content = resp.choices[0].message.content.strip()

    elif provider == "gemini":
        genai.configure(api_key=config["providers"]["gemini"]["api_key"])
        gm = genai.GenerativeModel(config["providers"]["gemini"]["model"])
        prompt = " ".join(m["content"] for m in messages)
        resp = gm.generate_content(prompt)
        content = resp.text.strip()

    elif provider == "anthropic":
        client = anthropic.Client(api_key=config["providers"]["anthropic"]["api_key"])
        convo = ""
        for m in messages:
            convo += anthropic.HUMAN_PROMPT if m["role"]=="user" else anthropic.AI_PROMPT
            convo += m["content"]
        convo += anthropic.AI_PROMPT
        resp = client.completions.create(
            model=config["providers"]["anthropic"]["model"],
            prompt=convo
        )
        content = resp.completion.strip()

    else:
        raise HTTPException(400, "Unsupported provider")

    return {"role":"assistant","content":content,"timestamp":datetime.utcnow().isoformat()}


# ─── Pydantic models ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    prompt: str
    provider: Optional[str] = None
    user_id: str
    chat_id: str

class SessionCreate(BaseModel):
    name: str

class SessionOut(BaseModel):
    id: str; name: str; created_at: str; updated_at: str; chat_ids: List[str]

class ChatCreate(BaseModel):
    title: Optional[str] = None

class ChatOut(BaseModel):
    id: str; session_id: str; title: str; created_at: str

class MessageIn(BaseModel):
    role: str; content: str

class EphemeralIn(BaseModel):
    messages: List[MessageIn]


# ─── Legacy /chat endpoint (unchanged) ────────────────────────────────────────
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        prov = req.provider or config["default_provider"]
        uid, cid = req.user_id, req.chat_id
        conversation_history.setdefault(uid, {}).setdefault(cid, [])
        conversation_history[uid][cid].append({"role":"user","content":req.prompt})
        save_conversation_history()

        reply = call_model(conversation_history[uid][cid])
        conversation_history[uid][cid].append({"role":reply["role"],"content":reply["content"]})
        save_conversation_history()
        return {"provider":prov,"response":reply["content"]}
    except Exception as e:
        logger.error(f"/chat error: {e}")
        raise HTTPException(500, "Internal Server Error")



# ─── Ephemeral one-off chats ──────────────────────────────────────────────────
@app.post("/chat/ephemeral")
def chat_ephemeral(body: EphemeralIn):
    msgs = [m.dict() for m in body.messages]
    return call_model(msgs)


# ─── Sessions CRUD ─────────────────────────────────────────────────────────────
@app.get("/sessions", response_model=List[SessionOut])
def list_sessions():
    return storage.load_sessions()

@app.post("/sessions", response_model=SessionOut)
def create_session(body: SessionCreate):
    return storage.create_session(body.name)

@app.patch("/sessions/{sid}", response_model=SessionOut)
def update_session(sid: str, body: SessionCreate):
    storage.update_session(sid, name=body.name)
    sess = next((s for s in storage.load_sessions() if s["id"]==sid), None)
    if not sess: raise HTTPException(404, "Session not found")
    return sess

@app.delete("/sessions/{sid}", status_code=204)
def delete_session(sid: str):
    storage.delete_session(sid)


# ─── Chats in a Session ───────────────────────────────────────────────────────
@app.get("/sessions/{sid}/chats", response_model=List[ChatOut])
def list_chats(sid: str):
    sess = next((s for s in storage.load_sessions() if s["id"]==sid), None)
    if not sess: raise HTTPException(404, "Session not found")
    out = []
    for cid in sess["chat_ids"]:
        chat = storage.load_chat(cid)
        if chat:
            out.append({
                "id":         chat["id"],
                "session_id": chat["session_id"],
                "title":      chat["title"],
                "created_at": chat["created_at"]
            })
    return out

@app.post("/sessions/{sid}/chats", response_model=ChatOut)
def create_chat(sid: str, body: ChatCreate):
    if not any(s["id"]==sid for s in storage.load_sessions()):
        raise HTTPException(404, "Session not found")
    chat = storage.create_chat(sid, body.title)
    return {"id":chat["id"],"session_id":chat["session_id"],
            "title":chat["title"],"created_at":chat["created_at"]}


# ─── GET a Chat’s Message History ──────────────────────────────────────────────
@app.get("/chats/{cid}/messages", response_model=List[dict])
def get_messages(cid: str):
    chat = storage.load_chat(cid)
    if chat is None:
        raise HTTPException(404, "Chat not found")
    return chat["messages"]


# ─── Persistent messaging in a Chat ────────────────────────────────────────────
@app.post("/chats/{cid}/messages")
def post_message(cid: str, body: MessageIn):
    chat = storage.load_chat(cid)
    if chat is None:
        raise HTTPException(404, "Chat not found")
    chat["messages"].append({
        "role":body.role,"content":body.content,
        "timestamp":datetime.utcnow().isoformat()
    })
    reply = call_model(chat["messages"])
    chat["messages"].append(reply)
    storage.save_chat(chat)
    return reply


# ─── Global Exception Handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def handle_all(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return {"detail": "Internal Server Error"}



from fastapi.staticfiles import StaticFiles
import pathlib

# assume your folder structure is:
# project/
#   backend/
#     main.py
#   frontend/
#     index.html, styles.css, app.js

# compute the absolute path to ../frontend
HERE = pathlib.Path(__file__).parent
FRONTEND = HERE.parent / "frontend"

app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND), html=True),
    name="static",
)

