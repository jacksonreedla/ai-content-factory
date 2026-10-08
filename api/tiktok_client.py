"""TikTok Content Posting API client: OAuth (Login Kit), direct post upload.

Setup (one time, free but requires app approval):
  1. developers.tiktok.com -> Manage apps -> create an app
  2. Add the "Login Kit" and "Content Posting API" products
  3. Enable "Direct Post" under the Content Posting API config
  4. Request/receive the scopes: user.info.basic, video.publish
  5. Add a redirect URI of  http://localhost:53682/callback  (must match
     tiktok.redirect_uri in config exactly)
  6. Copy the Client Key and Client Secret into Settings -> config.json
     under "tiktok", then click "Connect TikTok" on the Uploads page.

Notes on TikTok's rules (important for expectations):
  * Until your app passes TikTok's content-posting audit, every post is
    forced to private (SELF_ONLY) no matter what privacy level you request.
  * `video.publish` is rate limited to 6 init requests per minute per user.
  * The uploaded file is fetched/processed asynchronously; we poll the
    status endpoint until TikTok reports the post as published or failed.

The ``requests`` library is imported lazily so the rest of the app runs
without it, mirroring youtube_client's lazy-import approach.
"""
from __future__ import annotations

import http.server
import logging
import secrets
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

from app.config import Config
from app.paths import DATA_DIR

log = logging.getLogger("acf.tiktok")

AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
VIDEO_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

DEFAULT_SCOPES = "user.info.basic,video.publish"
DEFAULT_TOKEN = DATA_DIR / "tiktok_token.json"

# 5 MiB chunks. TikTok requires each chunk (except the last) to be between
# 5 MB and 64 MB, and the whole upload to be at most 1000 chunks.
CHUNK_SIZE = 5 * 1024 * 1024

# Map the app's generic visibility words to TikTok privacy levels.
VISIBILITY_TO_PRIVACY = {
    "public": "PUBLIC_TO_EVERYONE",
    "unlisted": "SELF_ONLY",      # TikTok has no "unlisted"; keep it private
    "private": "SELF_ONLY",
    "scheduled": "SELF_ONLY",     # direct-post has no schedule; treat as private
    "friends": "MUTUAL_FOLLOW_FRIENDS",
    "followers": "FOLLOWER_OF_CREATOR",
}

SETUP_HELP = (
    "TikTok is not connected. One-time setup: create an app at "
    "developers.tiktok.com, add the Login Kit + Content Posting API products, "
    "enable Direct Post, and register the redirect URI "
    "http://localhost:53682/callback. Put the Client Key and Client Secret in "
    "Settings -> config.json under 'tiktok', then click 'Connect TikTok' on "
    "the Uploads page. Full steps are in docs/tiktok_api_request.md."
)


class TikTokError(RuntimeError):
    pass


def _requests():
    try:
        import requests
        return requests
    except ImportError as exc:  # pragma: no cover - requests is a hard dep
        raise TikTokError(
            "The 'requests' library is required for TikTok uploads. "
            "Run: pip install requests") from exc


class _OAuthCatcher(http.server.BaseHTTPRequestHandler):
    """Single-request handler that captures the ?code=... redirect."""

    code: str | None = None
    state: str | None = None
    expected_state: str | None = None

    def do_GET(self):  # noqa: N802 (http.server API)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _OAuthCatcher.code = (params.get("code") or [None])[0]
        _OAuthCatcher.state = (params.get("state") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = (_OAuthCatcher.code and
              _OAuthCatcher.state == _OAuthCatcher.expected_state)
        body = ("<h2>TikTok connected - you can close this tab.</h2>" if ok
                else "<h2>Authorization failed. Check the app logs.</h2>")
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *_args):  # silence the default stderr logging
        return


class TikTokClient:
    def __init__(self, config: Config | None = None,
                 token_path: Path = DEFAULT_TOKEN):
        self.config = config
        self.token_path = Path(token_path)
        self._creator_info: dict | None = None

    # -------------------------------------------------------------- config
    def _cfg(self, key: str, default=None):
        if self.config is None:
            return default
        return self.config.get(f"tiktok.{key}", default)

    @property
    def client_key(self) -> str:
        return (self._cfg("client_key", "") or "").strip()

    @property
    def client_secret(self) -> str:
        return (self._cfg("client_secret", "") or "").strip()

    @property
    def redirect_uri(self) -> str:
        return (self._cfg("redirect_uri", "http://localhost:53682/callback")
                or "").strip()

    @property
    def scopes(self) -> str:
        return (self._cfg("scopes", DEFAULT_SCOPES) or DEFAULT_SCOPES).strip()

    # ---------------------------------------------------------- auth state
    def is_configured(self) -> bool:
        return bool(self.client_key and self.client_secret)

    def is_authorized(self) -> bool:
        return self._access_token() is not None

    def _load_token(self) -> dict | None:
        if not self.token_path.exists():
            return None
        import json
        try:
            return json.loads(self.token_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            log.warning("Bad TikTok token file: %s", exc)
            return None

    def _save_token(self, token: dict) -> None:
        import json
        token = dict(token)
        # Store an absolute expiry so refresh decisions survive restarts.
        if "expires_in" in token:
            token["expires_at"] = time.time() + int(token["expires_in"]) - 60
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token, indent=2),
                                   encoding="utf-8")

    def _access_token(self) -> str | None:
        """Return a valid access token, refreshing it if needed."""
        token = self._load_token()
        if not token or not token.get("access_token"):
            return None
        if time.time() < float(token.get("expires_at", 0)):
            return token["access_token"]
        # Expired - try the refresh token.
        refresh = token.get("refresh_token")
        if not refresh:
            return None
        try:
            return self._refresh(refresh)
        except TikTokError as exc:
            log.warning("TikTok token refresh failed: %s", exc)
            return None

    def _refresh(self, refresh_token: str) -> str:
        requests = _requests()
        resp = requests.post(TOKEN_URL, data={
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30)
        data = resp.json()
        if "access_token" not in data:
            raise TikTokError(f"Refresh failed: {data}")
        self._save_token(data)
        return data["access_token"]

    # ------------------------------------------------------------- authorize
    def authorize(self, timeout_s: int = 180) -> None:
        """Interactive OAuth: opens a browser, catches the redirect, saves token."""
        if not self.is_configured():
            raise TikTokError(SETUP_HELP)
        requests = _requests()

        state = secrets.token_urlsafe(16)
        parsed = urllib.parse.urlparse(self.redirect_uri)
        port = parsed.port or 53682

        params = {
            "client_key": self.client_key,
            "scope": self.scopes,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        auth_url = AUTH_BASE + "?" + urllib.parse.urlencode(params)

        _OAuthCatcher.code = None
        _OAuthCatcher.state = None
        _OAuthCatcher.expected_state = state
        server = http.server.HTTPServer((parsed.hostname or "localhost", port),
                                        _OAuthCatcher)
        server.timeout = timeout_s

        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        log.info("Opening TikTok authorization page...")
        webbrowser.open(auth_url)
        thread.join(timeout_s)
        server.server_close()

        if not _OAuthCatcher.code:
            raise TikTokError("Timed out waiting for TikTok authorization.")
        if _OAuthCatcher.state != state:
            raise TikTokError("OAuth state mismatch - aborting for safety.")

        resp = requests.post(TOKEN_URL, data={
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": _OAuthCatcher.code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30)
        data = resp.json()
        if "access_token" not in data:
            raise TikTokError(f"Token exchange failed: {data}")
        self._save_token(data)
        self._creator_info = None
        log.info("TikTok authorized; token saved to %s", self.token_path)

    def _auth_header(self) -> dict:
        token = self._access_token()
        if token is None:
            raise TikTokError(SETUP_HELP)
        return {"Authorization": f"Bearer {token}"}

    # ----------------------------------------------------------- creator info
    def creator_info(self, force: bool = False) -> dict:
        """Query the creator's posting options (privacy levels, limits)."""
        if self._creator_info is not None and not force:
            return self._creator_info
        requests = _requests()
        headers = self._auth_header()
        headers["Content-Type"] = "application/json; charset=UTF-8"
        resp = requests.post(CREATOR_INFO_URL, headers=headers, timeout=30)
        payload = resp.json()
        err = payload.get("error", {})
        if err.get("code") not in ("ok", None):
            raise TikTokError(f"creator_info failed: {err.get('code')} "
                              f"{err.get('message')}")
        self._creator_info = payload.get("data", {})
        return self._creator_info

    def username(self) -> str:
        """Used to confirm the connection works and to build a profile link."""
        return self.creator_info(force=True).get("creator_username", "")

    def resolve_privacy(self, requested: str) -> str:
        """Pick a privacy level TikTok will accept for this creator.

        Direct-post rejects a privacy_level that is not in the creator's
        allowed options, so we fall back to the safest available option
        (SELF_ONLY) rather than let the whole post fail.
        """
        target = VISIBILITY_TO_PRIVACY.get(requested.lower(), "SELF_ONLY")
        options = self.creator_info().get("privacy_level_options", [])
        if not options:
            return target
        if target in options:
            return target
        for fallback in ("SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS",
                         "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"):
            if fallback in options:
                log.info("Requested privacy %s unavailable; using %s",
                         target, fallback)
                return fallback
        return options[0]

    # ---------------------------------------------------------------- upload
    def upload_video(self, file_path: Path, *, title: str,
                     privacy_level: str = "SELF_ONLY",
                     disable_comment: bool = False,
                     disable_duet: bool = False,
                     disable_stitch: bool = False,
                     is_aigc: bool = True,
                     cover_timestamp_ms: int = 1000,
                     poll_timeout_s: int = 300) -> str:
        """Direct-post a local video file. Returns the TikTok publish_id."""
        requests = _requests()
        file_path = Path(file_path)
        size = file_path.stat().st_size
        if size <= 0:
            raise TikTokError(f"Video file is empty: {file_path}")

        chunk_size, total_chunks = self._chunk_plan(size)

        init_body = {
            "post_info": {
                "title": (title or "")[:2200],
                "privacy_level": privacy_level,
                "disable_comment": bool(disable_comment),
                "disable_duet": bool(disable_duet),
                "disable_stitch": bool(disable_stitch),
                "video_cover_timestamp_ms": int(cover_timestamp_ms),
                "brand_content_toggle": False,
                "brand_organic_toggle": False,
                "is_aigc": bool(is_aigc),
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }
        headers = self._auth_header()
        headers["Content-Type"] = "application/json; charset=UTF-8"
        resp = requests.post(VIDEO_INIT_URL, headers=headers, json=init_body,
                             timeout=60)
        payload = resp.json()
        err = payload.get("error", {})
        if err.get("code") not in ("ok", None):
            raise TikTokError(f"init failed: {err.get('code')} "
                              f"{err.get('message')}")
        data = payload.get("data", {})
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise TikTokError(f"init returned no upload url: {payload}")

        self._put_chunks(file_path, upload_url, size, chunk_size, total_chunks)
        self._await_publish(publish_id, poll_timeout_s)
        log.info("TikTok post published: %s", publish_id)
        return publish_id

    @staticmethod
    def _chunk_plan(size: int) -> tuple[int, int]:
        """TikTok rule: a single chunk if the file is small, else 5MB chunks
        with the final chunk absorbing the remainder (so it can exceed 5MB)."""
        if size <= CHUNK_SIZE:
            return size, 1
        total = size // CHUNK_SIZE  # last chunk carries the remainder
        return CHUNK_SIZE, max(1, total)

    def _put_chunks(self, file_path: Path, upload_url: str, size: int,
                    chunk_size: int, total_chunks: int) -> None:
        requests = _requests()
        with file_path.open("rb") as fh:
            for index in range(total_chunks):
                first = index * chunk_size
                if index == total_chunks - 1:
                    last = size - 1               # final chunk -> end of file
                else:
                    last = first + chunk_size - 1
                length = last - first + 1
                fh.seek(first)
                chunk = fh.read(length)
                headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(length),
                    "Content-Range": f"bytes {first}-{last}/{size}",
                }
                put = requests.put(upload_url, headers=headers, data=chunk,
                                   timeout=300)
                if put.status_code not in (200, 201, 206):
                    raise TikTokError(
                        f"chunk {index + 1}/{total_chunks} upload failed: "
                        f"HTTP {put.status_code} {put.text[:200]}")

    def _await_publish(self, publish_id: str, timeout_s: int) -> None:
        requests = _requests()
        headers = self._auth_header()
        headers["Content-Type"] = "application/json; charset=UTF-8"
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            resp = requests.post(STATUS_URL, headers=headers,
                                 json={"publish_id": publish_id}, timeout=30)
            payload = resp.json()
            err = payload.get("error", {})
            if err.get("code") not in ("ok", None):
                raise TikTokError(f"status failed: {err.get('code')} "
                                  f"{err.get('message')}")
            status = payload.get("data", {}).get("status", "")
            if status in ("PUBLISH_COMPLETE", "PUBLISHED"):
                return
            if status == "FAILED":
                reason = payload.get("data", {}).get("fail_reason", "")
                raise TikTokError(f"TikTok reported publish failure: {reason}")
            time.sleep(3)
        # Processing can outlive our poll window; that's not necessarily an
        # error (the post may still land), so we surface it as one and let the
        # publisher mark it for retry/inspection.
        raise TikTokError(
            f"Timed out after {timeout_s}s waiting for TikTok to finish "
            f"processing (publish_id={publish_id}). It may still complete.")
