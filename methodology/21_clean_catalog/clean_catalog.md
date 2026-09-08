# Clean catalog

Rules in families. Every finding cites a rule ID, so it can be argued with.

- **C, comments.** No metadata, noise or commented-out code; only real value.
- **E, environment.** Build and test in one command; no fragile setup.
- **F, functions.** Few arguments, no output or flag arguments, dead code deleted.
- **G, design.** One abstraction level and one responsibility per unit, named constants,
  encapsulated boundaries and conditionals.
- **N, names.** Descriptive, unambiguous, scaled to scope, side effects named.
- **P, hygiene.** No wildcard imports, enumerations over magic values, public type hints.
- **T, tests.** Failure-prone behaviour, boundaries, non-happy paths; fast and diagnostic.
- **S** security and **PF** performance, local: secrets redacted, input bounded, no per-item call
  in a loop.

**Strict.** Every rule, every time, no technical debt; if the task cannot be done that way, say so
rather than waive one. Leave every file you touch cleaner than you found it.

**Run the whole unit suite after every code change**, not the tests near it: a small edit has
non-local reach, and diff size is not evidence of safety. Cover the non-happy path — invalid input,
empty data, boundaries, exceptions, timeouts.

**A finding names a rule ID and a line.** Without both it is an observation.
