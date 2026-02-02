#!/usr/bin/env python3
"""Reconcile local ledger vs a MoneyWiz CSV export.

MoneyWiz export column names can vary. This script tries to auto-detect common fields.

Usage:
  python3 reconcile_moneywiz_export.py \
    --moneywiz-csv /path/to/export.csv \
    --ledger-csv skills/moneywiz-ledger/data/transactions.csv

Outputs:
  - counts
  - ledger rows that do not appear in MoneyWiz export (best-effort matching)

This is a best-effort helper; it never edits MoneyWiz data.
"""

import argparse
import csv
import datetime as dt
import os
from typing import Dict, List, Optional, Tuple


def parse_dt(s: str) -> Optional[dt.datetime]:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
        try:
            return dt.datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def sniff_cols(fieldnames: List[str]) -> Dict[str, str]:
    lower = {f.lower(): f for f in fieldnames}

    def pick(cands: List[str]) -> Optional[str]:
        for c in cands:
            if c in lower:
                return lower[c]
        return None

    return {
        "date": pick(["date", "transaction date", "time", "datetime", "created", "ts_local"]),
        "amount": pick(["amount", "value", "sum", "transaction amount"]),
        "memo": pick(["memo", "note", "description", "details"]),
        "account": pick(["account", "from account", "wallet"]),
        "category": pick(["category", "category path", "category/subcategory"]),
        "type": pick(["type", "transaction type"]),
    }


def read_csv(path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
        return rows, (r.fieldnames or [])


def norm_amount(s: str) -> Optional[float]:
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--moneywiz-csv", required=True)
    ap.add_argument("--ledger-csv", required=True)
    ap.add_argument("--window-min", type=int, default=5, help="match window in minutes")
    ap.add_argument("--amount-eps", type=float, default=0.01, help="amount tolerance")
    args = ap.parse_args()

    mw_rows, mw_fields = read_csv(args.moneywiz_csv)
    led_rows, led_fields = read_csv(args.ledger_csv)

    mw_cols = sniff_cols(mw_fields)

    # build index from moneywiz export (amount -> list of (dt, memo, raw))
    idx: List[Tuple[Optional[dt.datetime], Optional[float], str, Dict[str, str]]] = []
    for r in mw_rows:
        dtv = parse_dt(r.get(mw_cols["date"]) if mw_cols["date"] else "")
        amt = norm_amount(r.get(mw_cols["amount"]) if mw_cols["amount"] else "")
        memo = (r.get(mw_cols["memo"]) if mw_cols["memo"] else "") or ""
        idx.append((dtv, amt, memo.strip(), r))

    def match_one(lr: Dict[str, str]) -> bool:
        ldt = parse_dt(lr.get("ts_local", ""))
        lamt = norm_amount(lr.get("amount", ""))
        lmemo = (lr.get("memo", "") or "").strip()
        if lamt is None:
            return False

        for dtv, amt, memo, raw in idx:
            if amt is None:
                continue
            if abs(amt - lamt) > args.amount_eps:
                continue
            if ldt and dtv:
                if abs((dtv - ldt).total_seconds()) > args.window_min * 60:
                    continue
            # memo is fuzzy: if one contains the other, accept
            if lmemo and memo:
                if (lmemo not in memo) and (memo not in lmemo):
                    continue
            return True
        return False

    missing = [lr for lr in led_rows if not match_one(lr)]

    print(f"MoneyWiz export rows: {len(mw_rows)}")
    print(f"Ledger rows: {len(led_rows)}")
    print(f"Likely missing in MoneyWiz: {len(missing)}")
    for lr in missing[:50]:
        print(f"- {lr.get('ts_local')} {lr.get('type')} {lr.get('amount')} {lr.get('currency')} {lr.get('account')} {lr.get('category')} {lr.get('memo')}")


if __name__ == "__main__":
    main()
