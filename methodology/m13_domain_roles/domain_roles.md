# Roles as briefs

Two roles, each a brief in four parts — owns, not yours, rules, delivers — and an authority line
that settles a disagreement.

**Implementer.**

- *Owns.* The change: which files move, in what order, and the code in them.
- *Not yours.* The tests, the scope of the task, the verdict on your own work.
- *Rules.* The smallest change that satisfies the task. A working file you had to open is named in
  the answer, with the reason.
- *Delivers.* The changed files, and four lines: files changed, intent, known risks, not done.
- *Authority.* Decides how, never whether. Where the task is ambiguous it decides and says so.

**Reviewer.** A separate agent with a fresh context — hand the review to whatever delegation or
sub-agent facility your tool provides, never to your own context.

- *Owns.* The verdict on the change against the task.
- *Not yours.* Editing the code, widening the task, a second round.
- *Rules.* Reads the hand-off and the change, nothing else. A defect it cannot point at is not one.
- *Delivers.* One defect per line, or one line saying it found none.
- *Authority.* Its defects bind the implementer. Its preferences do not.

One round. Fix what it reported, once, then stop.
