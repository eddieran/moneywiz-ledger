# moneywiz-ledger

OpenClaw skill for fast personal bookkeeping with **MoneyWiz**.

✅ This project is built for and explicitly supports the **MoneyWiz product by Wiz**:
- Product site: https://www.wiz.money/
- URL Scheme docs: https://help.wiz.money/en/articles/4525440-automate-transaction-management-with-url-schemas

It converts natural-language transaction input (text/voice transcript) into a `moneywiz://...` deep link, so the transaction can be created in MoneyWiz.

## Search keywords

MoneyWiz, wiz.money, MoneyWiz URL Scheme, OpenClaw skill, personal finance automation, bookkeeping, expense tracking, income tracking, Carousell income, iOS finance app, macOS finance app

中文关键词：记账, 收入分类, 支出分类, MoneyWiz 自动记账, URL Scheme, 闲置收入, 语音记账

---

## What this skill does

- Parse transaction intent from chat-like input
- Support transaction types: `expense` / `income` / `transfer`
- Resolve categories via:
  - exact match
  - alias mapping
  - keyword inference
  - type-specific fallback
- Generate MoneyWiz URL Scheme links:
  - `moneywiz://expense?...`
  - `moneywiz://income?...`
  - `moneywiz://transfer?...`
- Optionally auto-open the deep link on macOS

## Income category support (important)

The skill supports dedicated income categories (not just expense categories), including examples like:

- `Other incoming`
- `Salary`
- `Investments`
- `Split bill`
- `Dividends`
- `Carousell`
- `Stable Investment`
- `Tax Refund`
- `Interest`
- `Refund`
- `Annual Bonus`
- `Other Bonus`
- `Reward`
- `Company Benefit`
- `Debit/Deposit`
- `Cashback`

Defaults are type-aware:
- expense → `Shopping/Other`
- income → `Other incoming`

## Privacy model

This repo is intended to stay public-safe. Personal finance data should remain local.

Ignored by git:
- `references/config.local.json` (private defaults: account names, etc.)
- `references/categories.json` and `references/category_aliases.json` (personal taxonomy/aliases)

Safe to keep in git:
- `references/config.json`
- `references/*.example.json`
- scripts and skill docs

## Setup

1) Create private local config:

```bash
cp references/config.example.json references/config.local.json
```

2) (Optional) Create private category files:

```bash
cp references/categories.example.json references/categories.json
cp references/category_aliases.example.json references/category_aliases.json
```

## Usage

Example: create an income transaction for MoneyWiz

```bash
python3 scripts/add_transaction.py \
  --type income \
  --amount 25 \
  --currency SGD \
  --category "卖闲置" \
  --payee "Carousell" \
  --memo "Sold IKEA Alex drawer" \
  --date "2026-02-12 10:02:00"
```

Output:
- prints a `moneywiz://...` URL
- optionally opens MoneyWiz directly on macOS (if enabled in config)

---

If you use MoneyWiz and want chat-first bookkeeping, this skill is designed exactly for that workflow.