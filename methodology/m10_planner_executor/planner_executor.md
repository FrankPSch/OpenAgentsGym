# Planner and executor

You work as two roles in one session, in this order, and you do not start the second before the
first is finished.

**Planner.** Before you change anything, write the plan as a numbered list in your reply. Do not
write it to a file. The list states, in order:

1. every file you are going to touch, by path,
2. what changes in each one, in one line,
3. the order you will do them in.

A step that names no file is not a step. If the task does not tell you enough to name the files,
say what is missing and plan against the reading the tests support.

**Executor.** Implement exactly that list, in that order, and nothing beside it. A file that is not
in the plan is not touched. When you finish the last step, stop.

Plans meet code and break. When you deviate — a step dropped, a step added, a file touched that the
plan did not name — state it in your final answer: which step, and why. An unstated deviation is
the failure this methodology exists to prevent; a stated one is a normal outcome.

Do not delegate either role to a subagent. Both are you.
