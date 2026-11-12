# Pusher Channels setup

GuardGo uses Pusher Channels for live in-app notification updates. MongoDB remains the source of truth: Pusher sends a small event after the notification is saved, and the browser refreshes notification data from GuardGo's authenticated API.

## 1. Create a Pusher Channels app

1. Sign in to the Pusher dashboard and create an app under **Channels**.
2. Choose the cluster nearest your users.
3. Open **App Keys** and copy the App ID, Key, Secret, and Cluster.

## 2. Configure the backend

Put the App ID, Key, Secret, and Cluster in the environment file used by the backend. For local Docker development, copy the values into `.env.local`; for deployed environments, use the environment file or secret manager configured for that deployment.

```dotenv
PUSHER_APP_ID='your-app-id'
PUSHER_APP_KEY='your-app-key'
PUSHER_APP_SECRET='your-app-secret'
PUSHER_CLUSTER='your-cluster'
```

The secret is used only by FastAPI to publish events and sign private-channel authorization. Do not put it in Angular configuration, commit it, or expose it in browser code. The backend dependency is pinned in `backend/requirements.txt`; rebuild/restart the backend container after changing credentials.

## 3. Configure the Angular client

Edit `client/src/app/config/pusher.config.ts` and set the public **Key** and **Cluster** from the same Pusher app:

```ts
export const PUSHER_CONFIG = {
  key: 'your-app-key',
  cluster: 'your-cluster',
};
```

These values are public and are included in the browser bundle. Rebuild the Angular client and redeploy the generated build after changing them. Until both are filled in, the app skips Pusher and keeps its existing 10-second notification refresh.

## 4. How the integration is secured

- Each signed-in user subscribes to `private-user-{user_id}`.
- The authenticated `/api/pusher/channel` endpoint provides that user's channel name.
- Pusher calls `/api/pusher/auth` to authorize the subscription. GuardGo checks its existing Bearer token and rejects channels belonging to any other user.
- Notification creation publishes `notification-created` with the notification ID and source module. Marking one/all read publishes `notification-updated` or `notifications-read-all`. The browser reloads saved notification data through the existing API.
- While the private channel is connected, the notification bell, notification page, and affected request/shift/leave views refresh from Pusher events instead of polling.
- A 10-second API polling fallback runs while Pusher is unconfigured or disconnected. Reconnection triggers an immediate refresh, and MongoDB retains notifications for users who were offline.

## 5. Confirm it works

1. Start the backend and client with the same Pusher app credentials.
2. Sign in to GuardGo and open the browser console/network panel. Confirm the private channel subscription succeeds.
3. Create an event that generates an in-app notification for that account. The notification bell and unread count should update without waiting for the fallback refresh.
4. Sign in as another user and confirm that user does not receive the first user's event.
5. Temporarily disconnect/reconnect the browser and confirm the bell refreshes after the private channel is re-established.

Pusher's [Channels JavaScript guide](https://pusher.com/docs/channels/getting_started/javascript/), [private channel guide](https://pusher.com/docs/channels/using_channels/private-channels/), and [authorization guide](https://pusher.com/docs/channels/server_api/authorizing-users/) provide provider-side reference material.
