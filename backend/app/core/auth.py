import os
import secrets
import logging
from pathlib import Path
from typing import Optional
from fastapi import Request, HTTPException, status, Security, WebSocket
from fastapi.security import APIKeyHeader, APIKeyQuery, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger("auth")

# Global active API key holder
_active_api_key: Optional[str] = None
_is_first_run: bool = False

# Security schemes for OpenAPI / Swagger UI
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, description="API Key passed via X-API-Key header")
api_key_query_scheme = APIKeyQuery(name="api_key", auto_error=False, description="API Key passed via api_key query parameter")
http_bearer_scheme = HTTPBearer(auto_error=False, description="API Key passed via Authorization: Bearer header")


def get_key_file_path() -> Path:
    """
    Returns the resolved Path for the persistent API key file.
    Default: .api_key in backend root directory.
    """
    custom_path = Path(settings.API_KEY_FILE_PATH)
    if custom_path.is_absolute():
        return custom_path
    
    # Resolve relative to backend root (parent of app/)
    backend_root = Path(__file__).resolve().parent.parent.parent
    return backend_root / custom_path


def init_api_key() -> Optional[str]:
    """
    Initializes the backend API key on startup.
    
    1. If settings.API_KEY is configured (via environment variable or .env), use it.
    2. If a persisted .api_key file exists, load it (subsequent run - no printing).
    3. If neither exists, generate a cryptographically secure key, persist it to .api_key,
       and print the key once to the console with a prominent banner (first run).
    """
    global _active_api_key, _is_first_run

    if not settings.API_KEY_AUTH_ENABLED:
        logger.warning("⚠️ API Key Authentication is DISABLED (API_KEY_AUTH_ENABLED=False).")
        _active_api_key = None
        _is_first_run = False
        return None

    # 1. Check if configured in environment / .env
    env_key = settings.API_KEY
    if env_key and env_key.strip() and not env_key.strip().startswith("your_"):
        _active_api_key = env_key.strip()
        _is_first_run = False
        logger.info("🔒 API Key Authentication: ACTIVE (pre-configured via environment).")
        return _active_api_key

    # 2. Check if persisted key file exists
    key_file = get_key_file_path()
    if not key_file.exists():
        # Fallback check for legacy root .api_key
        legacy_file = Path(__file__).resolve().parent.parent.parent / ".api_key"
        if legacy_file.exists():
            key_file = legacy_file

    if key_file.exists():
        try:
            saved_key = key_file.read_text(encoding="utf-8").strip()
            if saved_key:
                _active_api_key = saved_key
                _is_first_run = False
                logger.info(f"🔒 API Key Authentication: ACTIVE (loaded from {key_file.name}).")
                return _active_api_key
        except Exception as e:
            logger.error(f"❌ Failed to read existing API key file '{key_file}': {e}")

    # 3. First run: Generate a secure new key and persist it
    new_key = f"jarvis_sec_{secrets.token_urlsafe(32)}"
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        # Write key to file
        key_file.write_text(new_key, encoding="utf-8")
        # Restrict permissions to owner read/write only (POSIX)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass  # May not apply on certain non-POSIX filesystems
        
        _active_api_key = new_key
        _is_first_run = True

        print_first_run_key_banner(new_key, str(key_file))
        logger.info(f"🔒 API Key Authentication: ACTIVE (newly generated and saved to {key_file.name}).")
        return _active_api_key

    except Exception as e:
        logger.error(f"❌ Failed to persist generated API key to '{key_file}': {e}")
        _active_api_key = new_key
        _is_first_run = True
        print_first_run_key_banner(new_key, str(key_file))
        return _active_api_key


def print_first_run_key_banner(api_key: str, file_path: str):
    """
    Prints a prominent, formatted banner displaying the generated API key on first run.
    """
    banner = f"""
================================================================================
🔑 J.A.R.V.I.S. API KEY GENERATED (FIRST RUN)
================================================================================
A secure API key has been automatically generated for this Jarvis backend:

  API_KEY: {api_key}

Saved to: {file_path}

⚠️  IMPORTANT:
   - This key will NOT be printed again on subsequent runs.
   - Please keep this key safe.
   - You can provide this key to API clients using any of the following:
       • Header:        X-API-Key: {api_key}
       • Authorization: Bearer {api_key}
       • Query Param:   ?api_key={api_key}
================================================================================
"""
    # Print directly to standard output so it is immediately visible on console
    print(banner, flush=True)


def get_active_api_key() -> Optional[str]:
    """
    Returns the currently active API key.
    """
    global _active_api_key
    if _active_api_key is None and settings.API_KEY_AUTH_ENABLED:
        init_api_key()
    return _active_api_key


def is_valid_api_key(provided_key: Optional[str]) -> bool:
    """
    Validates a provided key against the active API key using constant-time comparison.
    """
    if not settings.API_KEY_AUTH_ENABLED:
        return True
    
    active_key = get_active_api_key()
    if not active_key or not provided_key:
        return False
    
    return secrets.compare_digest(provided_key.strip(), active_key.strip())


def extract_api_key_from_request(request: Request) -> Optional[str]:
    """
    Extracts API key from a request checking:
    1. X-API-Key header
    2. Authorization: Bearer <key>
    3. api_key or token query parameter
    """
    # 1. Check X-API-Key header
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key.strip()
    
    # 2. Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        elif len(parts) == 1:
            return parts[0].strip()

    # 3. Check query parameters
    query_key = request.query_params.get("api_key") or request.query_params.get("token")
    if query_key:
        return query_key.strip()

    return None


async def get_api_key(
    header_key: Optional[str] = Security(api_key_header_scheme),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(http_bearer_scheme),
    query_key: Optional[str] = Security(api_key_query_scheme),
) -> str:
    """
    FastAPI security dependency for OpenAPI Swagger documentation and endpoint protection.
    """
    if not settings.API_KEY_AUTH_ENABLED:
        return ""

    key_candidate = (
        header_key
        or (bearer_creds.credentials if bearer_creds else None)
        or query_key
    )

    if is_valid_api_key(key_candidate):
        return key_candidate or ""

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_ws_auth(websocket: WebSocket, query_api_key: Optional[str] = None) -> bool:
    """
    Authenticates an incoming WebSocket connection before handshake completion.
    Checks query parameter (?api_key=... or ?token=...) and headers.
    """
    if not settings.API_KEY_AUTH_ENABLED:
        return True

    # Check explicitly passed query_api_key or websocket.query_params
    candidate = (
        query_api_key
        or websocket.query_params.get("api_key")
        or websocket.query_params.get("token")
        or websocket.headers.get("X-API-Key")
    )

    # Check Authorization header on websocket
    if not candidate:
        auth_header = websocket.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                candidate = parts[1]
            elif len(parts) == 1:
                candidate = parts[0]

    if is_valid_api_key(candidate):
        return True

    logger.warning("🚫 Rejected unauthenticated WebSocket connection attempt.")
    return False


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces API key authentication on all HTTP endpoints starting with /api/.
    Non-API endpoints (such as /docs, /redoc, /openapi.json, /) are allowed without authentication.
    """
    def __init__(self, app, exempt_paths: Optional[list[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or ["/docs", "/redoc", "/openapi.json", "/favicon.ico", "/api/health"]

    async def dispatch(self, request: Request, call_next):
        # If authentication is disabled globally, pass through
        if not settings.API_KEY_AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path

        # Allow CORS pre-flight OPTIONS requests to pass through untouched
        if request.method == "OPTIONS":
            return await call_next(request)

        # Allow exempt documentation paths
        if any(path == exempt or path.startswith(f"{exempt}/") for exempt in self.exempt_paths):
            return await call_next(request)

        # Enforce on all /api/* routes
        if path.startswith("/api"):
            # Check for WebSocket upgrade requests (handled in WebSocket endpoint handler)
            if request.headers.get("upgrade", "").lower() == "websocket":
                return await call_next(request)

            provided_key = extract_api_key_from_request(request)
            if not is_valid_api_key(provided_key):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing API key"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return await call_next(request)
