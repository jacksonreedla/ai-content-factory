# infra/youtube/oauth.py
"""YouTube OAuth helpers. Lazy-imports google libs so the app runs without them."""
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class MissingYouTubeDeps(RuntimeError):
    """Raised when google-api-python-client / google-auth aren't installed."""


def _deps():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa
        from google.auth.transport.requests import Request  # noqa
        from google.oauth2.credentials import Credentials  # noqa
        import googleapiclient.http  # noqa
    except ImportError as e:
        raise MissingYouTubeDeps(
            "YouTube deps missing; pip install google-api-python-client "
            "google-auth-oauthlib google-auth-httplib2"
        ) from e


def run_oauth_flow(client_secrets_path: Path, token_path: Path,
                   port: int = 0) -> "object":
    """Run the OAuth flow once, persisting a token to `token_path`."""
    _deps()
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
    creds = flow.run_local_server(port=port)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    return creds


def load_credentials(token_path: Path, client_secrets_path: Optional[Path] = None,
                     port: int = 0):
    """Load credentials, refreshing or running the flow as needed."""
    _deps()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    if not creds or not creds.valid:
        if client_secrets_path is None or not client_secrets_path.exists():
            return None
        creds = run_oauth_flow(client_secrets_path, token_path, port=port)
    return creds
