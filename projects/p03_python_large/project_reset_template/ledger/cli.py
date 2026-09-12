"""Command line entry point: read a ledger file, print the report."""

from ledger.parse import parse_lines
from ledger.report import aggregate, format_report
from ledger.rules import DEFAULT_RULES


def main(argv):
    """Print the report for the file named in argv[0]; return the process exit code."""
    raise NotImplementedError
