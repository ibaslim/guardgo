import logging

from pusher import Pusher
from starlette.concurrency import run_in_threadpool

from orion.helper_manager.env_handler import env_handler


logger = logging.getLogger(__name__)


class PusherManager:
    """Small wrapper for Pusher Channels publishing and private-channel auth."""

    def __init__(self):
        env = env_handler.get_instance()
        self.app_id = str(env.env("PUSHER_APP_ID", "") or "").strip()
        self.key = str(env.env("PUSHER_APP_KEY", "") or "").strip()
        self.secret = str(env.env("PUSHER_APP_SECRET", "") or "").strip()
        self.cluster = str(env.env("PUSHER_CLUSTER", "") or "").strip()
        self._client = None

    @property
    def enabled(self) -> bool:
        return all((self.app_id, self.key, self.secret, self.cluster))

    def _get_client(self):
        if not self.enabled:
            return None
        if self._client is None:
            self._client = Pusher(
                app_id=self.app_id,
                key=self.key,
                secret=self.secret,
                cluster=self.cluster,
                ssl=True,
                timeout=5,
            )
        return self._client

    async def publish_user_event(
        self,
        recipient_user_id: str,
        event_name: str,
        payload: dict,
    ) -> None:
        client = self._get_client()
        if client is None:
            return

        try:
            await run_in_threadpool(
                client.trigger,
                f"private-user-{recipient_user_id}",
                event_name,
                payload,
            )
        except Exception:
            # Notification persistence must succeed even if the realtime provider is down.
            logger.exception("Could not publish notification event through Pusher")

    async def publish_notification(
        self,
        recipient_user_id: str,
        notification_id: str,
        source_module: str | None = None,
    ) -> None:
        await self.publish_user_event(
            recipient_user_id,
            "notification-created",
            {"id": str(notification_id), "source_module": source_module},
        )

    async def authenticate_channel(self, channel_name: str, socket_id: str) -> dict:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Pusher is not configured")
        return await run_in_threadpool(client.authenticate, channel_name, socket_id)


pusher_manager = PusherManager()
