import json
import re
from typing import Any, Optional

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_NULLISH = {"", "null", "none", "n/a", "na", "nil"}


def extract_json_object(text: str) -> Optional[dict]:
    """Pull the first JSON object out of model output (handles code fences and extra prose)."""
    if not text:
        return None
    candidates = []
    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)

    for cand in candidates:
        cand = cand.strip()
        try:
            obj = json.loads(cand)
        except ValueError:
            start, end = cand.find("{"), cand.rfind("}")
            if start == -1 or end <= start:
                continue
            try:
                obj = json.loads(cand[start:end + 1])
            except ValueError:
                continue
        if isinstance(obj, dict):
            return obj
    return None


def clean_value(value: Any) -> Optional[str]:
    """Normalise a raw model value to a stripped string, or None for null-like values."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return None if text.lower() in _NULLISH else text