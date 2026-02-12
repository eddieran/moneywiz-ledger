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


def infer_category(raw: str, categories: List[str], txn_type: str = "expense") -> Optional[str]:
    """Infer a best-fit category from keywords before falling back to default."""
    s = raw.strip().lower()
    if not s:
        return None

    expense_rules = [
        (["咖啡", "coffee", "latte", "cappuccino"], "Food & Life/Coffee"),
        (["奶茶", "饮料", "drink", "juice", "茶"], "Food & Life/Drink"),
        (["买菜", "超市", "grocery", "fairprice", "sheng siong"], "Food & Life/Buy Food"),
        (["水果", "fruit"], "Food & Life/Fruit"),
        (["零食", "snack"], "Food & Life/Snacks"),
        (["吃饭", "点餐", "外卖", "餐", "火锅", "haidilao", "restaurant", "dinner", "lunch"], "Food & Life/Restaurant"),
        (["打车", "taxi", "grab", "gojek"], "Transportation/Taxi"),
        (["地铁", "公交", "bus", "mrt", "train", "public transport"], "Transportation/Public Transportation"),
        (["停车", "parking"], "Transportation/Parking"),
        (["油费", "加油", "fuel", "petrol"], "Transportation/Fuel"),
        (["水电", "电费", "水费", "utilities", "utility"], "Household/Electric & Water"),
        (["网费", "internet", "wifi", "broadband"], "Household/Internet"),
        (["手机费", "电话费", "mobile", "telephone", "phone bill"], "Household/Telephone"),
        (["订阅", "subscription", "chatgpt", "1password", "notion", "software"], "Productivity/Software Subscribe"),
        (["书", "book", "kindle"], "Productivity/Book"),
        (["电影", "cinema", "movie"], "Entertainment/Movie"),
        (["拍照", "拍照片", "photo", "photograph"], "Entertainment/Photo"),
        (["按摩", "massage"], "Entertainment/Massage"),
        (["游戏", "game", "steam"], "Entertainment/Game"),
        (["健身", "gym"], "Health/Gym"),
        (["看病", "医院", "medical", "clinic", "doctor"], "Health/Medical"),
        (["牙", "dental"], "Health/Dental"),
        (["机票", "air ticket", "flight"], "Travel/Airplane"),
        (["酒店", "hotel"], "Travel/Hotel"),
        (["签证", "visa"], "Government/Visa"),
        (["保险", "insurance"], "Government/Insurance"),
        (["税", "tax"], "Government/Tax"),
        (["拖鞋", "鞋", "衣服", "clothes", "shirt", "pants", "shoe", "slipper"], "Shopping/Clothes"),
        (["电子", "设备", "iphone", "macbook", "ipad", "headphone", "electronic"], "Shopping/Electric Device"),
        (["礼物", "gift"], "Festival/Gift"),
    ]

    income_rules = [
        (["工资", "salary", "payroll"], "Salary"),
        (["年终", "年终奖", "annual bonus"], "Annual Bonus"),
        (["奖金", "bonus"], "Other Bonus"),
        (["分红", "股息", "dividend"], "Dividends"),
        (["利息", "interest"], "Interest"),
        (["投资", "investment"], "Investments"),
        (["定投", "stable investment", "dca"], "Stable Investment"),
        (["报税", "退税", "tax refund"], "Tax Refund"),
        (["返现", "cashback"], "Cashback"),
        (["退款", "refund"], "Refund"),
        (["公司福利", "benefit"], "Company Benefit"),
        (["奖励", "reward"], "Reward"),
        (["拼单", "aa", "split bill"], "Split bill"),
        (["闲置", "二手", "carousell"], "Carousell"),
        (["入金", "存入", "deposit", "debit/deposit"], "Debit/Deposit"),
        (["收入", "incoming", "other income"], "Other incoming"),
    ]

    rules = income_rules if txn_type == "income" else expense_rules

    for keys, target in rules:
        if target not in categories:
            continue
        if any(k in s for k in keys):
            return target

    return None


def resolve_category(
    raw: Optional[str],
    categories: List[str],
    aliases: Dict[str, str],
    txn_type: str = "expense",
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

    # Best-effort inference before fallback
    inferred = infer_category(s, categories, txn_type=txn_type)
    if inferred:
        return inferred

    # Return as-is (validator will fallback to default)
    return s


def save_alias(alias_key: str, target: str) -> None:
    """Persist newly inferred alias to references/category_aliases.json."""
    key = (alias_key or "").strip().lower()
    if not key:
        return

    data = {"aliases": {}}
    if os.path.exists(ALIASES_PATH):
        try:
            data = load_json(ALIASES_PATH)
        except Exception:
            data = {"aliases": {}}

    aliases = data.get("aliases") or {}
    if aliases.get(key) == target:
        return

    aliases[key] = target
    data["aliases"] = aliases
    with open(ALIASES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


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

    # Resolve category (support type-specific defaults)
    if args.type == "income":
        default_cat = cfg.get("default_income_category") or cfg.get("default_category")
    elif args.type == "expense":
        default_cat = cfg.get("default_expense_category") or cfg.get("default_category")
    else:
        default_cat = cfg.get("default_category")

    raw_cat = args.category or default_cat or ""
    category = resolve_category(raw_cat, categories_list, aliases, txn_type=args.type) or ""

    # If inferred/resolved to a valid known path, persist alias for future runs
    raw_key = (raw_cat or "").strip().lower()
    if (
        categories_list
        and category in categories_list
        and raw_key
        and raw_key not in aliases
        and raw_key != category.lower()
        and "/" not in raw_cat
    ):
        try:
            save_alias(raw_key, category)
            print(f"Info: Learned alias '{raw_cat}' -> '{category}'.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to persist alias '{raw_cat}': {e}", file=sys.stderr)

    # Validate category exists (strict mode: enforce existing)
    if categories_list and category and category not in categories_list:
        if args.type == "income":
            fallback = cfg.get("default_income_category") or cfg.get("default_category")
            hard_default = "Other incoming"
        elif args.type == "expense":
            fallback = cfg.get("default_expense_category") or cfg.get("default_category")
            hard_default = "Shopping/Other"
        else:
            fallback = cfg.get("default_category")
            hard_default = "Shopping/Other"

        # Try to resolve fallback to a valid path
        resolved_fallback = resolve_category(fallback, categories_list, aliases, txn_type=args.type)

        # Determine final category
        if resolved_fallback and resolved_fallback in categories_list:
            final_cat = resolved_fallback
        elif fallback and fallback in categories_list:
            final_cat = fallback
        elif hard_default in categories_list:
            final_cat = hard_default
        else:
            final_cat = fallback or hard_default

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
