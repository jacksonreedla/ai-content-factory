"""LLM provider abstraction. Ollama is the default; Claude/OpenAI are
drop-in fallbacks activated simply by adding an API key in Settings."""
from api.llm.base import LLMError, LLMProvider, LLMResponse
from api.llm.router import LLMRouter

__all__ = ["LLMError", "LLMProvider", "LLMResponse", "LLMRouter"]
