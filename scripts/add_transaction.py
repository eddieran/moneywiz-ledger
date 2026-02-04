#!/usr/bin/env python3
"""
MoneyWiz URL generator for OpenClaw.

Generates moneywiz:// deep links for expense/income/transfer transactions.
No local ledger storage - just URL generation.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from typing import Optional, Dict, List

# Paths relative to this script's parent directory (the skill root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "references", "config.json")
CONFIG_LOCAL_PATH = os.path.join(BASE_DIR, "references", "config.local.json")
CATEGORIES_PATH = os.path.join(BASE_DIR, "references", "categories.json")
ALIASES_PATH = os.path.join(BASE_DIR, "references", "category_aliases.json")


def load_config() -> Dict:
    """Load config with local override.

    Priority:
    1. references/config.local.json (user-specific, gitignored)
    2. references/config.json (defaults)
    """
    cfg = {}
    
    # Load base config
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    
    # Merge local overrides (takes precedence)
    if os.path.exists(CONFIG_LOCAL_PATH):
        try:
            with open(CONFIG_LOCAL_PATH, "r", encoding="utf-8") as f:
                local = json.load(f)
            cfg.update(local)  # local overrides base
        except Exception as e:
            print(f"Warning: Failed to load config.local.json: {e}", file=sys.stderr)
    
    return cfg


def load_json(path: str) -> Dict:
    """Load a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _walk_category(node: Dict, prefix: Optional[str] = None) -> List[str]:
    """Recursively walk category tree and collect all paths."""
    name = node.get("name", "").strip()
    if not name:
        return []
    path = name if not prefix else f"{prefix}/{name}"
    children = node.get("children") or []
    if not children:
        return [path]
    out: List[str] = []
    for ch in children:
        out.extend(_walk_category(ch, path))
    return out


def flatten_categories(tree: Dict) -> List[str]:
    """Flatten category tree into list of 'Parent/Child' paths."""
    cats = tree.get("categories") or []
    out: List[str] = []
    for c in cats:
        out.extend(_walk_category(c, None))
    # Also allow top-level categories as leaf
    top = [c.get("name", "").strip() for c in cats if c.get("name")]
    out.extend([t for t in top if t])
    # Unique, preserving order
    seen = set()
    return [p for p in out if not (p in seen or seen.add(p))]


def resolve_category(
    raw: Optional[str],
    categories: List[str],
    aliases: Dict[str, str],
) -> Optional[str]:
    """Resolve user input to a valid category path."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None

    # Exact match
    if s in categories:
        return s

    # Try alias (case-insensitive)
    key = s.lower()
    if key in aliases:
        return aliases[key]

    # Heuristic: if user provided a single word, try suffix match
    if "/" not in s:
        low = s.lower()
        hits = [c for c in categories if c.lower().endswith("/" + low) or c.lower() == low]
        if len(hits) == 1:
            return hits[0]

    # Return as-is (MoneyWiz will handle unknown categories)
    return s


def now_local(tzname: str) -> datetime:
    """Get current time in specified timezone."""
    return datetime.now(ZoneInfo(tzname))


def normalize_account(name: str) -> str:
    """Remove spaces from account name (MoneyWiz requirement)."""
    return (name or "").replace(" ", "")


def build_moneywiz_url(
    op: str,
    amount: Optional[float],
    account: Optional[str],
    to_account: Optional[str],
    currency: Optional[str],
    category: Optional[str],
    payee: Optional[str],
    description: Optional[str],
    memo: Optional[str],
    tags: Optional[str],
    date_str: Optional[str],
    save: bool,
) -> str:
    """Build MoneyWiz URL scheme."""
    params = []

    def add(k, v, safe=""):
        if v is None or v == "":
            return
        params.append(f"{k}={quote(str(v), safe=safe)}")

    if op in ("expense", "income"):
        if amount is None:
            raise ValueError("amount is required for expense/income")
        if not account:
            raise ValueError("account is required for expense/income")
        add("amount", f"{amount:.2f}")
        add("account", account)
        add("currency", currency)
        add("payee", payee)
        add("category", category, safe="/")  # Allow slash in category
        add("description", description)
        add("memo", memo)
        add("tags", tags)
        add("date", date_str)
        add("save", str(save).lower())

    elif op == "transfer":
        if amount is None:
            raise ValueError("amount is required for transfer")
        if not account or not to_account:
            raise ValueError("account and toAccount are required for transfer")
        add("account", account)
        add("toAccount", to_account)
        add("amount", f"{amount:.2f}")
        add("save", str(save).lower())
    else:
        raise ValueError(f"unsupported operation: {op}")

    qs = "&".join(params)
    return f"moneywiz://{op}?{qs}"


def main():
    cfg = load_config()
    
    # Debug: print which config was loaded
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true")
    if debug:
        print(f"DEBUG: Loaded config: {json.dumps(cfg, indent=2)}", file=sys.stderr)

    p = argparse.ArgumentParser(description="Generate MoneyWiz URL for transaction")
    p.add_argument("--type", choices=["expense", "income", "transfer"], default="expense")
    p.add_argument("--amount", type=float, required=False)
    p.add_argument("--currency", default=None)
    p.add_argument("--account", default=None)
    p.add_argument("--to-account", dest="to_account", default=None)
    p.add_argument("--category", default=None)
    p.add_argument("--payee", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--memo", default=None)
    p.add_argument("--tags", default=None)
    p.add_argument("--date", default=None, help="YYYY-MM-DD HH:MM:SS (local timezone)")
    p.add_argument("--save", default=None, choices=["true", "false"])
    args = p.parse_args()

    tz = cfg.get("timezone", "Asia/Singapore")

    # Apply defaults from config
    currency = (args.currency or cfg.get("default_currency") or "").upper()
    account = normalize_account(args.account or cfg.get("default_account") or "")
    to_account = normalize_account(args.to_account) if args.to_account else ""
    
    if debug:
        print(f"DEBUG: Using account: {account}", file=sys.stderr)

    # Load categories and aliases
    categories_list = []
    aliases = {}
    
    if os.path.exists(CATEGORIES_PATH):
        try:
            categories_list = flatten_categories(load_json(CATEGORIES_PATH))
            if debug:
                print(f"DEBUG: Loaded {len(categories_list)} categories", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to load categories: {e}", file=sys.stderr)
    
    if os.path.exists(ALIASES_PATH):
        try:
            aliases = load_json(ALIASES_PATH).get("aliases") or {}
            if debug:
                print(f"DEBUG: Loaded {len(aliases)} aliases", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to load aliases: {e}", file=sys.stderr)

    # Resolve category
    raw_cat = args.category or cfg.get("default_category") or ""
    category = resolve_category(raw_cat, categories_list, aliases) or ""

    # Validate category exists (strict mode: enforce existing)
    if categories_list and category and category not in categories_list:
        fallback = cfg.get("default_category")
        # Try to resolve fallback to a valid path
        resolved_fallback = resolve_category(fallback, categories_list, aliases)
        
        # Determine final category
        if resolved_fallback and resolved_fallback in categories_list:
            final_cat = resolved_fallback
        elif fallback and fallback in categories_list:
            final_cat = fallback
        else:
            # If default fails, try to find a generic one or just use the first one
            # But for now, let's just warn and use fallback (or "Uncategorized" if nil)
            final_cat = fallback or "Uncategorized"
            
        print(f"Warning: Category '{category}' not found in list. Fallback to '{final_cat}'.", file=sys.stderr)
        category = final_cat

    # Save behavior
    if args.save is None:
        save = bool(cfg.get("moneywiz_save_default", False))
    else:
        save = args.save == "true"

    # Date/time
    if args.date:
        ts_local = args.date.strip()
    else:
        ts_local = now_local(tz).strftime("%Y-%m-%d %H:%M:%S")

    # Build URL
    url = build_moneywiz_url(
        op=args.type,
        amount=args.amount,
        account=account,
        to_account=to_account,
        currency=currency,
        category=category,
        payee=args.payee,
        description=args.description,
        memo=args.memo,
        tags=args.tags,
        date_str=ts_local,
        save=save,
    )

    print(url)
    
    # Auto-open on macOS if configured
    if sys.platform == "darwin" and cfg.get("auto_open_on_mac"):
        try:
            import subprocess
            subprocess.run(["open", url], check=True)
            if debug:
                print("DEBUG: Opened MoneyWiz URL", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to auto-open URL: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
