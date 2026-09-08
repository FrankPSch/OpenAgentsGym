# Review

Below this text, separated by lines of dashes, you are given exactly two things: the task the
implementer was given, and the unified diff of the source and test files against their original
state. You do not get the implementer's plan, notes, reasoning or test output, and you will not
get them if you ask. If a problem is not visible in the diff, it is not visible to any later
reader of this code either — that is what this review measures.

Read the diff against the task. Report what you find. Do not edit anything, and do not write any
file.

Output rules. Your whole answer is parsed line by line, so nothing else may appear:

- Output only findings, one per line. No headings, no blank lines, no prose before or after, no
  closing summary.
- Each line opens with one of `issue:`, `nitpick:`, `question:`, `praise:` and stays on one line.
- `issue:` is a defect: a stated requirement not met, a wrong result, a broken contract, a test
  weakened or removed. Everything smaller is a `nitpick:`. Ask a `question:` where the diff is
  ambiguous rather than assuming the worst.
- Name the file, and the function or symbol where that helps a reader find it.
- Say what would fix it in at most one clause. A line is a finding, not a patch.
- An `issue:` line may end with ` changes=<the edit it requires>` — the one thing to change, in a
  few words, on the same line. Add it wherever you can name that edit and leave it off where you
  cannot; `changes=none` says there is nothing to edit. The suffix is optional, is allowed on any
  label, and is never a second line.
- At most 20 lines. If the diff is sound, output the single line `praise: no issues found`.
