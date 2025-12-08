# Multi-User Forwarder System

This document explains the new multi-user architecture where each user account gets their own dedicated Telegram forwarder worker.

## Architecture Overview

### Before
- Single forwarder instance using one Telegram session
- Hardcoded admin credentials in `.env`
- All users shared the same Telegram account

### After
- **One forwarder worker per user account**
- Database-backed user authentication
- Each user has their own Telegram session(s)
- Workers automatically start/stop based on user accounts

## How It Works

### 1. User Management
Users are stored in the MySQL `users` table with:
- Unique username
- Hashed password (bcrypt)
- Relationship to their Telegram sessions

### 2. Worker System

**ForwarderManager** ([backend/forwarder_manager.py](backend/forwarder_manager.py))
- Spawns one worker per user on startup
- Listens for user creation/deletion events
- Manages worker lifecycle

**UserForwarderWorker** ([backend/user_forwarder.py](backend/user_forwarder.py))
- Dedicated to a single user
- Loads that user's Telegram session(s)
- Waits if no valid session exists
- Automatically restarts if session becomes invalid

### 3. Session Association
When a user creates a Telegram session via `/auth/start` and `/auth/confirm`:
- Session is saved to the database
- `userId` field links session to user
- Worker is notified via Redis pub/sub
- Worker picks up the new session automatically

## Setup Instructions

### 1. Update Database Schema
```bash
prisma generate
prisma db push
```

This creates:
- `users` table
- Updated `sessions` table with `user_id` foreign key

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

New dependency: `bcrypt==4.2.1`

### 3. Create Your First User
```bash
cd backend
python create_initial_user.py admin mypassword
```

Or with custom credentials:
```bash
python create_initial_user.py <username> <password>
```

### 4. Start the Application
```bash
cd backend
uvicorn main:app --reload
```

On startup, you'll see:
```
[STARTUP] Connecting to database...
[STARTUP] Database connected
[STARTUP] Starting forwarder manager...
[FORWARDER-MANAGER] Spawning worker for user admin (...)
[USER-WORKER:admin] Starting worker for user ...
[FORWARDER-MANAGER] Started with 1 workers
```

### 5. Login and Create Telegram Session

**Login to get JWT token:**
```bash
POST /auth/login
{
  "username": "admin",
  "password": "mypassword"
}

Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Start Telegram login (provide phone number):**
```bash
POST /auth/start
Authorization: Bearer <token>
{
  "phone": "+1234567890"
}

Response:
{
  "login_id": "uuid-here"
}
```

**Confirm with code from Telegram:**
```bash
POST /auth/confirm
Authorization: Bearer <token>
{
  "login_id": "uuid-here",
  "code": "12345"
}

Response:
{
  "session_id": "sess_...",
  "label": "username",
  "phone": "+1234567890",
  "enabled": true,
  "valid": true
}
```

After confirming, you'll see in the logs:
```
[USER-WORKER:admin] Starting forwarder with session sess_...
[FORWARDER] Ready to forward from X sources to Y routes
```

## Workflow

### Adding a New User

1. **Create user account:**
```bash
POST /users
Authorization: Bearer <admin-token>
{
  "username": "newuser",
  "password": "securepass"
}
```

2. **Worker automatically spawns:**
```
[FORWARDER-MANAGER] Spawning worker for user newuser
[USER-WORKER:newuser] No valid session found, waiting...
```

3. **New user logs in and creates Telegram session:**
```bash
# Login as new user
POST /auth/login
{
  "username": "newuser",
  "password": "securepass"
}

# Create Telegram session
POST /auth/start -> POST /auth/confirm
```

4. **Worker picks up session:**
```
[USER-WORKER:newuser] Starting forwarder with session sess_...
```

### When Session Becomes Invalid

If a Telegram session expires or is revoked:
```
[FORWARDER] Session not authorized; marking invalid and stopping.
[USER-WORKER:username] No valid session found, waiting...
```

The worker waits until the user creates a new session via `/auth/start` and `/auth/confirm`.

## API Endpoints

### User Management
- `POST /users` - Create new user (requires auth)
- `GET /users` - List all users (requires auth)
- `DELETE /users/{username}` - Delete user (requires auth)

### Authentication
- `POST /auth/login` - Login with username/password
- `POST /auth/start` - Start Telegram login (requires auth)
- `POST /auth/confirm` - Confirm Telegram login (requires auth)

### Routes (same as before)
- `POST /routes` - Create message route
- `GET /routes` - List routes
- `PATCH /routes/{route_id}` - Update route
- `DELETE /routes/{route_id}` - Delete route

## Benefits

1. **Multi-tenancy**: Multiple users, each with their own Telegram account
2. **Isolation**: Each worker is independent - one user's issues don't affect others
3. **Scalability**: Add users without modifying configuration
4. **Security**: Passwords hashed with bcrypt, JWT authentication
5. **Resilience**: Workers automatically restart and wait for valid sessions

## Migration from Old System

If you have existing sessions in Redis:

1. Create a user account for the legacy session
2. Associate the session with that user:
```sql
UPDATE sessions
SET user_id = '<user_id>'
WHERE session_id = 'sess_...';
```

3. Restart the application

The worker will pick up the existing session automatically.

## Monitoring

Watch the logs to see worker status:
- `[FORWARDER-MANAGER]` - Manager-level events
- `[USER-WORKER:username]` - User-specific worker events
- `[FORWARDER]` - Individual forwarder instance logs

## Troubleshooting

**Worker not starting:**
- Check that the user exists in the database
- Verify the application started successfully

**Worker waiting for session:**
- User needs to create a Telegram session via `/auth/start` and `/auth/confirm`

**Session keeps getting invalidated:**
- Telegram account may be restricted
- Phone number may be banned
- Session may have been revoked in Telegram settings

**Routes not forwarding:**
- Check worker logs for the specific user
- Verify routes are enabled
- Ensure session is valid and authorized
