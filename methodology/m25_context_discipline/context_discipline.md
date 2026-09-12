# Context discipline

What you read is a cost like anything else you spend. This is the reading order.

**Before the first edit, read three things and stop.** The task. The test files it names. The
source files those tests import. Nothing else: not the neighbouring module, not the rest of the
package, not a file you expect to be interesting.

**Read a file once, whole.** A file read in fragments is read three times over, and a file read
twice is paid for twice. If you need one function, you still read the file it is in, once.

**Re-read only after a failed test, and only what the failure names.** A failure is the one event
that makes an already-read file untrustworthy. Nothing else is: a file you have not edited and no
test has accused has not changed since you read it, and opening it again buys nothing.

**Summarise once, before the final answer** — what you changed, what the tests said, and what you
did not read and may therefore have missed. Not per step: a running summary is the same context
paid for again on every turn.
