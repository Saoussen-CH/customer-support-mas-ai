from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging
import os
from pathlib import Path
from typing import Optional
from .config import settings
from .models import (
    ChatRequest, ChatResponse, HealthResponse,
    RegisterRequest, LoginRequest, AuthResponse, AnonymousUserResponse,
    SessionListResponse, RenameSessionRequest, MessageHistoryResponse, MessageInfo
)
from .agent_client import agent_client
from .database import get_database
from . import auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize database
db = get_database(
    project_id=settings.google_cloud_project,
    database_id="customer-support-db"
)

app = FastAPI(
    title="Customer Support AI Backend",
    description="Backend API for Customer Support Multi-Agent System with User Management",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# AUTHENTICATION DEPENDENCY
# =============================================================================

def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Extract user_id from Authorization header.

    Returns:
        user_id if authenticated, None if anonymous
    """
    if not authorization:
        return None

    # Expected format: "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    user_id = auth.verify_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_id


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        agent_engine=settings.agent_engine_resource_name,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location
    )


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

@app.post("/api/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register a new user account."""
    try:
        # Check if email already exists
        existing_user = db.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password and create user
        password_hash = auth.hash_password(request.password)
        user_id = db.create_user(
            email=request.email,
            name=request.name,
            password_hash=password_hash
        )

        # Generate auth token
        token = auth.generate_token(user_id)

        logger.info(f"User registered: {user_id} ({request.email})")

        return AuthResponse(
            user_id=user_id,
            token=token,
            name=request.name,
            email=request.email
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login with email and password."""
    try:
        # Get user by email
        user = db.get_user_by_email(request.email)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        if not auth.verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Update last login
        db.update_last_login(user["user_id"])

        # Generate auth token
        token = auth.generate_token(user["user_id"])

        logger.info(f"User logged in: {user['user_id']} ({request.email})")

        return AuthResponse(
            user_id=user["user_id"],
            token=token,
            name=user["name"],
            email=user["email"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.post("/api/auth/anonymous", response_model=AnonymousUserResponse)
async def create_anonymous():
    """Create an anonymous user (for users who don't want to register)."""
    try:
        user_id = db.create_anonymous_user()

        return AnonymousUserResponse(
            user_id=user_id,
            is_anonymous=True
        )

    except Exception as e:
        logger.error(f"Anonymous user creation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create anonymous user")


@app.post("/api/auth/logout")
async def logout(authorization: str = Header(...)):
    """Logout (revoke token)."""
    try:
        # Extract token
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            auth.revoke_token(token)
            return {"status": "logged_out"}

        raise HTTPException(status_code=400, detail="Invalid authorization header")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")


# =============================================================================
# CHAT ENDPOINT
# =============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: Optional[str] = Depends(get_current_user),
    x_user_id: Optional[str] = Header(None)
):
    """
    Send a message to the customer support agent.

    Supports both:
    - Authenticated users (via Authorization: Bearer token header)
    - Anonymous users (via X-User-Id header with anon-* user_id)

    Args:
        request: ChatRequest with message and optional session_id
        user_id: Extracted from Authorization header (if authenticated)
        x_user_id: Extracted from X-User-Id header (if anonymous)

    Returns:
        ChatResponse with agent response, user_id, and session_id
    """
    try:
        # Determine user_id (auth takes precedence over anonymous)
        actual_user_id = user_id or x_user_id

        if not actual_user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Use Authorization header or X-User-Id for anonymous users."
            )

        logger.info(f"Chat request from user: {actual_user_id}, message: {request.message[:50]}...")

        # Check if this is a new session or existing one
        if request.session_id:
            # Verify session belongs to user
            session = db.get_session(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            if session["user_id"] != actual_user_id:
                raise HTTPException(status_code=403, detail="Session does not belong to user")

            internal_session_id = request.session_id
            agent_engine_session_id = session["agent_engine_session_id"]

            logger.info(f"Using existing session: {internal_session_id}")
        else:
            # Create new session
            internal_session_id = None
            agent_engine_session_id = None
            logger.info("Creating new session")

        # Query the agent
        response_text, agent_engine_session_id = await agent_client.query_agent(
            user_id=actual_user_id,
            agent_engine_session_id=agent_engine_session_id,
            message=request.message
        )

        # If new session, create it in database
        if not internal_session_id:
            internal_session_id = db.create_session(
                user_id=actual_user_id,
                agent_engine_session_id=agent_engine_session_id
            )
            logger.info(f"Created new session: {internal_session_id}")
        else:
            # Update existing session
            db.update_session(internal_session_id)

        # Save messages to database for UI display
        db.save_message(internal_session_id, "user", request.message)
        db.save_message(internal_session_id, "assistant", response_text)

        return ChatResponse(
            response=response_text,
            user_id=actual_user_id,
            session_id=internal_session_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


# =============================================================================
# SESSION MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(
    user_id: Optional[str] = Depends(get_current_user),
    x_user_id: Optional[str] = Header(None)
):
    """Get all sessions for the current user."""
    try:
        actual_user_id = user_id or x_user_id

        if not actual_user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        sessions = db.get_user_sessions(actual_user_id)

        from .models import SessionInfo
        session_list = [
            SessionInfo(**session) for session in sessions
        ]

        return SessionListResponse(
            user_id=actual_user_id,
            sessions=session_list
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list sessions")


@app.put("/api/sessions/{session_id}/rename")
async def rename_session(
    session_id: str,
    request: RenameSessionRequest,
    user_id: Optional[str] = Depends(get_current_user),
    x_user_id: Optional[str] = Header(None)
):
    """Rename a session."""
    try:
        actual_user_id = user_id or x_user_id

        if not actual_user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Verify session belongs to user
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != actual_user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user")

        db.rename_session(session_id, request.session_name)

        return {"status": "success", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to rename session")


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: Optional[str] = Depends(get_current_user),
    x_user_id: Optional[str] = Header(None)
):
    """Delete a session."""
    try:
        actual_user_id = user_id or x_user_id

        if not actual_user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Verify session belongs to user
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != actual_user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user")

        db.delete_session(session_id)

        return {"status": "deleted", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete session")


@app.get("/api/sessions/{session_id}/messages", response_model=MessageHistoryResponse)
async def get_session_messages(
    session_id: str,
    user_id: Optional[str] = Depends(get_current_user),
    x_user_id: Optional[str] = Header(None)
):
    """Get message history for a session."""
    try:
        actual_user_id = user_id or x_user_id

        if not actual_user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Verify session belongs to user
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != actual_user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to user")

        # Get messages
        messages = db.get_session_messages(session_id)

        message_list = [MessageInfo(**msg) for msg in messages]

        return MessageHistoryResponse(
            session_id=session_id,
            messages=message_list
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@app.get("/api")
async def api_root():
    """API root endpoint"""
    return {
        "message": "Customer Support AI Backend v2.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "auth": {
                "register": "POST /api/auth/register",
                "login": "POST /api/auth/login",
                "anonymous": "POST /api/auth/anonymous",
                "logout": "POST /api/auth/logout"
            },
            "chat": "POST /api/chat",
            "sessions": {
                "list": "GET /api/sessions",
                "rename": "PUT /api/sessions/{id}/rename",
                "delete": "DELETE /api/sessions/{id}"
            }
        }
    }


# Serve static frontend files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/")
    async def serve_frontend():
        """Serve the React frontend"""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Frontend not found. Build the frontend first."}

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve SPA - return index.html for all non-API routes"""
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not found")

        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
