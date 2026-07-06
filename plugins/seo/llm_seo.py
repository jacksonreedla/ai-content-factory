# plugins/seo/llm_seo.py
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

_PROMPT = Path(__file__).resolve().parent.parent.parent / "config" / "prompts" / "seo.txt"
_SCHEMA = Path(__file__).resolve().parent.parent.parent / "config" / "seo_schema.json"

log = logging.getLogger(__name__)


@dataclass
class SEOResult:
    title: str = ""
    description: str = ""
    tags: list = field(default_factory=list)
    hashtags: list = field(default_factory=list)
    pinned_comment: str = ""
    community_post: str = ""
    ctr_score: float = 0.0
    seo_score: float = 0.0


class LLMSEOGenerator:
    """SEOGenerator over an LLM provider. Satisfies the SEOGenerator protocol."""

    def __init__(self, model_name: str = "") -> None:
        self.model_name = model_name
        self._prompt = _PROMPT.read_text(encoding="utf-8")
        self._schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))

    def generate(self, video, script) -> SEOResult:
        # `video` may be a row dict (has video_path etc.); `script` is the text.
        script_text = script if isinstance(script, str) else (
            script.get("text") if isinstance(script, dict) else
            getattr(script, "text", ""))
        prompt = self._prompt.format(script=script_text or "")
        # `video` carries the llm on it in tests; in prod the agent passes llm.
        llm = getattr(video, "llm", None) or (video["llm"] if isinstance(video, dict) and "llm" in video else None)
        if llm is None:
            raise RuntimeError("LLMSEOGenerator.generate needs an 'llm' on the video arg")
        data = llm.json_complete(prompt, self._schema)
        return SEOResult(
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            tags=list(data.get("tags", [])),
            hashtags=list(data.get("hashtags", [])),
            pinned_comment=str(data.get("pinned_comment", "")),
            community_post=str(data.get("community_post", "")),
            ctr_score=float(data.get("ctr_score", 0)),
            seo_score=float(data.get("seo_score", 0)),
        )
