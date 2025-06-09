# ─────────────────────────────────────────────────────────────────────────────
# backend/app/all_endpoints.py
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import os

import asyncio
import os
import json
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.submodules import (
    get_questions_resources,
    construct_response,
    call_chatgpt_api_all_chats,
    internal_prompts,
)

import socketio

generation_tasks = {}

# (These environment variables are fine—no changes here)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_DEBUG_CPU_TYPE"] = "5"

# ─────────────────────────────────────────────────────────────────────────────
# Create FastAPI app, add CORS (allow React dev / 8000)
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # during React dev
        "http://127.0.0.1:8000",  # when served statically by FastAPI
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Keep-alive header (no change)
# ─────────────────────────────────────────────────────────────────────────────
@app.middleware("http")
async def add_keep_alive_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Connection"] = "keep-alive"
    return response


# ─────────────────────────────────────────────────────────────────────────────
# 1) Mount React’s static files (the freshly built JS/CSS) from frontend/build/static.
#
#    We assume this file is located at:
#      …/community_services_llm/backend/app/all_endpoints.py
#
#    so:
#      os.path.dirname(__file__)           → …/community_services_llm/backend/app
#      os.path.dirname(os.path.dirname(__file__)) → …/community_services_llm/backend
#      os.path.join(that, "../frontend/build/static")
#                    → …/community_services_llm/backend/../frontend/build/static
#                    → …/community_services_llm/frontend/build/static
# ─────────────────────────────────────────────────────────────────────────────
app.mount(
    "/static",
    StaticFiles(
        directory=os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "../frontend/build/static"
        )
    ),
    name="static"
)


# ─────────────────────────────────────────────────────────────────────────────
# SOCKET.IO setup (no change below this line) including connect, disconnect,
# run_generation, start_generation, reset_session, etc.
#
# You can leave all of your @sio.event definitions exactly as they were.
# ─────────────────────────────────────────────────────────────────────────────

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

class Message(BaseModel):
    text: str
    previous_text: list
    model: str
    organization: str

def process_raw_chunk(raw_chunk: str) -> str:
    if raw_chunk.startswith("data:"):
        return raw_chunk[len("data: "):].replace('\n','')
    return raw_chunk.strip()

def accumulate_chunks(generator):
    accumulated = ""
    for raw_chunk in generator:
        token = process_raw_chunk(raw_chunk)
        if token != "[DONE]":
            if token.startswith('#'):
                accumulated += '\n' + token
            elif token.endswith('<br/>'):
                accumulated += token + '\n'
            elif token == '<br/><br/>':
                accumulated += '<br/>'
            else:
                accumulated += token
        yield accumulated

@sio.event
async def connect(sid, environ):
    print(f"[Socket.IO] Client connected: {sid}")
    await sio.emit("welcome", {"message": "Welcome from backend!"}, room=sid)

@sio.event
async def disconnect(sid):
    print(f"[Socket.IO] Client disconnected: {sid}")

async def run_generation(sid, generator):
    try:
        for accumulated_text in accumulate_chunks(generator):
            await sio.emit("generation_update", {"chunk": accumulated_text}, room=sid)
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print(f"[Socket.IO] Generation task for {sid} was cancelled.")
        await sio.emit("generation_update", {"chunk": "Generation cancelled."}, room=sid)
        raise
    except Exception as e:
        print(f"[Socket.IO] Error during generation: {e}")
        await sio.emit("generation_update", {"chunk": f"Error: {e}"}, room=sid)
    finally:
        if sid in generation_tasks:
            del generation_tasks[sid]
        await sio.emit("generation_complete", {"message": "Response generation complete."}, room=sid)

# @sio.event
# async def start_generation(sid, data):
#     print(f"[Socket.IO] Received start_generation from {sid} with data: {data}")
#     text = data.get("text", "")
#     previous_text = data.get("previous_text", [])
#     model = data.get("model")
#     organization = data.get("organization")

#     generator = construct_response(text, previous_text, model, organization)
#     if sid in generation_tasks:
#         generation_tasks[sid].cancel()

#     task = asyncio.create_task(run_generation(sid, generator))
#     generation_tasks[sid] = task
@sio.event
async def start_generation(sid, data):
    print(f"[Socket.IO] Received start_generation from {sid} with data: {data}")
    text          = data.get("text", "")
    previous_text = data.get("previous_text", [])
    model         = data.get("model")
    organization  = data.get("organization")

    # 1) Offload the small “intent check” to a thread so we don't block
    loop = asyncio.get_running_loop()
    intent_msgs = [
      {
        "role": "system",
        "content": (
          "You’re a request analyzer.  "
          "Given one user message, answer **strictly** in JSON with two keys:\n"
          '  • "needs_goals": true if they want advice or help or concrete next steps;\n'
          '  • "verbosity": one of "brief","medium","deep".\n'
          "Return only valid JSON, no extra commentary."
        )
      },
      {"role": "user", "content": text}
    ]
    try:
        meta_resp = await loop.run_in_executor(
          None,
          call_chatgpt_api_all_chats,
          intent_msgs,
          False,
          40
        )
        meta = json.loads(meta_resp.strip())
        needs_goals = bool(meta.get("needs_goals", False))
    except Exception as e:
        print(f"[Socket.IO] Error parsing needs_goals: {e}")
        needs_goals = False

    # 2) If goals are needed, fetch & emit them
    #if the goals are not nneeded then emit them and remove them and delete them 
    #If the goals are not needed then emit them and discard them and delete them 
    if needs_goals:
        loop = asyncio.get_running_loop()
        full_text, external_resources, raw_prompt = await loop.run_in_executor(
           None, get_questions_resources, text, previous_text, organization
        )
        match = re.search(r"SMART Goals:\s*(.*?)\nQuestions:", full_text, flags=re.DOTALL)
        if match:
            goals = [
                line.strip().lstrip("•").strip()
                for line in match.group(1).splitlines()
                if line.strip()
            ]
        else:
            goals = []
        resources = [
            r.strip() for r in external_resources.splitlines() if r.strip()
        ]

        await sio.emit(
          "goals_update",                   # ← new event name
          {"goals": goals, "resources": resources},
          room=sid
        )

    # 3) Continue with your existing streaming logic
    generator = construct_response(text, previous_text, model, organization)
    if sid in generation_tasks:
        generation_tasks[sid].cancel()
    task = asyncio.create_task(run_generation(sid, generator))
    generation_tasks[sid] = task



@sio.event
async def reset_session(sid):
    print(f"[Socket.IO] Reset session for client: {sid}")
    if sid in generation_tasks:
        generation_tasks[sid].cancel()
        del generation_tasks[sid]
    await sio.emit("reset_ack", {"message": "Session reset."}, room=sid)


# ─────────────────────────────────────────────────────────────────────────────
# 2) Single “catch-all” GET route must come *after* the /static mount.
#    Any request not matching “/static/*” (e.g. “/wellness-goals”) will get index.html,
#    and then React Router (in index.html) will load the correct component.
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    return FileResponse("../frontend/build/index.html")
