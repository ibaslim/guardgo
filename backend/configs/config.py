from orion.helper_manager.env_handler import env_handler


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _normalize_origin(value: str | None) -> str | None:
    candidate = (value or "").strip()
    if not candidate:
        return None
    if candidate.startswith(("http://", "https://")):
        return candidate.rstrip("/")
    return f"https://{candidate.rstrip('/')}"


DEBUG = env_handler.get_instance().env("PRODUCTION", "0") != "1"
PRODUCTION_DOMAIN = env_handler.get_instance().env("PRODUCTION_DOMAIN", "-")
APP_URL = env_handler.get_instance().env("APP_URL", "http://localhost:8080").rstrip("/")
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SAMESITE = 'lax'
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if not DEBUG else None
if DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost',
        'http://127.0.0.1',
        'http://localhost:3000',
        'http://localhost:8080',
        'http://127.0.0.1:8080',
        'http://0.0.0.0:8070',
    ]
    ALLOWED_CORS_ORIGINS = list(CSRF_TRUSTED_ORIGINS)
    TRUSTED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
else:
    TRUSTED_HOSTS = _split_csv(PRODUCTION_DOMAIN)
    configured_origins = _split_csv(env_handler.get_instance().env("ALLOWED_CORS_ORIGINS", ""))
    origin_candidates = configured_origins or [APP_URL] + TRUSTED_HOSTS
    ALLOWED_CORS_ORIGINS = [
        origin for origin in (_normalize_origin(candidate) for candidate in origin_candidates) if origin
    ]
    CSRF_TRUSTED_ORIGINS = list(ALLOWED_CORS_ORIGINS)

# Google Maps integration toggles (used by request matching/geocoding features).
GOOGLE_MAPS_API_KEY = env_handler.get_instance().env("GOOGLE_MAPS_API_KEY", "")
GOOGLE_MAPS_MAP_ID = env_handler.get_instance().env("GOOGLE_MAPS_MAP_ID", "")
GOOGLE_MAPS_COUNTRY_RESTRICTION = env_handler.get_instance().env("GOOGLE_MAPS_COUNTRY_RESTRICTION", "ca")
GOOGLE_MAPS_GEOCODING_ENABLED = env_handler.get_instance().env("GOOGLE_MAPS_GEOCODING_ENABLED", "0") == "1"
GOOGLE_MAPS_DISTANCE_MATRIX_ENABLED = env_handler.get_instance().env("GOOGLE_MAPS_DISTANCE_MATRIX_ENABLED", "0") == "1"
