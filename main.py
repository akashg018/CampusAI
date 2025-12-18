import os
import json
import base64
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Zoom Scheduler Bridge", version="1.0.0")

# CORS Configuration
# Allow all origins for Google AI Studio Prototype compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Zoom Credentials
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")

# Zoom API endpoints
ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"

# ==================== Request Models ====================

class CreateMeetingRequest(BaseModel):
    candidate_name: str
    user_email: EmailStr
    start_time: str  # ISO 8601 format: "2025-12-20T10:00:00"
    duration: int  # Duration in minutes


class MeetingResponse(BaseModel):
    join_url: str
    meeting_id: str
    password: str
    start_time: str
    duration: int
    topic: str


# ==================== Zoom OAuth Logic ====================

def get_zoom_access_token() -> str:
    """
    Get Zoom Server-to-Server OAuth Access Token.
    
    This function uses the Zoom account credentials to authenticate
    and retrieve an access token for API calls.
    
    Returns:
        str: Access token for Zoom API
        
    Raises:
        HTTPException: If token retrieval fails
    """
    if not all([ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, ZOOM_ACCOUNT_ID]):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Zoom credentials not configured"
        )
    
    # Create authorization header (Base64 encoded client_id:client_secret)
    credentials = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    payload = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID
    }
    
    try:
        response = httpx.post(
            ZOOM_OAUTH_URL,
            headers=headers,
            data=payload,
            timeout=10.0
        )
        response.raise_for_status()
        
        token_data = response.json()
        return token_data["access_token"]
    
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Zoom access token: {str(e)}"
        )


# ==================== Zoom Meeting Creation ====================

def create_zoom_meeting(
    access_token: str,
    candidate_name: str,
    start_time: str,
    duration: int
) -> dict:
    """
    Create a scheduled Zoom meeting using the Zoom API.
    
    Args:
        access_token: Zoom OAuth access token
        candidate_name: Name of the interview candidate
        start_time: Meeting start time (ISO 8601 format)
        duration: Meeting duration in minutes
        
    Returns:
        dict: Meeting details including join_url, meeting_id, and password
        
    Raises:
        HTTPException: If meeting creation fails
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    meeting_payload = {
        "topic": f"Interview with {candidate_name}",
        "type": 2,  # Scheduled Meeting
        "start_time": start_time,
        "duration": duration,
        "settings": {
            "join_before_host": True,
            "waiting_room": False,
            "host_video": True,
            "participant_video": True
        }
    }
    
    try:
        response = httpx.post(
            f"{ZOOM_API_BASE_URL}/users/me/meetings",
            headers=headers,
            json=meeting_payload,
            timeout=10.0
        )
        response.raise_for_status()
        
        meeting_data = response.json()
        
        return {
            "join_url": meeting_data.get("join_url"),
            "meeting_id": meeting_data.get("id"),
            "password": meeting_data.get("password"),
            "start_time": meeting_data.get("start_time"),
            "duration": meeting_data.get("duration"),
            "topic": meeting_data.get("topic")
        }
    
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Zoom meeting: {str(e)}"
        )


# ==================== API Endpoints ====================

@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint"""
    return {
        "status": "OK",
        "service": "Zoom Scheduler Bridge",
        "version": "1.0.0"
    }


@app.post(
    "/api/zoom/create-meeting",
    response_model=MeetingResponse,
    tags=["Zoom"],
    summary="Create a Zoom Interview Meeting"
)
async def create_meeting(request: CreateMeetingRequest) -> MeetingResponse:
    """
    Create a scheduled Zoom meeting for a candidate interview.
    
    This endpoint:
    1. Authenticates with Zoom using Server-to-Server OAuth
    2. Creates a scheduled meeting with interview topic
    3. Returns meeting details (join URL, ID, password)
    
    Args:
        request: Meeting creation request with candidate details
        
    Returns:
        MeetingResponse: Meeting details with join URL and credentials
        
    Raises:
        HTTPException: If Zoom authentication or API call fails
    """
    try:
        # Step 1: Get Zoom access token
        access_token = get_zoom_access_token()
        
        # Step 2: Create meeting via Zoom API
        meeting_details = create_zoom_meeting(
            access_token=access_token,
            candidate_name=request.candidate_name,
            start_time=request.start_time,
            duration=request.duration
        )
        
        # Step 3: Return formatted response
        return MeetingResponse(
            join_url=meeting_details["join_url"],
            meeting_id=str(meeting_details["meeting_id"]),
            password=meeting_details["password"],
            start_time=meeting_details["start_time"],
            duration=meeting_details["duration"],
            topic=meeting_details["topic"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


# ==================== Additional Endpoints ====================

@app.get("/api/zoom/status", tags=["Zoom"])
def zoom_status():
    """Check if Zoom credentials are configured"""
    credentials_configured = all([
        ZOOM_CLIENT_ID,
        ZOOM_CLIENT_SECRET,
        ZOOM_ACCOUNT_ID
    ])
    
    return {
        "credentials_configured": credentials_configured,
        "cors_enabled": "All origins (Google AI Studio compatible)"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "False") == "True"
    )
