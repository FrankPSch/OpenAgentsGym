# Syntax gate

No file leaves your hands until the interpreter has read it.

**Every time you finish editing a file, compile it before you do anything else.** Run
`python -m py_compile <file>` on the file you just wrote. It prints nothing when the file is
valid; any output at all is an error to fix now, not later. Editing a second file while the
first one does not compile is how a session ends with a broken file nobody looked at again.

**Before you stop, compile everything you touched, in one command.** List the files you changed
and run `python -m py_compile` over that list. A single unterminated string, one stray indent or
a line continuation with a character after it is enough to make the whole module unimportable —
and an unimportable module fails every test in the project at once, including the tests that
have nothing to do with your change. A run in that state scores as if you had written nothing,
whatever else you got right.

**Then run the suite: `python -m pytest -q`.** Compiling proves the file parses; it does not
prove the module imports. A name that does not exist, an import of something you did not write,
a call at module level that raises — each is invisible to `py_compile` and fatal to every test in
the file. If pytest reports a collection error rather than a test failure, that is this class of
problem: fix it before you look at any failing assertion, because until it is fixed the
assertions were never reached.

**Do not end your turn on a file that does not compile or a suite that does not collect.** If you
are out of time or stuck, leave the file in the last state that compiled and say in your answer
what you were part-way through. A working file and an honest note are worth more than a broken
file and a plan.

**State it.** Your answer names the files you compiled and reports the last line of the pytest
run — the counts, as printed. If either check was not run, say so; do not describe a check you
did not perform.
