import asyncio
import os
import re
import warnings

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mental_health.generate_response import analyze_mental_health_situation
from resources.generate_response import analyze_resource_situation
from benefits.generate_response import analyze_benefits

import socketio

generation_tasks = {}


os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_DEBUG_CPU_TYPE"] = "5"
warnings.filterwarnings("ignore", message=".*torchvision.*", category=UserWarning)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://feif-i7.isri.cmu.edu:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_keep_alive_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Connection"] = "keep-alive"
    return response

class Item(BaseModel):
    text: str
    previous_text: list
    model: str

@app.post("/benefit_response/")
async def benefit_response(item: Item):
    return StreamingResponse(
        analyze_benefits(item.text, item.previous_text, item.model),
        media_type='text/event-stream'
    )

@app.post("/wellness_response/")
async def wellness_response(item: Item):
    return StreamingResponse(
        analyze_mental_health_situation(item.text, item.previous_text, item.model),
        media_type='text/event-stream'
    )

@app.post("/resource_response/")
async def resource_response(item: Item):
    return StreamingResponse(
        analyze_resource_situation(item.text, item.previous_text, item.model),
        media_type='text/event-stream'
    )

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

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


@sio.event
async def start_generation(sid, data):
    """
    Expected data format:
      {
        "text": "user input",
        "previous_text": [...],
        "model": "copilot" or "chatgpt",
        "tool": "benefit" or "wellness" or "resource"
      }
    """
    print(f"[Socket.IO] Received start_generation from {sid} with data: {data}")

    text = data.get("text", "")
    previous_text = data.get("previous_text", [])
    model = data.get("model")
    tool = data.get("tool")
    
    if tool == "benefit":
        generator = analyze_benefits(text, previous_text, model)
    elif tool == "wellness":
        generator = analyze_mental_health_situation(text, previous_text, model)
    elif tool == "resource":
        print('here!!')
        generator = analyze_resource_situation(text, previous_text, model)
    else:
        await sio.emit("generation_update", {"chunk": "Error: Unknown tool."}, room=sid)
        return
    
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


