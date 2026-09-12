# Relative stop

When to stop is judged against the previous step, not only against the task.

Before each further edit, look at what the last one changed — the files it touched, the lines it
added, the lines it removed — and answer one question: **did that step add a behaviour the task
requires?**

- It did: the step paid for itself. Continue.
- It did not, but it removed size: it paid for itself. Continue.
- It added size and no required behaviour: that is the drift signal. Stop there. Do not take a
  further step to make the last one worth having.

Drift is per step, not per session. A run measured only against the task keeps finding one more
thing the task could be read to want; a run that measures each step against the one before it runs
out of steps that pay, and that is the stopping point.

**State the comparison.** Your answer names how many steps you took, and what the last one added
and removed. If you stopped on the drift signal, say which step it was.
