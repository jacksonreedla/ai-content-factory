# app/secrets.py
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.paths import AppPaths


@dataclass
class Secrets:
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ai-content-factory/0.1 by <user>"
    llm_api_keys: dict = field(default_factory=dict)  # provider name → key


def load_secrets(paths: Optional[AppPaths] = None) -> Secrets:
    paths = paths or AppPaths()
    if not paths.secrets_path.exists():
        return Secrets()
    data = json.loads(paths.secrets_path.read_text() or "{}")
    keep = {k: v for k, v in data.items() if k in Secrets.__dataclass_fields__}
    return Secrets(**keep)


def save_secrets(secrets: Secrets, paths: Optional[AppPaths] = None) -> None:
    paths = paths or AppPaths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.secrets_path.write_text(json.dumps(asdict(secrets), indent=2))
    try:
        os.chmod(paths.secrets_path, 0o600)
    except OSError:  # pragma: no cover - some platforms ignore chmod
        pass
