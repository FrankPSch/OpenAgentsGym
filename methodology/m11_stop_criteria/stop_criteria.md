# Stop criteria

When to stop is stated here, not left to judgement.

**Stop when the stated task's tests pass.** Run them with the project's own interpreter:
`python -m pytest -q`. Green on the task's tests is the end of the work, not the beginning of a
tidy-up.

**Never add a file, a function, a parameter or a dependency that neither the task nor this
methodology asks for.** Not a helper you expect to be useful, not a configuration knob, not a
second implementation behind a flag, not a test that was not asked for. What the task and this
methodology name between them is the whole list.

**If you believe something is missing, state it in your answer instead of building it.** A missing
case, a bug you found beside the task, an obvious next step: one line each in the answer. The next
session can act on a sentence; it cannot un-write a file.

**A run that touches more files than the task and this methodology name is a failed run** — even
if the tests are green. Before you stop, list the files you changed and check that list against
them. If it is longer, say which file was extra and why.
