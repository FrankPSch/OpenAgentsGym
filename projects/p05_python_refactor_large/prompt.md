# p05_python_refactor_large

## Task

Simplify `pricing.py` without changing its behaviour. `test_pricing.py` passes today and must
still pass when you are done.

## Specification

The public interface and the module constants it reads stay as they are: `subtotal(items)`,
`discount_rate(customer_type)`, `shipping_cost(net, express)`, `total(items,
customer_type="none", express=False)`. Rounding, the free-shipping threshold and the order of
discount, shipping and tax are behaviour: every input keeps the result it returns today, to the
cent.

It is bloated — a wrapper class around a dict, a counting loop for a multiplication, an if/elif
chain over a lookup table already in the module, two identical rounding helpers, and `else`
branches that only re-state the fall-through.

It must also get smaller: done means the golden tests still green *and* fewer source lines than
you started with.

## Files

Change `pricing.py` and keep everything in it: a second module is not a simplification, and the
score counts every non-test file. `test_pricing.py` is the visible suite; read it, do not modify
it.

## Verification

Run `python -m pytest -q` before you finish; the harness runs the full tier afterwards.
