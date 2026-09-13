"""Unit-test package marker.

Without this file, a bare `python3 -m unittest discover` from the repository root
finds nothing (`Ran 0 tests`, exit 0) because `tests/` is not an importable
package — a contributor running the conventional command gets a false green. With
it, both the conventional root command and the explicit CI command
(`python3 -m unittest discover -s tests`, kept as defense in depth) run the same
suite.
"""
