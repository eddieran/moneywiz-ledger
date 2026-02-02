# moneywiz-ledger

An OpenClaw skill to:
- append a local ledger row (CSV) for each transaction
- generate a `moneywiz://...` URL (MoneyWiz URL Scheme) to create/save the transaction in the MoneyWiz app

This repo is designed to be **public** and **privacy-safe**.

## Privacy model (important)
This repo **must not** contain any personal finance data.

Ignored by git:
- `data/transactions.csv` (your actual transactions)
- `references/config.local.json` (your personal defaults: account names, etc.)
- `references/categories.json` and `references/category_aliases.json` (your personal taxonomy / aliases)

Included in git:
- `references/config.json` (safe defaults)
- `references/*.example.json` templates you can copy

## Setup
### 1) Install / use inside OpenClaw workspace
This skill can live as a standalone repo (recommended) and be included in your OpenClaw workspace as a submodule.

### 2) Create local config (private)
Copy the example and edit it:

```bash
cp references/config.example.json references/config.local.json
```

### 3) Create your own categories (private)
Copy examples and edit them:

```bash
cp references/categories.example.json references/categories.json
cp references/category_aliases.example.json references/category_aliases.json
```

## Usage
Generate a transaction + auto-save in MoneyWiz:

```bash
python3 scripts/add_transaction.py \
  --type expense \
  --amount 12.30 \
  --currency SGD \
  --account Cash \
  --category "Food & Life/Restaurant" \
  --payee "Example Restaurant" \
  --memo "Dinner" \
  --date "2026-02-01 19:00:00" \
  --save true
```

The script:
- appends to `data/transactions.csv`
- prints a `moneywiz://...` URL

## Notes
- Research/utility tool only.
- Do not commit your `*.local.json` or ledger CSV.
