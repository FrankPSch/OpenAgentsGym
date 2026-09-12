Sg. Syntax gate: compile every edited file, then run the suite, before ending the turn.
Written against an observed failure, not a hypothesis. On 2026-09-12 three local runs scored
0.0000 while writing 51 to 147 diff lines, each because one file would not parse — an
unterminated triple-quoted string, an unexpected indent, a character after a line continuation.
Two further runs parsed cleanly and still collected nothing, which is why the gate names the
suite as well as the compiler: py_compile cannot see an import-time failure.
Its evidence is res_syntax_ok, res_syntax_error and res_collection_errors, which separate a
broken file from wrong code — both read 0.0000 in res_score alone. Read against m00_empty on the
same model and project: the models already had a shell and still shipped unparseable files, so
what is being measured is whether instructing self-verification closes that gap, not whether the
capability exists. A null result is informative here.
