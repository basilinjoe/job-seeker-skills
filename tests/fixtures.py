"""Builders and helpers for the jsk tests.

Standard library only, matching the package under test. Every artefact is written
to a caller-supplied temp directory, so nothing lands in the repo and .gitignore's
`*.pdf` rule never comes into it.

`src/` is put on the path here rather than requiring an install, so that
`python -m pytest tests` and `python -m unittest discover -s tests` both work from a
bare checkout - which is what ARCHITECTURE.md promises and what CI relies on.
"""
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
PACKAGE = "jsk"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The modules the tests drive as commands. These are module names, not file paths: a
# module inside a package run as a loose file has no package context, so its own
# `from . import ...` fails on the way in. `run()` invokes them with `-m`.
SCRIPTS = REPO_ROOT / "src" / PACKAGE      # for tests that read a module's source text
CLI = f"{PACKAGE}.cli"
CHECK_ATS = f"{PACKAGE}.adapters.cli.gates.ats"
FIT_PAGES = f"{PACKAGE}.domain.render.fit_levers"

# What the tests drive. DOCTOR is a command, the argv of `python -m jsk ...`. The rest were
# `jsk resume check|render|fit` until 2026-10-04, when those became the resume_check,
# resume_render and resume_fit tools (docs/superpowers/plans/2026-10-04-mcp-first.md): each is
# now the tool's name and the flags it passes, and run() calls the entry point that tool calls,
# in this interpreter, inside the working directory - as the tool runs it inside the workspace.
PARSE_GATE = ("resume_check", "--only", "parse")
PROSE_GATE = ("resume_check", "--only", "prose")
RECORD_GATE = ("resume_check",)
RENDER = ("resume_render",)
FIT = ("resume_fit",)
DOCTOR = (PACKAGE, "doctor", "--quick")

# The documented script name each tool runs through dispatch.call_gate (adapters/mcp/rendering.py);
# resume_check calls adapters/cli/resume.cmd_resume_check instead, which has none.
TOOL_SCRIPTS = {"resume_render": "render_resume.py", "resume_fit": "fit_pages.py"}


def load_script(name):
    """Import one of the package's modules, so its pure functions can be tested directly.

    This used to exec a loose file through `spec_from_file_location`, because the
    scripts were CLIs sitting outside any importable path. They are a package now, so
    an import is an import - and two modules reached the same way are the same object,
    which the file-loading version could not promise.

    A caller may name a module three ways: fully qualified, as a bare stem, or as the
    documented script filename that most of the codebase's comments still use. Which
    module a filename is is `dispatch.module_for`'s answer and not a second copy here -
    that is what `jsk` itself dispatches on, so a module that moves without it being
    updated fails in the CLI before it fails in a test.
    """
    name = str(name)
    if not name.startswith(PACKAGE + "."):
        from jsk.adapters.cli.dispatch import module_for   # noqa: PLC0415 - test helper
        name = module_for(f"{Path(name).stem}.py")
    return importlib.import_module(name)


def source_path(name):
    """Where module `name` (dotted, e.g. `jsk.infra.oxigraph.db`) is defined, relative to SCRIPTS.

    A structure test that names a module by its file stops matching the moment the module
    moves; named by its import path, it follows the move, because the old path is kept as
    an alias of the moved module until every importer is rewritten.
    """
    module = importlib.import_module(name)
    return Path(str(module.__file__)).resolve().relative_to(SCRIPTS.resolve()).as_posix()


def build_text(path, paragraphs=(), trailing=()):
    """Write the extracted-text form of a resume: one paragraph per line.

    This replaces build_docx. Both document gates now read text - check_ats.py
    from the PDF or the .txt, check_prose.py from the .tex or the .txt - so a
    fixture exercising a rule about what a document *says* no longer has to
    synthesise OOXML to say it. The seven rules that needed real OOXML were the
    structural ones, and those are gone: one LaTeX template cannot emit a table
    or a text box, so the check moved to a golden-file test on the template.
    """
    lines = [item if isinstance(item, str) else item[0] for item in paragraphs]
    lines.extend(trailing)
    with open(str(path), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return str(path)


def build_pdf(path, text_lines=(), blank=False):
    """A PDF written directly, for the rules that are about the PDF itself.

    `blank=True` produces a page with no text layer at all - a scan, as far as
    any parser is concerned - which is the case the extractability rule exists
    for and the one no .txt fixture can express.
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    if not blank:
        page.insert_text((72, 72), "\n".join(text_lines), fontsize=11)
    doc.save(str(path))
    doc.close()
    return str(path)


# A resume that satisfies every documented rule, in both normal and --strict mode.
# Guards against the fixes becoming so strict that legitimate documents are blocked.
CLEAN_RESUME = [
    "Jane Doe",
    "Phone: +61 400 123 456 | Email: jane.doe@example.com",
    "Professional Summary",
    "Solution architect who builds the platforms other teams build on.",
    "Technical Skills",
    "Azure, Bicep, Kubernetes, Terraform, Python",
    "Professional Experience",
    "Senior Architect, Acme Corp | Jun 2025 - Present",
    "Owned the migration to event-driven services across six delivery teams.",
    "Architect, Globex | Jan 2018 - May 2025",
    "Cut order-processing latency 62 percent by decomposing a monolithic service.",
    "Lead Engineer, Initech | Mar 2015 - Dec 2017",
    "Ran the delivery team through two platform rewrites.",
    "Education",
    "BSc Computer Science, University of Melbourne, 2014",
]


def resume_with(*replacements, base=None):
    """CLEAN_RESUME with `(old, new)` substitutions applied; new=None deletes the line."""
    lines = list(base if base is not None else CLEAN_RESUME)
    for old, new in replacements:
        idx = lines.index(old)
        if new is None:
            del lines[idx]
        else:
            lines[idx] = new
    return lines


def child_env():
    """An environment where the child interpreter can import the package.

    Without this every `run()` would need the package installed, and the promise that
    the suite works from a bare checkout would quietly stop being true - the tests
    would pass against whatever version happened to be installed instead of the one in
    the working tree, which is the worse of the two failures.
    """
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return env


def run(module, *args):
    """(exit code, combined output) of a command, or of the entry point a tool calls.

    `module` is a module name, a tuple naming a `jsk` command (DOCTOR), or a tuple naming a
    tool and its flags (PARSE_GATE, RENDER, ...). A command runs in a child interpreter, with
    `-m` rather than a file path, because these modules live in a package and their relative
    imports need the package context. A tool's entry point runs in this one (tool_entry).
    """
    if isinstance(module, tuple) and module[0] in ("resume_check", *TOOL_SCRIPTS):
        return tool_entry(module[0], *module[1:], *args)
    command = list(module) if isinstance(module, tuple) else [str(module)]
    proc = subprocess.run(
        [sys.executable, "-m", *command] + [str(a) for a in args],
        capture_output=True, text=True, env=child_env(),
    )
    return proc.returncode, proc.stdout + proc.stderr


def tool_entry(tool, *args):
    """(exit code, what it printed to stdout and stderr) of the entry point `tool` calls, with
    `args` as its argv, run inside the working directory through adapters/mcp/captured.py -
    the call the tool makes, less the JSON it wraps the answer in. stderr is kept, as a child
    interpreter's was, so an assertion on a warning printed there still sees it.
    """
    import contextlib   # noqa: PLC0415 - test helper
    import io           # noqa: PLC0415 - test helper

    from jsk.adapters.mcp import captured   # noqa: PLC0415 - test helper

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        if tool == "resume_check":
            from jsk.adapters.cli.resume import cmd_resume_check   # noqa: PLC0415

            code, out = captured.called(os.getcwd(), cmd_resume_check, args)
        else:
            code, out = captured.ran(os.getcwd(), TOOL_SCRIPTS[tool], args)
    return code, out + err.getvalue()


def gate(script, *args):
    """(exit code, output) of one gate's own main(), called in this interpreter.

    The gates' argument handling has no command of its own any more - `jsk resume check`
    finds a gate's file before it runs - so a test of what the gate itself says to a bad
    call calls it the way `jsk` does (dispatch.call_gate).
    """
    from jsk.adapters.cli.dispatch import call_gate   # noqa: PLC0415 - test helper

    return call_gate(script, [str(a) for a in args])


# The four ways an authored file reaches jsk: as jsk writes it, then as a Windows editor
# might save it. The first three are the same text; the last is not UTF-8 at all.
AWKWARD = ("utf-8", "bom", "crlf", "cp1252")


def awkward_bytes(text, form):
    """`text` (LF line endings) saved one of the AWKWARD ways, as bytes.

    The cp1252 form must hold a byte that is not UTF-8, or it tests nothing: an ASCII text
    encodes the same both ways. So `text` has to carry a character cp1252 writes above
    0x7f - a curly quote, a dash, an accented letter - and this refuses one that does not.
    """
    if form == "utf-8":
        return text.encode("utf-8")
    if form == "bom":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    if form == "crlf":
        return text.replace("\n", "\r\n").encode("utf-8")
    if form == "cp1252":
        data = text.encode("cp1252")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return data
        raise ValueError("this text is the same in cp1252 and UTF-8 - give it a curly "
                         "quote or a dash, so the cp1252 form is one UTF-8 cannot read")
    raise ValueError(f"unknown form {form!r}: one of {', '.join(AWKWARD)}")


def write_awkward(path, text, form):
    """Write `text` to `path` in one of the AWKWARD forms; the bytes written."""
    data = awkward_bytes(text, form)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(data)
    return data


# --- the render ---------------------------------------------------------------

# The skill still exists and still has references/ and its mode files; what moved out
# of it is the code and the schema. test_plugin_surface.py reads the skill, the tests
# below read the package.
PLUGIN = REPO_ROOT / "plugins" / "jsk"
RENDER_RESUME = f"{PACKAGE}.adapters.cli.render"
CHECK_PROSE = f"{PACKAGE}.domain.gates.prose_rules"
PREFLIGHT = f"{PACKAGE}.preflight"
# The shipped example workspace's general resume: what `jsk doctor` renders, and what a
# render test reaches for when any resume will do. Its selection was a short resume.json
# until 6.0 read none (docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2); it
# ships beside the career as resumes/example/resume.ttl, which `jsk kb load` imports.
EXAMPLE = SRC / PACKAGE / "data" / "example"
EXAMPLE_TARGET = "resumes/example"
_EXAMPLE = []


def example_short():
    """The ref of the example's general resume, in a copy of the workspace whose career and
    selection are in a store of their own - as `jsk doctor` imports them (preflight.verify).
    Made once per test process and only read, so every render test shares it; removed when
    the process exits. The ref goes wherever a resume.json path went before 6.0."""
    if not _EXAMPLE:
        import atexit
        import tempfile

        from storekit import seed

        root = Path(tempfile.mkdtemp()) / "example"
        atexit.register(shutil.rmtree, root.parent, True)
        shutil.copytree(EXAMPLE, root)
        seed(root)
        _EXAMPLE.append(root / "resumes" / "example" / "resume")
    return _EXAMPLE[0]


_EXAMPLE_PDFS = {}


def example_pdf(template, *flags):
    """example_short() rendered to a PDF in `template`, with extra render `flags` such as
    "--ats-max". The theme, layout and parse tests all read the same renders, and a TeX run
    is seconds: each is made once per test process, only read, and removed at exit."""
    key = (template, *flags)
    if key not in _EXAMPLE_PDFS:
        import atexit
        import tempfile

        out = Path(tempfile.mkdtemp())
        atexit.register(shutil.rmtree, out, True)
        code, output = run(RENDER, example_short(), "--out", out, "--template", template,
                           "--format", "latex", "--pdf", *flags)
        assert code == 0, output
        _EXAMPLE_PDFS[key] = next(out.glob("*.pdf"))
    return _EXAMPLE_PDFS[key]


def has_pymupdf():
    """Whether pymupdf imports: the tests that read a PDF back skip without it."""
    try:
        import pymupdf  # noqa: F401,PLC0415
        return True
    except ImportError:
        return False


def render_module(name):
    """Import a module the renderer itself uses, named under the package: `infra.tex`,
    `domain.render.themes`, `domain.render.emit_latex`.

    The bare spelling callers use is qualified here rather than at every call site.
    """
    if not name.startswith(PACKAGE + "."):
        name = f"{PACKAGE}.{name}"
    return importlib.import_module(name)


def one_test_each(cases, name, template):
    """A class decorator: one test method per case, each calling the class's method
    `template(self, case)`. `cases` is {key: case} or keys alone; `name` formats a key into
    the method name, as "test_{}_is_caught".

    A loop of slow cases inside one method runs on one worker however many `-n auto`
    starts, and it set the suite's wall clock: nine mutation runs of twenty seconds each,
    in a row. A method per case spreads them, and a failure names its case in the test id.
    """
    import re

    def decorate(cls):
        for key, case in (cases.items() if isinstance(cases, dict) else ((k, k) for k in cases)):
            method = name.format(re.sub(r"\W+", "_", str(key).lower()).strip("_"))
            assert not hasattr(cls, method), f"two cases make {method}"
            setattr(cls, method, lambda self, case=case: getattr(self, template)(case))
        return cls
    return decorate
