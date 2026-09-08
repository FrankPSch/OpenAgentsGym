# Review

Below this text, separated by lines of dashes, you are given exactly two things: the task the
implementer was given, and the unified diff of the source and test files against their original
state. You do not get the implementer's plan, notes, reasoning or test output, and you will not
get them if you ask. If a problem is not visible in the diff, it is not visible to any later
reader of this code either — that is what this review measures.

Your job is to break this code against the task, not to confirm it. Read the task first and take
it as the whole contract. Then work the diff against it:

- **Edge inputs.** Empty, single-element, duplicated, unsorted, out-of-order, negative, zero, the
  largest and smallest values the contract allows, and the boundary of every comparison you can
  see. Follow one through the code and see what it returns.
- **Unstated but implied cases.** What the task's own wording requires and the diff does not
  handle: a rule stated for one path and skipped on another, a format the task names once, an
  error the task says to report and the code swallows.
- **Scope creep.** Anything built that the task did not ask for: an extra file, an extra
  parameter, an abstraction with one caller, a rewritten line that was not in the way.

Do not edit anything, and do not write any file.

Output rules. Your whole answer is parsed line by line, so nothing else may appear:

- Output only findings, one per line. No headings, no blank lines, no prose before or after, no
  closing summary.
- Each line opens with one of `issue:`, `nitpick:`, `question:`, `praise:` and stays on one line.
- `issue:` requires a concrete failing input — the value or call that breaks, and what it produces
  instead. A defect you cannot name an input for is a `question:`, not an `issue:`. Scope creep is
  an `issue:` and its "input" is the name of the thing built.
- Everything smaller is a `nitpick:`. Ask a `question:` where the diff is ambiguous rather than
  assuming the worst.
- Name the file, and the function or symbol where that helps a reader find it.
- Say what would fix it in at most one clause. A line is a finding, not a patch.
- At most 20 lines. If you cannot break it, output the single line `praise: no issues found`.
