# app/paths.py
import os
from pathlib import Path


class AppPaths:
    """Cross-platform path resolution for user data.

    Override the user dir with $AICF_HOME (used by tests and portable installs).
    """

    def __init__(self) -> None:
        home = os.environ.get("AICF_HOME")
        if home:
            self.data_dir = Path(home)
        else:
            self.data_dir = Path.home() / ".aicf"

    @property
    def db_path(self) -> Path: return self.data_dir / "aicf.db"
    @property
    def settings_path(self) -> Path: return self.data_dir / "settings.json"
    @property
    def secrets_path(self) -> Path: return self.data_dir / "secrets.json"
    @property
    def logs_dir(self) -> Path: return self.data_dir / "logs"
    @property
    def library_dir(self) -> Path: return self.data_dir / "library"
    @property
    def jobs_dir(self) -> Path: return self.data_dir / "jobs"
    @property
    def plugins_dir(self) -> Path: return self.data_dir / "plugins"

    def ensure(self) -> None:
        for d in (self.data_dir, self.logs_dir, self.library_dir,
                  self.jobs_dir, self.plugins_dir):
            d.mkdir(parents=True, exist_ok=True)
