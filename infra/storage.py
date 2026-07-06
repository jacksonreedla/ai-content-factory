# infra/storage.py
from pathlib import Path


def job_dir(paths, job_id: int) -> Path:
    """Return (creating) the per-job working directory."""
    d = paths.jobs_dir / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def library_subdir(paths, kind: str, category: str = "") -> Path:
    """Return (creating) a library subdirectory: library/<kind>[/<category>]."""
    d = paths.library_dir / kind
    if category:
        d = d / category
    d.mkdir(parents=True, exist_ok=True)
    return d
