# Redis Removal Plan

This document outlines the steps to completely remove Redis and use only MySQL/Prisma for all data storage.

## Current Redis Usage

1. **Session Storage** - `tg:session:{session_id}` ✅ Migrated to MySQL
2. **Login Sessions** - `tg:login:{login_id}` ✅ Migrated to MySQL (`LoginSession` model)
3. **Default Session** - `tg:session:default` ❌ Removed (no longer needed in multi-user system)
4. **Routes** - `tg:route:{route_id}` ✅ Already using MySQL
5. **Pub/Sub** - Used for notifying forwarders of changes ❌ Needs replacement
6. **Session Locking** - `tg:session:lock:{session_id}` ❌ Needs database replacement

## Replacement Strategy

### 1. Remove Pub/Sub (forwarder notifications)
**Current:** Redis pub/sub channels (`forwarder:reload`, `forwarder:control`, `forwarder:user`)
**Replacement:** Database polling with version numbers

**Implementation:**
- Add `version` field to Routes table (already exists in Sessions)
- Workers poll database periodically for version changes
- Increment version on route/session changes
- Workers detect version changes and reload

### 2. Replace Session Locking
**Current:** Redis SET with NX/EX for distributed locks
**Replacement:** MySQL row-level locking or separate `SessionLock` table

**Implementation Option A - Row Locking:**
```sql
SELECT * FROM sessions WHERE session_id = ? FOR UPDATE
```

**Implementation Option B - Lock Table:**
```prisma
model SessionLock {
  sessionId String   @id
  lockId    String
  expiresAt DateTime
}
```

### 3. Clean Up Files
Remove or update these files:
- `backend/shared/redis_client.py` - Delete
- `backend/shared/pubsub.py` - Delete or replace with polling
- `backend/session_manager.py` - Remove Redis imports, use database locking
- `backend/enhanced_forwarder.py` - Remove Redis, use database polling
- `backend/routes/auth.py` - Remove `redis_get_json` usage

## Migration Steps

### Step 1: Update Session Manager ✅ DONE
- [x] Remove Redis imports
- [x] Use database for session CRUD
- [x] Implement database-based locking

### Step 2: Update Forwarder ⏳ IN PROGRESS
- [ ] Remove Redis pub/sub listener
- [ ] Add database polling for route/session changes
- [ ] Use database for loading routes
- [ ] Remove Redis from `enhanced_forwarder.py`

### Step 3: Update Auth Routes
- [ ] Remove `redis_get_json` usage in `/auth/session`
- [ ] Use database to get sessions

### Step 4: Remove Redis Files
- [ ] Delete `backend/shared/redis_client.py`
- [ ] Delete `backend/shared/pubsub.py`
- [ ] Remove `redis` from `requirements.txt`
- [ ] Remove `REDIS_URL` from `config.py` and `.env`

### Step 5: Update Main App
- [ ] Remove Redis test endpoint
- [ ] Verify no Redis imports remain

### Step 6: Documentation
- [ ] Update MIGRATION_GUIDE.md
- [ ] Update MULTI_USER_SETUP.md
- [ ] Add database polling explanation

## Database Polling Implementation

```python
class ConfigurationWatcher:
    """Watches for configuration changes in the database."""

    def __init__(self):
        self.last_route_version = 0
        self.last_session_check = datetime.now()

    async def check_for_updates(self) -> dict:
        """Check if routes or sessions have changed."""
        # Get latest route update timestamp
        latest_route = await db.route.find_first(
            order={"updatedAt": "desc"}
        )

        # Check if any sessions were updated
        sessions_updated = await db.session.find_many(
            where={"updatedAt": {"gt": self.last_session_check}}
        )

        changes = {
            "routes_changed": latest_route and latest_route.updatedAt > self.last_check,
            "sessions_changed": len(sessions_updated) > 0
        }

        self.last_session_check = datetime.now()
        return changes
```

## Benefits of Removing Redis

1. **Simplified Architecture** - One database instead of two
2. **Reduced Dependencies** - No Redis server required
3. **Easier Deployment** - Only need MySQL
4. **ACID Guarantees** - Database transactions for consistency
5. **Simpler Backup** - Single database to backup
6. **Lower Costs** - One less service to run/manage

## Trade-offs

1. **Performance** - Database polling slower than pub/sub (but good enough for this use case)
2. **Polling Overhead** - Periodic database queries (mitigated by reasonable intervals)
3. **Lock Performance** - MySQL locks slightly slower than Redis (negligible for this scale)

## Timeline

- **Phase 1** (Current): Session/Route storage migrated ✅
- **Phase 2** (Next): Remove pub/sub, implement polling
- **Phase 3** (Final): Remove all Redis dependencies, cleanup

## Testing Checklist

After Redis removal:
- [ ] User can create account
- [ ] User can login
- [ ] User can create Telegram session
- [ ] Forwarder starts for each user
- [ ] Routes can be created/updated/deleted
- [ ] Forwarder picks up route changes
- [ ] Session invalidation works
- [ ] Multiple users work independently
- [ ] Worker restarts on session changes
