# Backend changes: push notifications (Expo Push Service)

Written for the GuardGo backend, branch `pusher_integration`, FastAPI + MongoDB (odmantic/motor).
Every change below says **what** to do and **why**, so the implementer can make sensible calls
where the code differs from what is described here.

---

## 0. Background (read first)

**Goal.** When the backend saves an in-app notification (a job offer, a request change, a leave
decision...), the user's phone shows a system notification even when the GuardGo mobile app is
closed. Tapping it opens the right screen.

**What already exists and must keep working unchanged:**

- `NotificationManager.create_for_user()` in
  `backend/orion/api/interactive/notification_manager/notification_manager.py` saves a
  `NotificationRecord` and then calls `pusher_manager.publish_notification(...)`. Every other
  helper (`create_for_users`, `create_for_tenant_users`, `create_for_tenant_admin_users`,
  `create_for_platform_admin_users`) ends up calling `create_for_user`, so it is the only place
  every notification passes through.
- Pusher (`backend/orion/services/pusher_manager.py`) delivers live events to an **open** app
  or browser. It cannot reach a closed app. That is the gap push fills.

**How push is delivered.** The mobile app (Expo SDK 58, `expo-notifications`) gets an
**Expo push token** (`ExponentPushToken[xxxx]`) and sends it to the backend. To notify a
user, the backend POSTs to Expo's push API (`https://exp.host/--/api/v2/push/send`). Expo
forwards to FCM (Android) or APNs (iOS).

- **Why Expo Push and not Firebase Admin / APNs directly:** one token format and one HTTP call
  cover both platforms. The FCM and Apple credentials are stored on Expo's servers, so this
  backend holds **no Firebase or Apple secrets** and needs no new SDK. `httpx` is already in
  `requirements.txt`.

**Design rules (apply them to every change):**

1. **Push is best-effort.** Saving a notification must never fail, slow down noticeably, or
   raise because push failed. This is the same rule `pusher_manager.publish_user_event` already
   follows ("Notification persistence must succeed even if the realtime provider is down").
2. **MongoDB stays the source of truth.** A push is a doorbell. The app re-fetches real data
   through the existing API after a tap, exactly as it does for Pusher events.
3. **Do not change any existing response shape or Pusher event.** The web client and the
   mobile app already depend on them.

---

## 1. New model: `PushTokenRecord`

**File:** `backend/orion/services/mongo_manager/shared_model/db_push_token_model.py` (new)

```python
from datetime import datetime
from typing import Optional

from odmantic import Model, Field


class PushTokenRecord(Model):
    token: str = Field(unique=True)              # "ExponentPushToken[...]"
    user_id: str = Field(index=True)
    tenant_id: Optional[str] = Field(default=None, index=True)
    platform: str                                # "android" | "ios"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

**Why:**
- One row per **device**, not per user. A client or provider can be signed in on a phone and
  a tablet, and both should ring.
- `token` is unique because a token identifies one app install. If the same phone signs in as
  another user, the row must move to the new user (see §3). Otherwise the previous user's
  alerts would keep arriving on a phone they no longer use, which leaks their data.
- `last_seen_at` lets us prune stale devices and pick which ones to drop when a user has too many.

**Also add the indexes in `mongo_controller.ensure_indexes()`**
(`backend/orion/services/mongo_manager/mongo_controller.py`), next to the
`pending_arrivals_by_client` index:

```python
await self.__engine.get_collection(PushTokenRecord).create_index("token", unique=True, name="unique_push_token")
await self.__engine.get_collection(PushTokenRecord).create_index("user_id", name="push_tokens_by_user")
```

**Why:** the code already creates its important indexes explicitly there instead of relying on
odmantic. The unique index is what actually stops two concurrent registrations from creating
duplicate rows for the same token.

---

## 2. New service: `push_manager.py`

**File:** `backend/orion/services/push_manager.py` (new). Follow the shape of `pusher_manager.py`:
a small class, a module-level singleton `push_manager = PushManager()`, config read through
`env_handler`.

### 2.1 Configuration

```python
env = env_handler.get_instance()
self.enabled_flag = str(env.env("EXPO_PUSH_ENABLED", "true") or "true").strip().lower() == "true"
self.access_token = str(env.env("EXPO_ACCESS_TOKEN", "") or "").strip()
```

- `EXPO_PUSH_ENABLED` (default `true`) is a kill switch: it can turn push off in an environment,
  for example a test or staging server that should never ring real phones, without a code change.
- `EXPO_ACCESS_TOKEN` (default empty) is **optional**. When "Enhanced security for push" is
  turned on in the Expo dashboard, Expo rejects requests without
  `Authorization: Bearer <token>`. Send the header **only when the value is non-empty**, so
  local development works with no configuration.

### 2.2 Constants

```python
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
MAX_MESSAGES_PER_REQUEST = 100      # Expo hard limit per request
MAX_RECEIPT_IDS_PER_REQUEST = 1000  # Expo hard limit per receipts request
REQUEST_TIMEOUT_SECONDS = 10

# Android notification channels. MUST match the channel ids the mobile app creates.
CHANNEL_JOBS = "job-updates-v1"
CHANNEL_GENERAL = "general-v1"
```

**Why the channel ids matter:** on Android, if a push names a `channelId` the phone doesn't
have, **the notification is silently dropped**. The mobile app creates exactly these two
channels. The `-v1` suffix exists because a channel's importance can't be changed once it is on
a phone; raising it later needs a new id (`-v2`) on both sides at the same time.

### 2.3 Building a message from a saved notification

```python
def build_message(token: str, record: NotificationRecord) -> dict:
    metadata = record.metadata or {}
    is_job = (record.source_module or "") == "requests"
    return {
        "to": token,
        "title": _truncate(record.title, 120),
        "body": _truncate(record.message, 600),
        "sound": "default",
        "priority": "high" if is_job else "default",
        "channelId": CHANNEL_JOBS if is_job else CHANNEL_GENERAL,
        "data": {
            "v": "1",
            "notification_id": str(record.id),
            "source_module": record.source_module or "",
            "action_url": record.action_url or "",
            "request_id": str(metadata.get("request_id") or ""),
            "assignment_id": str(metadata.get("assignment_id") or ""),
        },
    }
```

**Why each field:**
- `data` carries exactly what the mobile app already uses to route a tapped notification
  (`notificationTarget()` in the app reads `action_url`, `metadata.request_id`,
  `metadata.assignment_id`, `source_module`), plus `notification_id` so the app can mark it
  read. Send ids only, not the whole record: Expo rejects payloads over **4096 bytes**
  (`MessageTooBig`), and the app re-fetches the full data anyway (design rule 2).
- `v: "1"` is a payload version. A later breaking change bumps it, and older app builds that
  don't recognise the version can ignore the push instead of routing wrongly.
- All `data` values are **strings**. FCM's data map only allows strings, so a number or `None`
  can fail or arrive changed.
- `priority: "high"` for job offers and request changes, which are time-sensitive (offers
  lapse). Other categories use `"default"` so Android doesn't throttle the app for overusing
  high priority.
- Truncating `title`/`body` keeps the payload under the 4 KB limit when a message is long.
  Truncate on characters and add `…`.

### 2.4 Sending

```python
async def send_for_notification(self, record: NotificationRecord) -> None
```

1. Return immediately if `not self.enabled_flag`.
2. Load the recipient's tokens: `PushTokenRecord.user_id == record.recipient_user_id`. If
   there are none, return. Most web-only users have none, and that is normal.
3. Build one message per token and send in chunks of `MAX_MESSAGES_PER_REQUEST` with
   `httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)`. Headers:
   `accept: application/json`, `accept-encoding: gzip, deflate`,
   `content-type: application/json`, plus `Authorization` when configured (§2.1).
4. On HTTP **429 or 5xx**: retry up to **3** times with exponential backoff (1s, 2s, 4s).
   Expo documents this behaviour. On other non-2xx responses, log the body and stop.
5. Read the response `data` array. **Tickets come back in the same order as the messages**,
   so `tickets[i]` belongs to `messages[i]`:
   - `status == "ok"` → store the ticket for the receipt check (§5): `ticket["id"]` + the token.
   - `status == "error"` → look at `ticket["details"]["error"]`:
     - `DeviceNotRegistered` → **delete that token** (app uninstalled or token revoked; Expo
       says stop sending to it).
     - `MessageTooBig` → log a warning with the notification id (a payload bug to fix).
     - `MessageRateExceeded` → log a warning.
     - `InvalidCredentials` / `MismatchSenderId` → log an **error**. These mean the FCM/APNs
       credentials on the Expo project are wrong. **Do not delete tokens for these**: the
       devices are fine, the configuration isn't.
6. Catch **every** exception inside this method and `logger.exception(...)` it. Never let it
   reach the caller (design rule 1).

Also add:

```python
async def delete_tokens(self, tokens: list[str]) -> None
async def delete_tokens_for_user(self, user_id: str) -> None
```

Used by the reaping above, by the revoke endpoint, and by account disabling (§6).

---

## 3. New routes: register and revoke a device

**File:** `backend/routes/push_routes.py` (new), registered in `backend/main.py` next to
`pusher_routes`:

```python
from routes.push_routes import push_routes
...
app.include_router(push_routes, include_in_schema=True)
```

Use the same router setup as `routes/pusher_routes.py`:
`APIRouter(dependencies=[Depends(status_required([UserStatus.ACTIVE]))], tags=["Push"])`
and `current_user=Depends(get_current_user)`.

**Why:** only active users should be able to register for alerts, and this matches how
`/api/notifications` and `/api/pusher/*` are already protected.

### 3.1 `POST /api/push-tokens` → `204 No Content`

Request body (Pydantic model):

```json
{ "token": "ExponentPushToken[xxxxxxxx]", "platform": "android" }
```

- Validate `token` against `^Expo(nent)?PushToken\[[^\]]+\]$`, max length 200; return **422**
  otherwise. **Why:** Expo only accepts its own token format. Rejecting garbage here keeps junk
  rows out and stops someone using the endpoint to store arbitrary strings.
- `platform` must be `"android"` or `"ios"`.
- **Upsert on `token`:**
  - Exists → set `user_id = current_user.id`, `tenant_id = current_user.tenant_uuid`, the
    platform, and `last_seen_at = now`.
  - Doesn't exist → insert.
  - **Why upsert and re-bind:** the app calls this on every launch and whenever the token
    rotates, so it must be idempotent. Re-binding handles a phone that signs in as a different
    user (see §1).
- Handle `DuplicateKeyError` from two concurrent calls with the same token by retrying the
  update once. **Why:** the app can fire this twice on start-up (launch plus token refresh).
- **Cap devices per user at 10:** after saving, if the user has more than 10 rows, delete the
  oldest by `last_seen_at`. **Why:** reinstalls create new tokens and old ones are only
  cleaned up once Expo reports them dead, so without a cap one user could pile up dozens of
  rows and get a request per dead token on every notification.

### 3.2 `POST /api/push-tokens/revoke` → `204 No Content`

Request body: `{ "token": "ExponentPushToken[...]" }`

- Delete the row **only if** `token` matches **and** `user_id == current_user.id`. Always
  return 204, even when nothing matched.
- **Why `POST .../revoke` and not `DELETE` with a body:** some HTTP clients and proxies drop
  bodies on DELETE, and putting the token in the URL would put it in access logs.
- **Why scoped to the current user:** otherwise anyone signed in could silence someone else's
  phone by sending their token.
- **Why always 204:** the app calls this while logging out and must never be held up by it.
  The app calls it **before** `/api/logout`, while its access token is still valid.

---

## 4. Hook push into `NotificationManager.create_for_user`

**File:** `backend/orion/api/interactive/notification_manager/notification_manager.py`

After the existing `await pusher_manager.publish_notification(...)` in `create_for_user`,
schedule the push **without awaiting it**:

```python
from orion.services.push_manager import push_manager

# module level
_background_tasks: set[asyncio.Task] = set()

def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
```

```python
saved_record = await self._engine.save(record)
await pusher_manager.publish_notification(...)          # unchanged
if not (saved_record.metadata or {}).get("seeded"):
    _spawn(push_manager.send_for_notification(saved_record))
return saved_record
```

**Why each part:**
- **Not awaited:** `create_for_users` loops over recipients one by one. An offer wave can
  notify many guards in one API request, and awaiting an HTTP call to Expo for each one would
  add seconds to that request. A failed push must also never fail the save (design rule 1).
- **Strong references in `_background_tasks`:** asyncio keeps only weak references to tasks,
  so a task nothing holds can be garbage-collected before it finishes. This is the pattern
  Python's docs recommend.
- **Skip `metadata.seeded`:** `_ensure_default_notification` creates the "Welcome to GuardGo"
  notification the first time a user opens their notification list. They are already in the
  app, so a push for it would just be noise.
- **Only here:** don't add push to `publish_realtime_event_to_tenant_users`, `mark_read`,
  `mark_all_read`, or the `request-updated` Pusher event. Those aren't inbox notifications.
  Pushing them would ring phones for every background data change.

Don't change `create_for_users` or the other `create_for_*` helpers. They already go through
`create_for_user`.

---

## 5. Receipt check (cleans up dead tokens)

**Why this exists:** an `"ok"` ticket from §2.4 only means Expo **accepted** the message. Whether
FCM/APNs actually delivered it is reported later in a **receipt**. That is the main place
Expo reports `DeviceNotRegistered` (app uninstalled). Without this step, dead tokens pile up
forever and every notification wastes requests on them.

### 5.1 Model

**File:** `backend/orion/services/mongo_manager/shared_model/db_push_token_model.py`
(same file as §1)

```python
class PushTicketRecord(Model):
    ticket_id: str = Field(unique=True)
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

In `ensure_indexes()`, add a TTL index so Mongo deletes tickets after 24 hours by itself:

```python
await self.__engine.get_collection(PushTicketRecord).create_index(
    "created_at", expireAfterSeconds=86400, name="push_tickets_ttl"
)
```

**Why 24h:** Expo deletes receipts after 24 hours, so an older ticket can never be checked.

### 5.2 Periodic job

Add `async def check_receipts(self) -> None` to `push_manager`:

1. Load tickets older than **15 minutes**. Expo recommends waiting about 15 minutes before
   receipts are ready.
2. POST their ids to `EXPO_RECEIPTS_URL` in chunks of `MAX_RECEIPT_IDS_PER_REQUEST`, as
   `{"ids": [...]}`.
3. For each receipt with `status == "error"` and `details.error == "DeviceNotRegistered"`,
   delete that ticket's token. Log the other error codes, using the rules in §2.4.
4. Delete every ticket you got a receipt for, success or error. Leave tickets with no receipt
   yet; the TTL index removes them after 24h.
5. Catch and log every exception.

Run it every **15 minutes** from the cron process: `backend/cronjobs.py` →
`service_manager.init_cronjobs()` in
`backend/orion/management/managers/service_manager.py`. Start it beside
`request_shift_maintenance_manager.get_instance().start()`, written in the same style as that
manager's loop. **Why the cron process:** it already exists for periodic work, and running the
check in the API process would run it once per API worker.

---

## 6. Remove tokens when an account is disabled

In every place that sets a user to `UserStatus.DISABLE` or `UserStatus.INACTIVE`, call
`await push_manager.delete_tokens_for_user(str(user.id))` after the save. Wrap the call in
try/except and log, so disabling never fails because of it. Current places:

- `backend/orion/api/interactive/account_manager/account_manager.py` (around line 329,
  `UserStatus.INACTIVE`)
- `backend/orion/api/interactive/account_manager/account_manager.py` (around line 506,
  `UserStatus.DISABLE`)
- `backend/orion/api/interactive/tenant_manager/tenant_manager.py` (around lines 633 and 649,
  `UserStatus.DISABLE` for a tenant's users)

Search for other `status = UserStatus.DISABLE` / `INACTIVE` assignments too.

**Why:** a disabled user's phone shouldn't keep receiving work alerts. The user also can't
revoke the token themselves, because `/api/push-tokens/revoke` requires an **active** user.
A re-enabled user's app re-registers on its next launch, so nothing is lost.

---

## 7. Configuration and docs

1. Wherever the backend's env templates or examples list `PUSHER_APP_ID` and the other Pusher
   keys, add:
   ```dotenv
   EXPO_PUSH_ENABLED='true'
   EXPO_ACCESS_TOKEN=''
   ```
   **Do not put real secret values in committed files.**
2. Add `docs/push-notifications-setup.md`, in the style of `docs/pusher-setup.md`. Explain:
   - push goes through Expo's push API;
   - the backend holds no Firebase or Apple keys (those are uploaded to the Expo project with
     `eas credentials`);
   - what the two env vars do;
   - the server needs **outbound HTTPS to `exp.host`**. **Why:** a firewalled Docker network
     would otherwise fail without any visible error.
3. No new dependency. Use the `httpx` already pinned in `requirements.txt`.

---

## 8. Tests

Add `backend/tests/test_push_manager.py` and `backend/tests/test_push_routes.py`, following the
style of `tests/test_notification_manager.py` (fake engines, `object.__new__`,
`@pytest.mark.anyio`). Use `httpx.MockTransport` for Expo. **Never call the real Expo API
in tests.**

Cover at least:

- `build_message`:
  - uses `job-updates-v1` + `high` for `source_module == "requests"`, and `general-v1` +
    `default` otherwise;
  - every `data` value is a `str`;
  - long text is truncated.
- 250 tokens are sent as 3 requests (100/100/50).
- An error ticket with `DeviceNotRegistered` deletes exactly that token. `InvalidCredentials`
  deletes nothing.
- 429, then 200: the request is retried and succeeds.
- An exception inside the sender doesn't propagate.
- `EXPO_PUSH_ENABLED=false` makes no HTTP call. A blank `EXPO_ACCESS_TOKEN` sends no
  `Authorization` header; a set one sends `Bearer <token>`.
- `create_for_user`:
  - still returns the saved record when push raises;
  - schedules no push for a `metadata.seeded` notification.
- `POST /api/push-tokens`:
  - inserts, then upserts the same token (one row);
  - re-binds a token to a different user;
  - rejects a malformed token with 422;
  - keeps at most 10 rows per user.
- `POST /api/push-tokens/revoke` deletes only the caller's own token and returns 204 for an
  unknown token.
- `check_receipts` deletes tokens for `DeviceNotRegistered` receipts and removes processed
  tickets.

Run the existing suite as well, to confirm `NotificationManager`, Pusher and the notification
routes still behave exactly as before.

---

## 9. Contract with the mobile app (must stay in sync)

| Item | Value |
|---|---|
| Register | `POST /api/push-tokens` `{token, platform}` → 204 |
| Revoke | `POST /api/push-tokens/revoke` `{token}` → 204 (called before `/api/logout`) |
| Android channels | `job-updates-v1` (high importance), `general-v1` (default) |
| `data` keys (all strings) | `v`, `notification_id`, `source_module`, `action_url`, `request_id`, `assignment_id` |
| Payload version | `v = "1"` |

Changing any row here needs a matching change in the mobile app (`guardgo-mobile`), or pushes
will silently stop arriving or route to the wrong screen.

## Out of scope (do not do now)

- iOS badge counts: would need an unread-count query per push.
- Per-user notification preferences or muting categories.
- Expiring lapsed offers from the tray, or "offer withdrawn" pushes.
- Batching several recipients into one Expo request in `create_for_users`. Per-recipient
  background tasks are fine at current volume.
