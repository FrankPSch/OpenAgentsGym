# The cycle

Work moves through five stages, in order. A stage is left only when its condition holds; say which
stage you are in when you report.

| stage | left when |
|---|---|
| **plan** | you can name what the task asks for, which files change, and what deliberately does not change |
| **build** | the smallest change that satisfies the task exists |
| **verify** | the test command has been **run** and its output pasted — your own reading of the code is not a verification |
| **review** | the reviewer has returned findings and every `issue:` is fixed |
| **report** | the hand-off is written and every unrun check is named |

**A failed check is a comprehension failure first.** When a test fails, re-read the task before you
change the code: a task read wrongly produces code that passes and is wrong.

**Only four things block: it crashes, it corrupts data, it edits the tests, or a number it reports
is wrong.** Everything else is a list item — `should` if it changes a decision, `note` if it changes
none. A `note` is filed in the hand-off, not argued.

**Halt after three.** If the same check fails three times against three different fixes, stop
changing it. Say what fails, what you tried, and finish whatever is independent of it.

**Never trim the honesty.** The last line of your report names every check that could not run, one
line each. An absent line reads as a check nobody ran.
