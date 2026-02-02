import json
import os
from typing import Dict, List, Optional, Tuple


def _walk(node: Dict, prefix: Optional[str] = None) -> List[str]:
    name = node.get("name", "").strip()
    if not name:
        return []
    path = name if not prefix else f"{prefix}/{name}"
    children = node.get("children") or []
    if not children:
        return [path]
    out: List[str] = []
    for ch in children:
        out.extend(_walk(ch, path))
    return out


def flatten_categories(tree: Dict) -> List[str]:
    cats = tree.get("categories") or []
    out: List[str] = []
    for c in cats:
        out.extend(_walk(c, None))
    # also allow top-level categories as leaf if user uses them
    top = [c.get("name", "").strip() for c in cats if c.get("name")]
    out.extend([t for t in top if t])
    # unique stable
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_category(
    raw: Optional[str],
    categories: List[str],
    aliases: Dict[str, str],
) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None

    # exact match
    if s in categories:
        return s

    # try alias
    key = s.lower()
    if key in aliases:
        cand = aliases[key]
        return cand if cand in categories else cand

    # heuristic: if user provided a single word, try contains match
    if "/" not in s:
        low = s.lower()
        hits = [c for c in categories if c.lower().endswith("/" + low) or c.lower() == low]
        if len(hits) == 1:
            return hits[0]

    return s
