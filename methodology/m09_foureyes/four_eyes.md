# Four eyes

Nothing you wrote is finished until a second pair of eyes has read it. The reviewer is a separate
agent with a fresh context — hand the review to whatever delegation or sub-agent facility your tool
provides; do not review in your own context. It reviews blind: it is given the task and the diff,
never your reasoning, your plan or your justification.

1. Implement the task.
2. Produce the diff of every file you changed or added against its original state.
3. Spawn the reviewer with exactly two things: the task text and that diff. Do not tell it what you
   were trying to do, what you considered, or what you think is fine. If it cannot see a problem in
   the diff, the problem is not visible to a reader either — that is the point of the exercise.
4. The reviewer writes its findings to `REVIEW.md` in the project_workspace root, one per line, each opening
   with a Conventional Comments label:
   `issue:`, `nitpick:`, `question:`, `praise:`.
   The reviewer reviews; it never edits code.
5. Every `issue:` blocks. Fix all of them, then append one line per issue to `REVIEW.md` saying what
   changed. `nitpick:` and `question:` do not block and are left unaddressed unless fixing them is
   free.
6. Run the number of rounds stated in the entry file, and no more. Each round is one fresh
   reviewer on the diff as it then stands; do not re-review your own fixes beyond that number, and
   do not spawn a reviewer the count does not allow.

If the reviewer finds nothing, it writes `praise: no issues found` and you stop.
