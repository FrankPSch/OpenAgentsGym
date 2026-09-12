# Finding schema

You work as the **implementer**. The **reviewer** is a separate agent with a fresh context — hand
the review to whatever delegation or sub-agent facility your tool provides; do not review in your
own context. It is given the task and the change, and nothing else. One round.

Every finding is one line, and every line carries the same five fields in the same order:

    <label>: severity=<blocks|should|note> claim=<one sentence> evidence=<where>
    changes=<what to edit> confidence=<high|medium|low>

- The label is `issue:`, `nitpick:`, `question:` or `praise:`.
- `evidence` is a file and a symbol, or the input that fails. Never an opinion.
- `changes` names the code change the finding requires, or `none`.

**`changes` decides the label.** A finding whose `changes` is `none` changes nothing and is never
an `issue:` — it is a `nitpick:` or a `question:`, whatever its severity says. A finding that names
a code change is an `issue:`, whatever its severity says.

A claim with no evidence is a `question:`, not an `issue:`. Ask rather than assume the worst.

Fix every `issue:`, once. Then stop.
