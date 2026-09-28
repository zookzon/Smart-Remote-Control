import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "smart_remote_control"
TAG = re.compile(r"<[^>]+>")

def _walk(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)
    elif isinstance(value, str):
        yield value

def test_no_tag_like_markup_in_strings():
    for rel in ("translations/en.json",):
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        bad = [text for text in _walk(data) if TAG.search(text)]
        assert not bad, bad
