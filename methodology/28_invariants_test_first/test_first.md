# Test first

The test for a change is written before the change.

**Before you touch a source file, write or extend a test that fails for the reason the task
names.** One test per behaviour the task asks for. Run it and watch it fail: a test that is green
before the code exists is testing something else.

**Then write the smallest code that turns it green**, and run the whole suite before you start the
next behaviour. One behaviour at a time — not three tests, then three implementations.

**Your own tests are allowed and are not scored.** That is stated plainly because it changes what
they are for. The suite the project ships is the contract: it is what decides whether the task was
done, and it is the suite that is read after you stop, whatever you leave beside it. A test you
write is a tool for writing the code, not evidence about it. Weakening, deleting or narrowing a
shipped test is a failed run, never a shortcut.

**State it.** Your answer lists the tests you wrote and, for each, the behaviour it pins.
