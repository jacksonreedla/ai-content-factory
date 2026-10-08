"""YouTube Data API v3 client: OAuth, resumable upload, thumbnails, playlists.

Setup (one time, free):
  1. console.cloud.google.com -> new project -> enable "YouTube Data API v3"
  2. OAuth consent screen -> External -> add yourself as test user
  3. Credentials -> Create OAuth client ID -> Desktop app
  4. Download the JSON as settings/client_secret.json

Google libraries are imported lazily so the rest of the app runs without
them installed.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.paths import DATA_DIR, SETTINGS_DIR

log = logging.getLogger("acf.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]
DEFAULT_SECRETS = SETTINGS_DIR / "client_secret.json"
DEFAULT_TOKEN = DATA_DIR / "youtube_token.json"

SETUP_HELP = (
    "YouTube is not connected. One-time setup: create a Google Cloud project, "
    "enable 'YouTube Data API v3', create an OAuth 'Desktop app' client, and "
    "save the downloaded JSON as settings/client_secret.json. Then click "
    "'Connect YouTube' on the Uploads page. Full steps are in README.md."
)


class YouTubeError(RuntimeError):
    pass


def _import_google():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        return Request, Credentials, InstalledAppFlow, build, MediaFileUpload
    except ImportError as exc:
        raise YouTubeError(
            "Google API libraries missing. Run: pip install "
            "google-api-python-client google-auth-oauthlib") from exc


class YouTubeClient:
    def __init__(self, secrets_path: Path = DEFAULT_SECRETS,
                 token_path: Path = DEFAULT_TOKEN, category_id: str = "24"):
        self.secrets_path = Path(secrets_path)
        self.token_path = Path(token_path)
        self.category_id = category_id
        self._service = None

    # ------------------------------------------------------------ auth state
    def is_configured(self) -> bool:
        return self.secrets_path.exists()

    def is_authorized(self) -> bool:
        return self.token_path.exists() and self._credentials() is not None

    def _credentials(self):
        if not self.token_path.exists():
            return None
        Request, Credentials, *_ = _import_google()
        try:
            creds = Credentials.from_authorized_user_file(
                str(self.token_path), SCOPES)
        except (ValueError, OSError) as exc:
            log.warning("Bad YouTube token file: %s", exc)
            return None
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self.token_path.write_text(creds.to_json(), encoding="utf-8")
                return creds
            except Exception as exc:
                log.warning("YouTube token refresh failed: %s", exc)
        return None

    def authorize(self) -> None:
        """Interactive OAuth - opens a browser, saves the token."""
        if not self.is_configured():
            raise YouTubeError(SETUP_HELP)
        _Request, _Creds, InstalledAppFlow, *_ = _import_google()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.secrets_path), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")
        self._service = None
        log.info("YouTube authorized; token saved to %s", self.token_path)

    def service(self):
        if self._service is None:
            creds = self._credentials()
            if creds is None:
                raise YouTubeError(SETUP_HELP)
            *_, build, _media = _import_google()
            self._service = build("youtube", "v3", credentials=creds,
                                  cache_discovery=False)
        return self._service

    # ---------------------------------------------------------------- upload
    def upload_video(self, file_path: Path, *, title: str, description: str,
                     tags: list[str], privacy: str = "private",
                     publish_at_utc: str | None = None,
                     made_for_kids: bool = False) -> str:
        """Resumable upload. Returns the YouTube video id."""
        *_, MediaFileUpload = _import_google()
        service = self.service()

        status: dict = {
            "privacyStatus": "private" if publish_at_utc else privacy,
            "selfDeclaredMadeForKids": made_for_kids,
        }
        if publish_at_utc:
            status["publishAt"] = publish_at_utc  # requires privacy=private
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:4900],
                "tags": tags[:40],
                "categoryId": self.category_id,
            },
            "status": status,
        }
        media = MediaFileUpload(str(file_path), chunksize=8 * 1024 * 1024,
                                resumable=True)
        request = service.videos().insert(
            part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            try:
                progress, response = request.next_chunk()
                if progress:
                    log.info("Upload %s: %d%%", file_path.name,
                             int(progress.progress() * 100))
            except Exception as exc:
                raise YouTubeError(f"Upload failed: {exc}") from exc
        video_id = response.get("id", "")
        if not video_id:
            raise YouTubeError(f"Upload returned no video id: {response}")
        log.info("Uploaded %s -> https://youtu.be/%s", file_path.name, video_id)
        return video_id

    def set_thumbnail(self, video_id: str, thumbnail_path: Path) -> None:
        *_, MediaFileUpload = _import_google()
        try:
            self.service().thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path)),
            ).execute()
        except Exception as exc:
            # Non-fatal: brand-new channels can't set custom thumbnails yet.
            log.warning("Thumbnail set failed for %s: %s", video_id, exc)

    def add_to_playlist(self, video_id: str, playlist_id: str) -> None:
        try:
            self.service().playlistItems().insert(
                part="snippet",
                body={"snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video",
                                   "videoId": video_id},
                }},
            ).execute()
        except Exception as exc:
            log.warning("Playlist add failed for %s: %s", video_id, exc)

    def video_stats(self, video_ids: list[str]) -> dict[str, dict]:
        """{youtube_id: {views, likes, comments}} for up to 50 ids per call."""
        stats: dict[str, dict] = {}
        for start in range(0, len(video_ids), 50):
            batch = video_ids[start:start + 50]
            try:
                response = self.service().videos().list(
                    part="statistics", id=",".join(batch)).execute()
            except Exception as exc:
                raise YouTubeError(f"Stats fetch failed: {exc}") from exc
            for item in response.get("items", []):
                s = item.get("statistics", {})
                stats[item["id"]] = {
                    "views": int(s.get("viewCount", 0)),
                    "likes": int(s.get("likeCount", 0)),
                    "comments": int(s.get("commentCount", 0)),
                }
        return stats

    def channel_title(self) -> str:
        """Small call used to verify the connection works."""
        response = self.service().channels().list(
            part="snippet", mine=True).execute()
        items = response.get("items", [])
        return items[0]["snippet"]["title"] if items else "(no channel)"
