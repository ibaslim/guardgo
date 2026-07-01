from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from configs import config
from orion.middleware.middlewares.cache_admin import cache_admin
from orion.middleware.middlewares.content_block_middleware import content_block_middleware
from orion.middleware.middlewares.content_security_policy_middleware import content_security_policy_middleware
from orion.middleware.middlewares.security_headers_middleware import security_headers_middleware
from orion.middleware.middlewares.service_ready_middleware import service_ready_middleware


def setup_middlewares(app):
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    app.add_middleware(content_security_policy_middleware)
    app.add_middleware(service_ready_middleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"])

    if not config.DEBUG and config.TRUSTED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS)

    app.add_middleware(security_headers_middleware)
    app.add_middleware(content_block_middleware)
    app.add_middleware(cache_admin)
