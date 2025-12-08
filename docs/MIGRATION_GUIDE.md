# Migration Guide: Redis to MySQL with Prisma

This guide walks you through migrating your session and route data from Redis to MySQL using Prisma ORM.

## Prerequisites

- MySQL server running (local or remote)
- Python 3.13+ environment
- Access to your existing Redis instance

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `prisma==0.15.0` along with other dependencies.

## Step 2: Configure Database Connection

Update your `.env` file with your MySQL database connection string:

```env
DATABASE_URL=mysql://username:password@host:port/database_name
```

Example:
```env
DATABASE_URL=mysql://root:mypassword@localhost:3306/telegram_forwarder
```

## Step 3: Generate Prisma Client

Generate the Prisma Python client from the schema:

```bash
prisma generate
```

## Step 4: Create the Database

If the database doesn't exist yet, create it:

```bash
mysql -u root -p -e "CREATE DATABASE telegram_forwarder CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## Step 5: Run Database Migrations

Push the Prisma schema to your MySQL database:

```bash
prisma db push
```

This will create the following tables:
- `sessions` - Stores Telegram session data
- `routes` - Stores message routing rules
- `default_session` - Stores the default session configuration

## Step 6: Migrate Existing Data from Redis (Optional)

If you have existing data in Redis that you want to migrate to MySQL, create a migration script:

```python
# migrate_redis_to_mysql.py
import asyncio
from database import connect_db, disconnect_db, create_session, create_route, set_default_session
from shared.redis_client import redis_scan_json, redis_get_json

async def migrate_sessions():
    """Migrate all sessions from Redis to MySQL"""
    print("Migrating sessions...")
    sessions = await redis_scan_json("tg:session:sess_*")

    for session_data in sessions:
        try:
            await create_session(
                session_id=session_data["session_id"],
                session_str=session_data["session_str"],
                label=session_data.get("label", ""),
                phone=session_data.get("phone", ""),
                enabled=session_data.get("enabled", True),
                valid=session_data.get("valid", True)
            )
            print(f"✓ Migrated session: {session_data['session_id']}")
        except Exception as e:
            print(f"✗ Error migrating session {session_data['session_id']}: {e}")

async def migrate_routes():
    """Migrate all routes from Redis to MySQL"""
    print("Migrating routes...")
    routes = await redis_scan_json("tg:route:route_*")

    for route_data in routes:
        try:
            await create_route(
                route_id=route_data["route_id"],
                source_chat=str(route_data["source_chat"]),
                target_chat=str(route_data["target_chat"]),
                transform_type=route_data.get("transform_type", "solana_ca"),
                enabled=route_data.get("enabled", True)
            )
            print(f"✓ Migrated route: {route_data['route_id']}")
        except Exception as e:
            print(f"✗ Error migrating route {route_data['route_id']}: {e}")

async def migrate_default_session():
    """Migrate default session from Redis to MySQL"""
    print("Migrating default session...")
    default = await redis_get_json("tg:session:default")

    if default and "session_id" in default:
        try:
            await set_default_session(default["session_id"])
            print(f"✓ Set default session: {default['session_id']}")
        except Exception as e:
            print(f"✗ Error setting default session: {e}")

async def main():
    await connect_db()

    await migrate_sessions()
    await migrate_routes()
    await migrate_default_session()

    await disconnect_db()
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

Run the migration:

```bash
cd backend
python migrate_redis_to_mysql.py
```

## Step 7: Start the Application

Start your FastAPI application:

```bash
cd backend
uvicorn main:app --reload
```

The application will:
1. Connect to MySQL on startup
2. Use MySQL for all session and route operations
3. Still use Redis for locking and pub/sub operations
4. Disconnect from MySQL gracefully on shutdown

## What Changed

### Session Storage
- **Before**: Sessions stored in Redis with keys like `tg:session:{session_id}`
- **After**: Sessions stored in MySQL `sessions` table with proper schema

### Route Storage
- **Before**: Routes stored in Redis with keys like `tg:route:{route_id}`
- **After**: Routes stored in MySQL `routes` table with proper schema

### What Still Uses Redis
- Session locking (`acquire_session_lock`, `release_session_lock`)
- Pub/sub notifications (`notify_forwarder_reload`)

## Troubleshooting

### "Table doesn't exist" error
Run `prisma db push` to create the tables.

### Connection errors
Verify your `DATABASE_URL` in `.env` is correct and the MySQL server is running.

### Import errors
Make sure you've run `prisma generate` after installing the prisma package.

## Schema Reference

The Prisma schema ([schema.prisma](schema.prisma)) defines three models:

1. **Session**: Stores Telegram session data with versioning, health tracking, and error logging
2. **Route**: Stores message forwarding routes with source/target chat configuration
3. **DefaultSession**: Stores which session should be used as default

All timestamps (`createdAt`, `updatedAt`, `lastChecked`, `lastActivity`) are automatically managed by Prisma.
