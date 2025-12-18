# Zoom Scheduler Bridge - Setup & Usage

## 📋 Prerequisites

- Python 3.8+
- Zoom Account with Developer credentials
- Frontend running on http://localhost:3000 (or configured URL)

## 🔑 Getting Zoom Credentials

1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/)
2. Create a new OAuth application
3. Choose **Server-to-Server OAuth** app type
4. Copy your:
   - **Client ID**
   - **Client Secret**
   - **Account ID**

## 🚀 Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file (copy from `.env.example`):
```
ZOOM_CLIENT_ID=your_client_id
ZOOM_CLIENT_SECRET=your_client_secret
ZOOM_ACCOUNT_ID=your_account_id
FRONTEND_URL=http://localhost:3000
DEBUG=True
```

### 3. Run the Application
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://127.0.0.1:8000`

## 📡 API Endpoints

### Health Check
```
GET /
```
Returns application status.

### Create Zoom Meeting
```
POST /api/zoom/create-meeting
```

**Request Body:**
```json
{
  "candidate_name": "John Doe",
  "user_email": "john@example.com",
  "start_time": "2025-12-20T10:00:00",
  "duration": 60
}
```

**Response:**
```json
{
  "join_url": "https://zoom.us/j/1234567890?pwd=abc123",
  "meeting_id": "1234567890",
  "password": "abc123",
  "start_time": "2025-12-20T10:00:00Z",
  "duration": 60,
  "topic": "Interview with John Doe"
}
```

### Check Zoom Status
```
GET /api/zoom/status
```
Verifies if Zoom credentials are configured.

## ✨ Features

✅ **Server-to-Server OAuth** - Secure Zoom authentication  
✅ **CORS Support** - Configured for frontend integration  
✅ **Request Validation** - Pydantic models for data validation  
✅ **Error Handling** - Comprehensive error management  
✅ **Environment Configuration** - python-dotenv support  
✅ **Meeting Settings** - Pre-configured for interviews (join before host, no waiting room)  

## 🧪 Testing

### Using cURL
```bash
curl -X POST http://127.0.0.1:8000/api/zoom/create-meeting \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_name": "Jane Smith",
    "user_email": "jane@example.com",
    "start_time": "2025-12-20T14:30:00",
    "duration": 45
  }'
```

### Using PowerShell
```powershell
$body = @{
    candidate_name = "Jane Smith"
    user_email = "jane@example.com"
    start_time = "2025-12-20T14:30:00"
    duration = 45
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/zoom/create-meeting" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

## 📚 Documentation

- **FastAPI Docs**: http://127.0.0.1:8000/docs (Swagger UI)
- **ReDoc Docs**: http://127.0.0.1:8000/redoc

## 🔒 Security Notes

- Never commit `.env` file with real credentials
- Keep `ZOOM_CLIENT_SECRET` confidential
- Use environment variables for all sensitive data
- CORS is restricted to configured FRONTEND_URL only

## 🐛 Troubleshooting

### 401 Unauthorized
- Verify Zoom credentials in `.env` file
- Check if Account ID is correct

### 403 Forbidden
- Ensure OAuth app has permission to create meetings
- Check Zoom account authorization

### CORS Errors
- Verify `FRONTEND_URL` matches your frontend domain
- Check browser console for exact error

## 📝 License

This project is provided as-is for educational purposes.
