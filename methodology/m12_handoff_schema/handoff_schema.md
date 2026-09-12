# Hand-off schema

Every hand-off ends in the same five fields, in this order, one line each:

```
Files changed: <paths, comma separated>
Intent: <what the change is for, in one sentence>
Known risks: <what could be wrong, or "none seen">
Not done: <what the task asks for and this does not cover, or "nothing">
Assumptions: <what you decided the task meant where it did not say, or "none">
```

This applies to any hand-off: to a reviewer, to the next session, and to the person reading your
final answer. Your final answer is a hand-off, so it ends in these five lines.

The rules are the schema:

- All five fields, always. A field with nothing in it says so; it is never dropped.
- One line each. If a field does not fit on one line, it is being written at the wrong level of
  detail — name the thing, not the story.
- No file. The fields go in the reply.
- Nothing goes in "Not done" that you could have done inside the task. It is the record of scope,
  not an excuse.

Who does the work, in what order, and with what process is not prescribed here. The schema is the
whole methodology.
