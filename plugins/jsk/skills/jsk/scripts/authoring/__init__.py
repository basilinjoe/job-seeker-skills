"""The write half of okf: typed commands that change a bundle.

Every module here obeys one split. schema.py judges and never formats;
concept.py formats and never judges. A validation rule inside a formatter, or a
quoting decision inside the schema, is the seam being crossed.
"""
