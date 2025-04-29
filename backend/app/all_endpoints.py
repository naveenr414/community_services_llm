import asyncio
import os

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.submodules import construct_response
from app.process_profiles import get_all_outreach, get_all_service_users
from app.login import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import update_conversation, add_new_wellness_checkin

import socketio
from datetime import timedelta
import secrets

generation_tasks = {}

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_DEBUG_CPU_TYPE"] = "5"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Run the React frontend
@app.middleware("http")
async def add_keep_alive_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Connection"] = "keep-alive"
    return response

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

# Add this endpoint to your FastAPI app
@app.post("/api/auth/login")
async def login(login_data: LoginRequest):
    print("Analyzing login_data {} {}".format(login_data.username,login_data.password))
    success, _, role = authenticate_user(login_data.username, login_data.password)
    
    if not success:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": login_data.username, "role": role},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=role
    )

class NewWellness(BaseModel):
    patientName: str
    lastSession: str
    nextCheckIn: str
    followUpMessage: str

@app.get("/service_user_list/")
async def service_user_list(name):
    return get_all_service_users(name)

@app.get("/outreach_list/")
async def outreach_list(name):
    return get_all_outreach(name)

@app.post("/new_checkin/")
async def create_item(item: NewWellness, current_user: str = Depends(get_current_user)):
    success, message = add_new_wellness_checkin(
        current_user, 
        item.patientName, 
        item.lastSession, 
        item.nextCheckIn, 
        item.followUpMessage
    )
    
    if success:
        return {"message": "Check-in added successfully", "item": item}
    else:
        raise HTTPException(status_code=400, detail=message)


app.mount("/static", StaticFiles(directory="../frontend/build/static"), name="static")

# Handle Socket Messages

class Message(BaseModel):
    text: str
    previous_text: list
    model: str
    organization: str
    conversation_id: str
    username: str

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

def process_raw_chunk(raw_chunk: str) -> str:
    if raw_chunk.startswith("data:"):
        return raw_chunk[len("data: "):].replace('\n','')
    return raw_chunk.strip()

def accumulate_chunks(generator):
    """
    Accumulates and processes streaming text chunks from a generator.

    This function iterates over a generator of raw text chunks, processes each chunk,
    and appends it to an accumulated string with appropriate formatting. The function 
    yields the progressively accumulated text after each chunk is processed.

    Processing rules:
    - If the token is "[DONE]", it is ignored.
    - If the token starts with '#', a newline is prepended before adding it.
    - If the token ends with '<br/>', a newline is appended after it.
    - If the token is '<br/><br/>', it is replaced with a single '<br/>'.
    - Otherwise, the token is appended to the accumulated text.

    Parameters:
    generator (iterator): An iterator that yields raw text chunks.

    Yields:
    str: The progressively accumulated text after processing each chunk.
    """
    accumulated = ""
    for raw_chunk in generator:
        # print("before: {}".format(list(raw_chunk)))
        token = process_raw_chunk(raw_chunk)
        # print("after: {}".format(token))
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

async def run_generation(sid, generator,text,metadata):
    """
    Handles real-time streaming of generated text chunks to a client via Socket.IO.

    This function processes a generator that produces accumulated text chunks and 
    asynchronously emits updates to the client. It ensures graceful handling of 
    cancellations and errors.

    Parameters:
    sid (str): The session ID of the client.
    generator (Iterator[str]): An iterator yielding progressively accumulated text chunks.

    Behavior:
    - Iterates through `accumulate_chunks(generator)`, emitting each chunk as a "generation_update".
    - Introduces a small delay (`asyncio.sleep(0.1)`) to prevent overwhelming the client.
    - Catches `asyncio.CancelledError` to handle task cancellation gracefully and notifies the client.
    - Handles unexpected exceptions, logging errors and notifying the client.
    - Ensures that the session ID is removed from `generation_tasks` upon completion.
    - Sends a final "generation_complete" event to signal the end of text generation.

    Returns:
    None (asynchronous function).
    """
    try:
        total_text = ""
        for accumulated_text in accumulate_chunks(generator):
            await sio.emit("generation_update", {"chunk": accumulated_text}, room=sid)
            await asyncio.sleep(0.1)
            total_text = accumulated_text
        update_conversation(metadata,[{'role': 'user', 'content': text}, {'role': 'system', 'content': total_text}])
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
    Initiates a text generation process based on the provided user input and tool type.

    This function processes incoming data from a Socket.IO connection, determines the appropriate
    analysis function based on the specified tool type, and starts an asynchronous generation task.
    If a previous task exists for the given session ID (`sid`), it is canceled before starting a new one.

    Expected data format:
    {
        "text": str,          # User input text.
        "previous_text": list, # List of previous messages for context.
        "model": str,         # Model type ("copilot" or "chatgpt").
        "tool": str           # Tool type ("benefit", "wellness", or "resource").
    }

    Parameters:
    sid (str): The session ID associated with the request.
    data (dict): A dictionary containing the input text, previous conversation history,
                 selected model, and tool type.

    Behavior:
    - Calls the appropriate function (`analyze_benefits`, `analyze_mental_health_situation`, or
      `analyze_resource_situation`) based on the `tool` value.
    - Emits an error message if an invalid `tool` is provided.
    - Cancels any existing generation task associated with the session ID before starting a new one.
    - Creates an asynchronous task (`run_generation`) to process the generator and store it.
    """
    print(f"[Socket.IO] Received start_generation from {sid} with data: {data}")

    text = data.get("text", "")
    previous_text = data.get("previous_text", [])
    model = data.get("model")
    organization = data.get("organization")
    conversation_id = data.get("conversation_id","")
    if conversation_id == "":
        conversation_id = secrets.token_hex(16)
        await sio.emit("conversation_id", {"conversation_id": conversation_id}, room=sid)
    username = data.get("username","")

    generator = construct_response(text, previous_text, model,organization)
    
    if sid in generation_tasks:
        generation_tasks[sid].cancel()

    task = asyncio.create_task(run_generation(sid, generator,text,{'conversation_id': conversation_id, 'username': username}))
    generation_tasks[sid] = task


@sio.event
async def reset_session(sid):
    print(f"[Socket.IO] Reset session for client: {sid}")
    if sid in generation_tasks:
        generation_tasks[sid].cancel()
        del generation_tasks[sid]
    await sio.emit("reset_ack", {"message": "Session reset."}, room=sid)


@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    return FileResponse("../frontend/build/index.html")
