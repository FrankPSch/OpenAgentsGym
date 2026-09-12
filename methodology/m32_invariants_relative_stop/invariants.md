# Invariants

True at the end of every run, whatever the task says. Each is phrased so a reader can say violated
or not.

- **I1** No test file is edited, renamed, weakened or deleted. The tests are the specification.
- **I2** No dependency is added. What the project already declares is what you have.
- **I3** A public signature — module, class, function, parameter, return shape — is unchanged
  unless the task names that signature.
- **I4** No behaviour moves beyond what the task asks for. A fix that also tunes cannot be
  verified: the check has two reasons to move.
- **I5** Nothing is deleted that the task did not ask to have deleted.

A task that appears to require breaking one of these has been misread, or is wrong. Say which, in
one line, and stop.

**What a change costs.** Before you make one, read its row.

| you change… | it costs… |
|---|---|
| a working file, to add something to it | every later reader of that file, and the claim that its parts are separable |
| a public signature | every caller, every test that names it, and every document that quotes it |
| a file, a flag or an abstraction added | paid by the next change, not this one; the only refund is a deletion |
