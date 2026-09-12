# Roles

You work as the **implementer**. The **reviewer** is a separate agent with a fresh context — hand the
review to whatever delegation or sub-agent facility your tool provides; do not review in your own
context.

1. Implement the task.
2. When you believe the task is done, hand off to the reviewer. The handoff states four fields and
   nothing else:
   - files changed
   - intent
   - known risks
   - what was not done
3. The reviewer reads the diff against the task and reports defects it finds. It reviews; it does not
   edit.
4. Fix the defects the reviewer reported, once. Then stop.

One review round only. Do not hand off a second time, and do not spawn any other subagent.
