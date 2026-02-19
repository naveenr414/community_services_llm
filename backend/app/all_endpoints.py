"""FastAPI application and Socket.IO endpoints for the PeerCopilot backend.

This module wires routes, background scheduler jobs, and socket event handlers.
"""

import asyncio
import os
import threading
import time
import secrets

from fastapi import FastAPI, Request, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field 
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import threading
import time
import socketio
from app.phi_scrubber import PHIScrubber
from openai import AzureOpenAI

from app.audit_logger import AuditLogger
from app.submodules import construct_response
from app.process_profiles import get_all_outreach, get_all_service_users
from app.login import get_current_user, UserData
from app.login import router as auth_router
from app.audit_viewer import router as audit_router

from typing import Optional
import psycopg

from app.database import (
    update_conversation, 
    add_new_service_user, 
    fetch_service_user_checkins, 
    edit_service_user_outreach,
    get_notification_settings,
    update_notification_settings
)
from app.generate_outreach import generate_check_ins_rule_based
from app.notifications import notification_job
import openai 

# Environment configuration
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_DEBUG_CPU_TYPE"] = "5"

scheduler = BackgroundScheduler(timezone='America/New_York')
scheduler.add_job(notification_job, CronTrigger(minute='*/15'), id='send_notifications')

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    print("Scheduler started")
    yield
    scheduler.shutdown()
    print("Scheduler stopped")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        os.environ.get("FRONTEND_URL", ""),
        "https://peercopilot.com",
        "https://www.peercopilot.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(audit_router)

# Request/Response model

class NewWellness(BaseModel):
    patientName: str
    lastSession: str
    nextCheckIn: str
    followUpMessage: str
    username: str
    location: str

# Middleware
@app.middleware("http")
async def add_keep_alive_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Connection"] = "keep-alive"
    return response

# Notification settings endpoints
class NotificationSettingsUpdate(BaseModel):
    username: str
    email: str
    notifications_enabled: bool
    notification_time: str
    
@app.get("/api/notification-settings")
async def get_user_notification_settings(current_user: UserData = Depends(get_current_user)):
    """Get notification settings for a user"""
    username = current_user.username
    
    success, result = get_notification_settings(username)
    
    if success:
        return {"success": True, "settings": result}
    else:
        raise HTTPException(status_code=400, detail=result)


@app.post("/api/notification-settings")
async def update_user_notification_settings(
    settings: NotificationSettingsUpdate,
    current_user: UserData = Depends(get_current_user)
):
    """Update notification settings for a user"""
    username = current_user.username
    
    # Use token username instead of trusting client
    if username != settings.username:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Basic email validation
    if '@' not in settings.email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    success, message = update_notification_settings(
        username,
        settings.email,
        settings.notifications_enabled,
        settings.notification_time
    )
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)
    
# Health check endpoints
@app.get("/")
async def root():
    return {"status": "ok", "message": "PeerCopilot Backend Running"}


@app.get("/health")
async def health():
    return {"status": "ok"}

def warmup_models():
    """Background task to load embeddings after server starts"""
    try:
        print("[Warmup] Loading embeddings...")
        from app.rag_utils import get_model_and_indices
        get_model_and_indices()
        print("[Warmup] Embeddings loaded successfully")
    except Exception as e:
        print(f"[Warmup] Failed to load embeddings: {e}")

# Start a background thread to warm up embeddings after server start (may be slow)
threading.Thread(target=warmup_models, daemon=True).start()

# Service user endpoints
class NewServiceUser(BaseModel):
    patientName: str
    lastSession: str
    nextCheckIn: str
    followUpMessage: str
    username: str

class SidebarItem(BaseModel):
    title: str = Field(description="A short, 3-5 word title for the goal or resource.")
    details: str = Field(description="A single actionable sentence describing the next step or key info.")

class SidebarState(BaseModel):
    goals: list[SidebarItem] = Field(description="Current, active goals based on the ENTIRE conversation.")
    resources: list[SidebarItem] = Field(description="All relevant resources mentioned so far.")

def generate_sidebar_update(all_messages, sid, loop):
    """
    Analyzes the FULL conversation to produce a cumulative, detailed sidebar.
    """
    try:
        # 1. Use the FULL history (filter out system/tool messages to save some tokens if you want)
        # We keep 'user' and 'assistant' to understand the flow.
        context_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in all_messages 
            if m["role"] in ["user", "assistant"]
        ]

        system_prompt = (
            "You are the state manager for a peer support dashboard. "
            "Analyze the ENTIRE conversation history provided below.\n"
            "1. Identify 3-5 'Active Goals'. These should be tasks the user is currently working on. "
            "   - If a goal was completed or abandoned in the chat, DO NOT include it.\n"
            "   - Provide a 'details' sentence for each (e.g., 'Check eligibility tool for SNAP').\n"
            "2. Identify 'Resources'. These are organizations, tools, or websites mentioned by the assistant. "
            "   - Provide a 'details' sentence (e.g., 'Located at 123 Main St, open 9-5')."
        )

        messages = [{"role": "system", "content": system_prompt}] + context_messages

        # 2. Call GPT-4o-mini
        client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=os.environ.get("OPENAI_AZURE_ENDPOINT"),
            api_key=os.environ.get("OPENAI_API_KEY_AZURE"),
        )
        
        completion = client.chat.completions.parse(
            model="gpt-5-chat", 
            messages=messages,
            response_format=SidebarState
        )
        
        state_data = completion.choices[0].message.parsed
        
        # 3. Serialize to dict for JSON transmission
        # We need to convert Pydantic models to standard dicts for Socket.IO
        update_payload = {
            "goals": [item.model_dump() for item in state_data.goals],
            "resources": [item.model_dump() for item in state_data.resources]
        }

        print(f"[Sidecar] Emitting update for {sid}: {len(state_data.goals)} goals")

        asyncio.run_coroutine_threadsafe(
            sio.emit("goals_update", update_payload, room=sid),
            loop
        )

    except Exception as e:
        print(f"[Sidecar] Error: {e}")
        
@app.get("/service_user_list/")
async def service_user_list(current_user: UserData = Depends(get_current_user), req: Request = None):
    result = get_all_service_users(current_user.username, current_user.organization)
    
    # Log PHI access
    AuditLogger.log(
        username=current_user.username,
        user_role=current_user.role,
        action="list_patients",
        resource_type="patient_list",
        status="success",
        ip_address=req.client.host if req and req.client else None,
        details={"count": len(result)}
    )
    
    return result

@app.get("/outreach_list/")
async def outreach_list(current_user: UserData = Depends(get_current_user)):
    return get_all_outreach(current_user.username, current_user.organization)

# Update service_user_check_ins endpoint:
@app.get("/service_user_check_ins/")
async def service_user_check_ins(
    service_user_id: str = None,
    current_user: UserData = Depends(get_current_user),
    req: Request = None
):
    """Get all check-ins for a specific service user"""
    success, result = fetch_service_user_checkins(service_user_id)
    
    if success:
        # Log PHI access
        AuditLogger.log_phi_access(
            username=current_user.username,
            user_role=current_user.role,
            action="view_patient_checkins",
            patient_id=service_user_id,
            ip_address=req.client.host if req and req.client else None,
            details={"checkin_count": len(result)}
        )
        return result
    else:
        raise HTTPException(status_code=400, detail=result)

    
@app.post("/service_user_outreach_edit/")
async def service_user_outreach_edit(data: dict):
    """Handle updates to service user outreach via sidebar"""
    check_in_id = data.get('check_in_id')
    check_in_date = data.get('check_in')
    follow_up_message = data.get('follow_up_message')
    success, result = edit_service_user_outreach(check_in_id, check_in_date, follow_up_message)
    if success:
        return result 
    else:
        raise HTTPException(status_code=400, detail=result)
    

@app.post("/new_service_user/")
async def create_service_user(item: NewWellness, current_user: UserData = Depends(get_current_user), req: Request = None):
    print(f"[API] Creating service user: {item.dict()}")
    success, message = add_new_service_user(
        item.username,
        item.patientName, 
        item.lastSession, 
        item.nextCheckIn, 
        item.location,
        item.followUpMessage
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Log patient creation
    AuditLogger.log_phi_access(
        username=current_user.username,
        user_role=current_user.role,
        action="create_patient",
        patient_id=item.patientName,
        ip_address=req.client.host if req and req.client else None,
        details={"patient_name": item.patientName, "location": item.location}
    )
    
    return {"success": True, "message": message, "item": item}

class GenerateCheckInsRequest(BaseModel):
    service_user_id: str
    conversation_id: str

@app.post("/generate_check_ins/")
async def generate_check_ins_endpoint(request: GenerateCheckInsRequest):
    success, result = generate_check_ins_rule_based(request.service_user_id, request.conversation_id)
    if success:
        return {"success": True, "check_ins": result}
    else:
        raise HTTPException(status_code=400, detail=result)
    

# Handle Socket Messages

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Utility functions
def process_raw_chunk(raw_chunk: str) -> str:
    """Remove 'data:' prefix and clean chunk."""
    if raw_chunk.startswith("data:"):
        return raw_chunk[len("data: "):].replace('\n', '')
    return raw_chunk.strip()

def accumulate_chunks(generator):
    """
    Accumulates and processes streaming text chunks from a generator.
    
    Yields progressively accumulated text with proper formatting.
    """
    accumulated = ""
    for raw_chunk in generator:
        token = process_raw_chunk(raw_chunk)
        
        if token == "[DONE]":
            continue
            
        if token.startswith('#'):
            accumulated += '\n' + token
        elif token.endswith('<br/>'):
            accumulated += token + '\n'
        elif token == '<br/><br/>':
            accumulated += '<br/>'
        else:
            accumulated += token
            
        yield accumulated

# Background streaming
def _background_stream(
    sid, 
    text, 
    previous_text, 
    model, 
    organization, 
    loop, 
    metadata, 
    service_user_id,
    version,
):
    """Runs construct_response in its own OS thread."""
    accumulated_text = ""

    try:
        # Log GPT request
        scrubbed_text = PHIScrubber.scrub_for_gpt(
            text, 
            patient_id=service_user_id
        )
        
        # Also scrub conversation history
        scrubbed_history = []
        for msg in previous_text:
            if isinstance(msg, dict) and 'content' in msg:
                scrubbed_content = PHIScrubber.scrub_for_gpt(
                    msg['content'],
                    patient_id=service_user_id
                )
                scrubbed_history.append({
                    'role': msg['role'],
                    'content': scrubbed_content
                })
            else:
                scrubbed_history.append(msg)
        
        # Log what was scrubbed
        print(f"[PHI SCRUB] Original length: {len(text)}, Scrubbed length: {len(scrubbed_text)}")
        if len(text) != len(scrubbed_text):
            print("[PHI SCRUB] Scrubbed {}".format(scrubbed_text))

        # Log GPT request with scrubbed flag
        AuditLogger.log_gpt_request(
            username=metadata.get('username'),
            user_role='provider',
            patient_id=service_user_id,
            conversation_id=metadata.get('conversation_id'),
            prompt_length=len(scrubbed_text),
            response_length=0
        )
        
        # Send scrubbed content to GPT
        gen = construct_response(
            scrubbed_text,  # Use scrubbed text
            scrubbed_history,  # Use scrubbed history
            model, 
            organization,
            version,
        )
        
        for accumulated_text in accumulate_chunks(gen):
            asyncio.run_coroutine_threadsafe(
                sio.emit("generation_update", {"chunk": accumulated_text}, room=sid),
                loop
            )
            time.sleep(0.1)
        
        # Update conversation in database
        update_conversation(
            metadata,
            [
                {'role': 'user', 'content': text},
                {'role': 'system', 'content': accumulated_text}
            ],
            service_user_id
        )
        
        # Log completion
        AuditLogger.log_gpt_request(
            username=metadata.get('username'),
            user_role='provider',
            patient_id=service_user_id,
            conversation_id=metadata.get('conversation_id'),
            prompt_length=len(text),
            response_length=len(accumulated_text)
        )
        session_histories[sid].append({"role": "assistant", "content": accumulated_text})
        print("[Background] Triggering sidebar update...")
        generate_sidebar_update(session_histories[sid], sid, loop)

    except Exception as e:
        print(f"[BackgroundStream] Error: {e}")
        asyncio.run_coroutine_threadsafe(
            sio.emit(
                "generation_update",
                {"chunk": f"Sorry, something went wrong: {e}"},
                room=sid
            ),
            loop
        )

    finally:
        asyncio.run_coroutine_threadsafe(
            sio.emit(
                "generation_complete", 
                {"message": "Response generation complete."}, 
                room=sid
            ),
            loop
        )

# Socket.IO events
@sio.event
async def connect(sid, environ):
    print(f"[Socket.IO] Client connected: {sid}")
    await sio.emit("welcome", {"message": "Welcome from backend!"}, room=sid)

class FeedbackRequest(BaseModel):
    conversation_id: str
    rating: int  # 1 for helpful, 0 for not (or 1-5 scale)
    feedback_text: Optional[str] = ""

@app.post("/submit_feedback")
def submit_feedback(feedback: FeedbackRequest):
    """
    Receives feedback for a specific conversation and saves it to the DB.
    """
    if not feedback.conversation_id:
        raise HTTPException(status_code=400, detail="Conversation ID is required")

    try:
        # Use your existing connection string
        with psycopg.connect(os.environ["DATABASE_URL"],sslmode="require") as conn:
            with conn.cursor() as cur:
                
                # Optional: Verify conversation exists first
                # cur.execute("SELECT 1 FROM conversations WHERE id = %s", (feedback.conversation_id,))
                # if not cur.fetchone():
                #     raise HTTPException(status_code=404, detail="Conversation not found")

                cur.execute(
                    """
                    INSERT INTO conversation_feedback 
                    (conversation_id, rating, feedback_text)
                    VALUES (%s, %s, %s)
                    """,
                    (feedback.conversation_id, feedback.rating, feedback.feedback_text)
                )
            conn.commit()
            
        print(f"[Feedback] Saved for {feedback.conversation_id}: Rating {feedback.rating}")
        return {"success": True, "message": "Feedback received"}

    except Exception as e:
        print(f"[Feedback Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sio.event
async def disconnect(sid):
    print(f"[Socket.IO] Client disconnected: {sid}")

session_histories = {}  # global dict: sid -> list of messages

@sio.event
async def start_generation(sid, data):
    """Initiate text generation based on user input."""
    print(f"[Socket.IO] start_generation from {sid} at {time.time()}")

    if sid not in session_histories:
        session_histories[sid] = []

    # Extract request data
    text = data.get("text", "")
    model = data.get("model")
    organization = data.get("organization")
    conversation_id = data.get("conversation_id", "")
    username = data.get("username")
    service_user_id = data.get("service_user_id")
    version = data.get("version", "new")  # Default to "new" if not provided
    print(f"[Version] Using version: {version}")  # Add this line for debugging
    
    # Generate conversation ID if needed
    if not conversation_id:
        conversation_id = secrets.token_hex(16)
        await sio.emit("conversation_id", {"conversation_id": conversation_id}, room=sid)
    
    metadata = {
        'conversation_id': conversation_id,
        'username': username
    }
       
    text = data.get("text", "")
    session_histories[sid].append({"role": "user", "content": text})

    # fetch full conversation
    all_messages = session_histories[sid]

    print(f"Finished goals/resources at {time.time()}")

    # Start background streaming
    loop = asyncio.get_running_loop()
    threading.Thread(
        target=_background_stream,
        args=(
            sid, text, all_messages, model, organization, 
            loop, metadata, service_user_id, version,
        ),
        daemon=True
    ).start()

@sio.event
async def reset_session(sid, data):
    """Reset the chat session."""
    print(f"[Socket.IO] Reset session for {sid}")
    print(f"  Reason: {data.get('reason')}")
    print(f"  Previous user: {data.get('previous_service_user_id')}")
    print(f"  New user: {data.get('new_service_user_id')}")
    
    await sio.emit("reset_ack", {
        "message": "Session reset.",
        "previous_service_user_id": data.get('previous_service_user_id'),
        "new_service_user_id": data.get('new_service_user_id')
    }, room=sid)
