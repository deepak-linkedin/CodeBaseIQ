import os

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def auth_is_enabled() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID", "").strip()) or os.getenv("AUTH_REQUIRED", "false").lower() == "true"


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """
    Verify Google ID tokens for deployed use. If GOOGLE_CLIENT_ID is unset,
    the API runs in local-development mode with one local user.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        if os.getenv("AUTH_REQUIRED", "false").lower() == "true":
            raise HTTPException(status_code=503, detail="Authentication is required but GOOGLE_CLIENT_ID is not configured.")
        return "local-dev"

    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Sign in with Google to continue.")

    try:
        response = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credentials.credentials},
            timeout=5.0,
        )
        response.raise_for_status()
        claims = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Google sign-in token is invalid or expired.") from exc

    if claims.get("aud") != client_id or claims.get("email_verified") not in ("true", True):
        raise HTTPException(status_code=401, detail="Google sign-in token could not be verified.")

    subject = claims.get("sub")
    if not subject:
        raise HTTPException(status_code=401, detail="Google account identity is missing.")
    return str(subject)
