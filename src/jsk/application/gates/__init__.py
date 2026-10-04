"""The four mechanical gates, and the one that is not mechanical.

A resume passes five gates before anybody sends it. Four of them are here and run as
the resume_check tool, each one's output printed verbatim:

    record gate   record.py   is the short resume.json sound, and does every number in a
                              bullet it selects trace to a current metric version in the
                              career? Runs before anything is rendered, because a defect
                              there becomes a defect in every file at once.
    parse gate    ats.py      will an ATS read the PDF without mangling it?
    prose gate    prose.py    does the writing obey the rules a parser cannot see - third
                              person, unresolved placeholders, a sentence that stops before
                              its object?
    layout gate   layout.py   tofu, a face the template did not declare, a heading stranded
                              at a page foot, a date out of its column, the wrong paper.

**The fifth gate is a person opening the PDF and reading every page, and nothing here can
run it.** The resume_check tool closes by saying so rather than exiting 0 and letting a caller
infer that a resume has been checked: a gate that overstates what it covers teaches people
to stop reading the ones that do not.

The rules are domain/gates/; each use case here takes its readers and the career's reads as
parameters and returns a result, and adapters/entry/gates/ prints it. The resume_check tool runs
all four in one interpreter, and dispatch.call_gate contains a gate that raised where it
should have returned a verdict.
"""
