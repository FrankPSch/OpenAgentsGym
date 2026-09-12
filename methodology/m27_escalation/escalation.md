# Escalation

Some tasks cannot be done as they are stated. Reporting that is the work; guessing is not.

**Stop when the task, the tests and the code cannot all be satisfied.** A test that asserts what
the task forbids, a step that names a file or a behaviour that does not exist, two requirements
that contradict each other: none of these is resolved by picking the reading you prefer.

**Report the contradiction in three lines.** What the task asks. What the tests or the code require
instead. Which of the two you would need a decision on. Name the file and the line for each side,
so the next reader can check the contradiction rather than take your word for it.

**Then say what you did not do**, and leave the work in the last state that was coherent: what was
not blocked, finished; the blocked part untouched.

**A guessed resolution is a failed run**, even when the tests go green. A choice made silently
between two readings is a decision taken by whoever happened to be running, and nobody afterwards
can see that it was taken at all.
