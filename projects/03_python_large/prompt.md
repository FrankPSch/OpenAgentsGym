# 03_python_large

## Task

Implement the `ledger` package. Every function currently raises `NotImplementedError`.

## Specification

A ledger file holds one transaction per line: `YYYY-MM-DD;description;amount`. Blank lines and
lines whose first non-space character is `#` are ignored.

`ledger/parse.py`

- `parse_amount(text)` → float. Amounts come in two conventions and may be wrapped in parentheses
  to mark a negative: `1.234,56` and `1,234.56` are both `1234.56`, `(12.50)` is `-12.50`, a leading
  `-` also marks a negative. Rule for the separators: the last `.` or `,` in the digits is the
  decimal separator, unless exactly three digits follow it, in which case every `.` and `,` is a
  group separator — so `1.234` and `1,234` are both `1234.0`. Anything that is not an amount raises
  `ValueError`.
- `parse_lines(lines)` → `(transactions, errors)`. A transaction is the `Transaction` namedtuple
  already defined in the module: a `datetime.date`, the description stripped of surrounding
  whitespace, and the amount. A malformed line — wrong field count, unparsable date, unparsable
  amount — is skipped, not fatal: it is collected in `errors`, stripped, in the order it appeared.

`ledger/rules.py`

- `categorise(description, rules=None, fallback="other")` → the category of the **first** rule whose
  keyword occurs in the description, compared case-insensitively as a substring; the fallback when
  none matches. `rules` is a sequence of `(keyword, category)` and `None` means `DEFAULT_RULES`.
  Rule order is the precedence.

`ledger/report.py`

- `round_half_away(value, places=2)` → float, rounded **half away from zero**. Python's built-in
  `round()` rounds half to even and will not satisfy this.
- `aggregate(transactions, rules=None)` → `{(month, category): total}` with the month written
  `YYYY-MM`, each total the sum of its transactions rounded to 2 decimals by the rule above.
- `format_report(totals)` → one `YYYY-MM;category;amount` line per entry, the amount with 2
  decimals, sorted by month then category, joined by newlines with no trailing newline. An empty
  aggregate renders as the empty string.

`ledger/cli.py`

- `main(argv)` → exit code. `argv[0]` is the path of a ledger file. Prints the report; if lines were
  skipped, prints `skipped N malformed line(s)` after it. Returns 0.

## Files

Change the four modules under `ledger/`. `test_ledger.py` is the visible suite; read it, do not modify it.

## Verification

Run `python -m pytest -q` before you finish; the harness runs the full tier afterwards.

## Work order

1. Read this spec and `test_ledger.py`.
2. Implement `parse_amount`, both locale conventions and the parenthesised negative.
3. Implement `parse_lines`: skip blank and comment lines, collect the malformed ones.
4. Implement `categorise`: first match wins, then the fallback.
5. Implement `aggregate` over month and category.
6. Implement `round_half_away` and apply it to the category totals.
7. Implement `format_report`.
8. Wire `main(argv)` in `cli.py` to read the file and print the report.
9. Run the full test suite.
10. Report what was done and what was not.
