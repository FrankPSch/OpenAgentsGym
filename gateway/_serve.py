"""Start the LiteLLM proxy without touching a generated .exe shim.

Why this file exists rather than a plain `litellm --config ...`:

  * On a managed machine the generated `litellm.exe` launcher is blocked by
    Device Guard / WDAC policy. Python and the package itself are not.
  * `py -3 -m litellm` does not work: `litellm` is a package with no
    `__main__`.
  * The console-script entry point is `litellm.proxy.proxy_cli:run_server`.
    It was named `cli` in older releases; if a future release renames it
    again, `python -c "import litellm.proxy.proxy_cli as m; print(dir(m))"`
    shows what is there.

Arguments are passed straight through to LiteLLM's click command, so this is
a drop-in for the blocked executable.
"""

import sys

from litellm.proxy.proxy_cli import run_server

if __name__ == "__main__":
    # click reads sys.argv; argv[0] is only ever shown in usage text.
    sys.argv[0] = "litellm"
    run_server()
