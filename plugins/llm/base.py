# plugins/llm/base.py
import json
import re


def extract_json(text: str) -> dict:
    """Best-effort JSON object extraction from LLM output.

    Handles markdown code fences and surrounding prose. Raises ValueError
    (or json.JSONDecodeError) when no JSON can be parsed.
    """
    if not text:
        raise ValueError("empty LLM response")
    # Strip markdown code fences.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Otherwise grab the first {...} block.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)
