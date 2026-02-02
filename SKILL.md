---
name: moneywiz-ledger
description: Record personal expenses/income from chat (often transcribed voice) into a local ledger and generate a MoneyWiz URL scheme (moneywiz://expense|income|transfer?...) to create the transaction in the MoneyWiz app. Use when the user says they spent/earned/transferred money, asks to log a transaction, wants to "记账/报销/记一笔", or wants a MoneyWiz deep link for transaction creation.
---

# MoneyWiz Ledger (voice → bookkeeping)

Generate MoneyWiz deep links from natural language transaction descriptions.

## Setup

1. Copy `references/config.example.json` to `references/config.local.json`
2. Edit `config.local.json` with your personal settings (account name, currency, etc.)
3. Optionally customize `references/categories.json` and `references/category_aliases.json`

Files in `.gitignore` (won't be committed):
- `references/config.local.json` - your personal config
- `references/categories.json` - your category tree
- `references/category_aliases.json` - your alias mappings

## Workflow

### 1) Parse the user message

Extract fields from natural language:
- **type**: `expense` (default) | `income` | `transfer`
- **amount**: number (required)
- **currency**: ISO code (default from config)
- **account**: account name without spaces (default from config)
- **category**: resolved via aliases or exact match
- **payee** (optional)
- **memo** (optional)
- **date/time** (optional, defaults to now)
- **save**: default from config (usually `true`)

**Category resolution:**
1. Check exact match in `categories.json`
2. Check `category_aliases.json` for common phrases (e.g., "吃饭" → "Food & Life/Restaurant")
3. If still unknown, pass through as-is

If amount is missing, ask for it.

### 2) Generate MoneyWiz URL

```bash
python3 skills/moneywiz-ledger/scripts/add_transaction.py \
  --type expense \
  --amount 10.00 \
  --category "吃饭" \
  --memo "午饭"
```

The script:
- Loads config (config.local.json overrides config.json)
- Resolves category via aliases
- Prints a `moneywiz://...` URL

### 3) Open in MoneyWiz

If `auto_open_on_mac` is true in config and running on macOS:

```bash
open "moneywiz://expense?..."
```

### 4) Reply to user

Short confirmation: what was logged, which category, amount.

## MoneyWiz URL Reference

Prefix: `moneywiz://`

Operations: `expense?`, `income?`, `transfer?`

Common attributes:
- `account` (required) - no spaces
- `amount` (required)
- `currency` (optional)
- `payee` (optional)
- `category` (optional, use slashes, URL-encoded)
- `description` (optional)
- `memo` (optional)
- `tags` (optional, comma-separated)
- `date` (optional, `yyyy-MM-dd HH:mm:ss`)
- `save` (optional, default false in MoneyWiz)

Transfer:
- `account` (from)
- `toAccount` (to)
- `amount`
- `save`

Reference: https://help.wiz.money/en/articles/4525440-automate-transaction-management-with-url-schemas
