#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from typing import Optional

from categories import flatten_categories, load_json, resolve_category

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "references", "config.json")
CONFIG_LOCAL_PATH = os.path.join(BASE_DIR, "references", "config.local.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
LEDGER_PATH = os.path.join(DATA_DIR, "transactions.csv")

# Optional category validation
CATEGORIES_DEFAULT = os.path.join(BASE_DIR, "references", "categories.json")
ALIASES_DEFAULT = os.path.join(BASE_DIR, "references", "category_aliases.json")


def load_config():
    """Load config with local override.

    - references/config.json: safe defaults (can be committed to public repo)
    - references/config.local.json: user-specific overrides (ignored by git)
    """
    cfg = {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if os.path.exists(CONFIG_LOCAL_PATH):
        try:
            with open(CONFIG_LOCAL_PATH, "r", encoding="utf-8") as f:
                local = json.load(f)
            # shallow merge
            cfg.update(local)
        except Exception:
            pass

    return cfg


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def now_local(tzname: str) -> datetime:
    return datetime.now(ZoneInfo(tzname))


def normalize_account(name: str) -> str:
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
    # MoneyWiz expects URL-encoded values; we keep slashes in category.
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
        # allow slash in category hierarchy
        add("category", category, safe="/")
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
        raise ValueError("unsupported op")

    qs = "&".join(params)
    return f"moneywiz://{op}?{qs}"


def append_ledger(row: dict):
    ensure_dirs()
    exists = os.path.exists(LEDGER_PATH)
    with open(LEDGER_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "ts_local",
                "type",
                "amount",
                "currency",
                "account",
                "to_account",
                "category",
                "payee",
                "description",
                "memo",
                "tags",
                "save",
                "source",
            ],
        )
        if not exists:
            w.writeheader()
        w.writerow(row)


def main():
    cfg = load_config()

    p = argparse.ArgumentParser()
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
    p.add_argument("--source", default="openclaw")
    args = p.parse_args()

    tz = cfg.get("timezone", "Asia/Singapore")

    currency = (args.currency or cfg.get("default_currency") or "").upper()
    account = normalize_account(args.account or cfg.get("default_account") or "")
    to_account = normalize_account(args.to_account) if args.to_account else ""
    # Category resolution: enforce existing category paths when possible
    categories_path = cfg.get("categories_file") or CATEGORIES_DEFAULT
    aliases_path = cfg.get("category_aliases_file") or ALIASES_DEFAULT

    categories_list = []
    aliases = {}
    try:
        if os.path.exists(categories_path):
            categories_list = flatten_categories(load_json(categories_path))
    except Exception:
        categories_list = []
    try:
        if os.path.exists(aliases_path):
            aliases = (load_json(aliases_path).get("aliases") or {})
    except Exception:
        aliases = {}

    raw_cat = args.category or cfg.get("default_category") or ""
    category = resolve_category(raw_cat, categories_list, aliases) or ""

    # If we have a category list, require membership
    if categories_list and category and category not in categories_list:
        raise ValueError(
            f"category not in allowed list: {category}. Provide an existing category path (e.g. 'Food & Life/Buy Food')."
        )

    if args.save is None:
        save = bool(cfg.get("moneywiz_save_default", False))
    else:
        save = args.save == "true"

    if args.date:
        # assume provided date is local time
        ts_local = args.date.strip()
    else:
        ts_local = now_local(tz).strftime("%Y-%m-%d %H:%M:%S")

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

    append_ledger(
        {
            "ts_local": ts_local,
            "type": args.type,
            "amount": f"{args.amount:.2f}" if args.amount is not None else "",
            "currency": currency,
            "account": account,
            "to_account": to_account,
            "category": category,
            "payee": args.payee or "",
            "description": args.description or "",
            "memo": args.memo or "",
            "tags": args.tags or "",
            "save": str(save).lower(),
            "source": args.source,
        }
    )

    print(url)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
