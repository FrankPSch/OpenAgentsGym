# Clean restraint

Improve maintainability with a small, reviewable diff. Externally observable behaviour is preserved
unless the task asks for a change to it.

**Material issues, evidenced rather than felt:** unclear domain names, mixed responsibilities,
needlessly hard control or data flow, hidden side effects, weak boundary validation, lost error
context, unstable duplication, tests that miss observable behaviour or overfit the implementation.

**The prohibitions.**

- No arbitrary function, class or file length limit.
- No one-use wrapper unless it names a real concept or isolates real complexity.
- No interface, factory, base class, helper, pattern or dependency without a concrete current need.
- Duplication is preferable to the wrong abstraction; local clarity beats speculative abstraction.
- Public interfaces, stored formats, concurrency semantics, security properties and material
  performance stay as they are unless the task names them.
- Errors stay explicit: keep the cause and context, never swallow a failure.
- Comments carry rationale, invariants or trade-offs, not a paraphrase of the code.
- Tests assert observable behaviour; a brittle test may not distort the design.
- A clean-code pass is not permission for a broad rewrite.

**Make the smallest coherent change**; leave unrelated tidying out.
