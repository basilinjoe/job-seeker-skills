"""The three mechanical gates, and the one that is not mechanical.

A resume passes four gates before anybody sends it. Three of them are here and run as
`jsk gates <out-dir>`, each one's output printed verbatim:

    record gate   record.py          is the short resume.json sound, and does every
                                     number in a bullet it selects trace to a current
                                     metric version in career/kb.ttl? Runs before
                                     anything is rendered, because a defect there
                                     becomes a defect in every file at once.
    parse gate    check_ats.py       will an ATS read the PDF without mangling it?
    prose gate    check_prose.py     does the writing obey the rules a parser cannot
                                     see - third person, unresolved placeholders, a
                                     sentence that stops before its object?

**The fourth gate is a person opening the PDF and reading every page, and nothing in
this package can run it.** `jsk gates` closes by saying so rather than exiting 0 and
letting a caller infer that a resume has been checked. That is the whole reason the
other three are worth having: a gate that overstates what it covers teaches people to
stop reading the ones that do not.

Every module here exposes `main(argv)` and runs as `python -m jsk.gates.<name>`,
because `jsk gates` calls all three in one interpreter rather than spawning four - and
a gate that raised where it should have returned a verdict would take the other two
down with it. `cli.call_gate` is where that is contained.

`report.py` (Report, show) and `numbers.py` (the numeral detector and the number check
over graph bullets) are shared: `check_prose` borrows `numbers.numerals` rather than
growing a second numeral detector - the first one already knows that a year, a glued
designator like `p95` and a standard's number are not claims, and a detector without
those exclusions reports a resume as unquantified because it mentions 2019.
"""

__all__ = ["check_ats", "check_prose", "numbers", "record", "report"]
