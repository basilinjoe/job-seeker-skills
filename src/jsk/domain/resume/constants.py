"""The limits a resume is built under, named once for the builder, export and the letter check."""

# The floor a short file sets, as a rank: a bullet renders when its provenance ranks at or
# above it. Unknown provenance ranks lowest.
PROVENANCE_RANK = {"confirmed": 3, "inferred": 2, "needs-verification": 1, "disputed": 0}

# A skills row longer than this stops being scanned. The ATS render of the Everforth
# application filled 45% of page 1 with its skills block while page 2 was half empty;
# ten names is what a recruiter reads in one pass of a row.
MAX_SKILLS_PER_ROW = 10
