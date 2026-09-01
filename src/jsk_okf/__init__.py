"""jsk-okf: the career-bundle toolchain behind the Job Seeker Skill.

One CLI - `okf` - over a bundle of plain Markdown concepts: compile it to a record,
write to it a verb at a time, render a resume, and run every gate that decides whether
the result is safe to send.

    okf doctor                  what works on this machine
    okf new PATH --name NAME    scaffold a bundle
    okf compile BUNDLE          the record everything downstream reads
    okf validate TARGET         a bundle, or a record
    okf render RECORD --out D   one record to a PDF and plain text
    okf check FILE              the parse gate and the prose gate
    okf gates DIR --view ID     the record, parse and prose gates over one render
    okf <noun> <verb>           every change to a bundle - see `okf --help`

The modules are the documented API and are importable individually; each one that has
a CLI also runs as `python -m jsk_okf.<module>`. `cli.py` is a convenience layer over
them and never the only way in.

Dependencies are deliberately close to zero and every one is optional, imported at the
point of use rather than here: `pyyaml` to read a bundle, `pymupdf` to read a PDF,
`jsonschema` for full record validation. A bare Python runs the write layer, the
compile, the prose gate and the `.txt` parse gate - which is what makes `okf doctor`
able to report on a machine before anything is installed on it.
"""

__version__ = "3.0.0.dev0"

__all__ = ["__version__"]
