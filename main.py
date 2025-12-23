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


class SchedulerBookingRequest(BaseModel):
    """Request model for Zoom Scheduler booking with email trigger"""
    schedule_id: str  # Zoom Scheduler schedule ID
    start_time: str  # ISO 8601 format: "2025-02-01T10:00:00Z"
    user_email: EmailStr  # User's email address
    first_name: str  # User's first name
    last_name: str  # User's last name


class SchedulerBookingResponse(BaseModel):
    """Response model for Zoom Scheduler booking"""
    booking_id: str
    email_sent: bool
    meeting_link: str
    scheduled_time: str
    status: str
    invitee_email: str


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


def create_scheduler_booking(
    access_token: str,
    schedule_id: str,
    start_time: str,
    user_email: str,
    first_name: str,
    last_name: str
) -> dict:
    """
    Create a booking in Zoom Scheduler which triggers email notification.
    
    This function calls the Zoom Scheduler API endpoint to create a booking.
    When the booking is created, Zoom automatically:
    - Creates the meeting
    - Generates the join link
    - Sends confirmation email to the invitee with calendar invite
    
    Args:
        access_token: Zoom OAuth access token
        schedule_id: Zoom Scheduler schedule ID
        start_time: Meeting start time (ISO 8601 format: "2025-02-01T10:00:00Z")
        user_email: Invitee's email address
        first_name: Invitee's first name
        last_name: Invitee's last name
        
    Returns:
        dict: Booking details including booking_id, meeting_link, and status
        
    Raises:
        HTTPException: If booking creation fails
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Construct the payload according to Zoom Scheduler API specification
    booking_payload = {
        "start_time": start_time,
        "invitee": {
            "email": user_email,
            "first_name": first_name,
            "last_name": last_name
        }
    }
    
    try:
        response = httpx.post(
            f"{ZOOM_API_BASE_URL}/scheduler/schedules/{schedule_id}/bookings",
            headers=headers,
            json=booking_payload,
            timeout=10.0
        )
        response.raise_for_status()
        
        booking_data = response.json()
        
        return {
            "booking_id": booking_data.get("id"),
            "email_sent": True,  # Zoom sends email automatically when booking is created
            "meeting_link": booking_data.get("join_url", ""),
            "scheduled_time": booking_data.get("start_time"),
            "status": booking_data.get("status", "created"),
            "invitee_email": user_email
        }
    
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Zoom Scheduler booking: {str(e)}"
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


@app.post(
    "/api/zoom/scheduler/book",
    response_model=SchedulerBookingResponse,
    tags=["Zoom Scheduler"],
    summary="Book a Zoom Scheduler Meeting (Triggers Email)"
)
async def book_scheduler_meeting(request: SchedulerBookingRequest) -> SchedulerBookingResponse:
    """
    Create a booking in Zoom Scheduler and trigger email notification.
    
    🔥 This endpoint triggers automatic email sending:
    - When booking is created, Zoom internally creates the meeting
    - Zoom generates the join link automatically
    - 📧 Zoom sends confirmation email to invitee automatically
    - 📅 Calendar invite is attached to the email
    
    This is ideal for integrating with Google AI Studio where users enter their email addresses.
    
    Endpoint Flow:
    1. User submits email via Google AI Studio
    2. Backend calls this endpoint with user's email details
    3. Zoom creates booking and sends email automatically
    
    Args:
        request: SchedulerBookingRequest containing:
            - schedule_id: Zoom Scheduler schedule ID
            - start_time: Meeting start time (ISO 8601: "2025-02-01T10:00:00Z")
            - user_email: User's email address
            - first_name: User's first name
            - last_name: User's last name
        
    Returns:
        SchedulerBookingResponse: Booking confirmation with email status
        
    Raises:
        HTTPException: If Zoom authentication or booking creation fails
    """
    try:
        # Step 1: Get Zoom access token
        access_token = get_zoom_access_token()
        
        # Step 2: Create booking via Zoom Scheduler API (triggers email)
        booking_details = create_scheduler_booking(
            access_token=access_token,
            schedule_id=request.schedule_id,
            start_time=request.start_time,
            user_email=request.user_email,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        # Step 3: Return confirmation response
        return SchedulerBookingResponse(
            booking_id=booking_details["booking_id"],
            email_sent=booking_details["email_sent"],
            meeting_link=booking_details["meeting_link"],
            scheduled_time=booking_details["scheduled_time"],
            status=booking_details["status"],
            invitee_email=booking_details["invitee_email"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error creating Scheduler booking: {str(e)}"
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
