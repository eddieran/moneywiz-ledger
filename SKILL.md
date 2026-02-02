---
name: moneywiz-ledger
description: Record personal expenses/income from chat (often transcribed voice) into a local ledger and generate a MoneyWiz URL scheme (moneywiz://expense|income|transfer?...) to create the transaction in the MoneyWiz app. Use when the user says they spent/earned/transferred money, asks to log a transaction, wants to "记账/报销/记一笔", or wants a MoneyWiz deep link for transaction creation.
---

# MoneyWiz Ledger (voice → bookkeeping)

You log transactions **locally in the workspace** and optionally generate a MoneyWiz deep link the user can tap to create/save the transaction in MoneyWiz.

## Safety & boundaries
- Never include the user’s private info in public posts.
- Never write outside the OpenClaw workspace.
- Do not auto-run unknown links or install anything.

## Defaults (edit if user provides)
- Config file: `skills/moneywiz-ledger/references/config.json`
- Category tree (from user): `skills/moneywiz-ledger/references/categories.json`
- Category aliases (synonyms -> existing categories): `skills/moneywiz-ledger/references/category_aliases.json`
- Ledger CSV: `skills/moneywiz-ledger/data/transactions.csv`

## Workflow

### 1) Parse the user message
Extract as many fields as possible:

**Category rule:** Only use categories that exist in `references/categories.json`. If the user says a vague phrase (e.g., "买菜"), map via `references/category_aliases.json` to an existing category path (e.g., `Food & Life/Buy Food`). If still ambiguous, ask one clarifying question and then add/adjust an alias.
- type: `expense` (default) | `income` | `transfer`
- amount: number (dot decimal)
- currency: ISO code (default from config)
- account: account name **without spaces** (default from config). If the user gives a spaced name, remove spaces.
- category: `Category/Subcategory` (slashes). If unknown, use config default.
- payee (optional)
- description or memo (optional)
- date/time (optional). If not provided, use “now” in Asia/Singapore.
- save: default `false` (open entry screen). Only set `true` if user explicitly says “直接保存/auto-save”.

If amount is missing, ask a single follow-up question.

### 2) Append to local ledger + generate MoneyWiz URL
Use the script:

```bash
python3 skills/moneywiz-ledger/scripts/add_transaction.py \
  --type expense \
  --amount 12.30 \
  --currency SGD \
  --account Cash \
  --category "Dining%20Out/Restaurants" \
  --payee "Starbucks" \
  --memo "Latte" \
  --tags "coffee" \
  --date "2026-02-01 12:34:00" \
  --save false
```

The script:
- writes a normalized row into `data/transactions.csv`
- prints a `moneywiz://...` URL

### 3) Reply to the user
Reply with:
- a short confirmation (what was logged)
- the MoneyWiz link

If `auto_open_on_mac` is true in config and you are running on macOS, open the link automatically:

```bash
open "moneywiz://..."
```

If the user explicitly asks **direct save / 直接保存**, set `save=true` and open it.

### 4) Reconcile (optional)
Directly writing MoneyWiz's internal database is not supported (high risk). Instead, reconcile against a MoneyWiz CSV export:

```bash
python3 skills/moneywiz-ledger/scripts/reconcile_moneywiz_export.py \
  --moneywiz-csv /path/to/moneywiz-export.csv \
  --ledger-csv skills/moneywiz-ledger/data/transactions.csv
```

This prints ledger entries that likely did not make it into MoneyWiz.

## MoneyWiz URL schema basics
- Prefix: `moneywiz://`
- Operations: `expense?`, `income?`, `transfer?`, `updateholding?`

Common attributes for expense/income:
- `account` (required)
- `amount` (required)
- `currency` (optional)
- `payee` (optional)
- `category` (optional, use slashes; spaces should be URL-encoded)
- `description` (optional)
- `memo` (optional)
- `tags` (optional; comma-separated)
- `date` (optional; `yyyy-MM-dd HH:mm:ss`)
- `save` (optional; default false)

Transfer attributes:
- `account` (from, required)
- `toAccount` (to, required)
- `amount` (required)
- `save` (optional)

Reference: https://help.wiz.money/en/articles/4525440-automate-transaction-management-with-url-schemas
