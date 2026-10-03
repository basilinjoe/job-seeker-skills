"""jsk - the Job Seeker Skill's command line: `jsk <noun> <verb>`, the noun what you work on.

    jsk doctor                  what works on this machine
    jsk kb new PATH --name NAME scaffold career/store/ - the career and its log at r1 -
                                and applications/
    jsk kb VERB [...]           the graph record: apply a changeset, confirm, show, check
    jsk resume check TARGET     the record gate, before anything renders - TARGET is an
                                application's <stem> or resumes/<name>
      ... check PDF [--strict]  the parse gate and the prose gate, both
      ...   --only parse|prose  one of them, for re-checking one repaired file
      ...   --only layout       fonts, tofu, stranded headings, date column, paper
      ... check DIR [--record TARGET]  the record, parse, prose and layout gates over a render
      ... render TARGET [...]   its selection to a .tex (a PDF too with --pdf), in its
                                own directory
      ... preview TARGET --out D  the same resume in every template, to pick a look
      ... fit TEX [...]         fit a render to a page budget
      ... ship TARGET           validate, render and gate, in one pass
    jsk letter check LETTER --record TARGET   a cover letter's length, prose and numbers
    jsk app freeze APP --submitted DATE|false --channel TEXT   archive a sent application
      ... event APP KIND --date DATE      add a screen, an offer, a rejection to one
      ... drop APP [--reason T] [--dry-run]   set an unsent one aside: graphs removed,
                                folder kept under dropped/
    jsk mcp                     serve the career and its applications to an agent as MCP
                                tools, over stdio (the mcp extra)

`jsk <noun> --help` lists a noun's verbs, and `jsk <noun> <verb> --help` its flags.

The career is the graph record, in career/store/: changed through `jsk kb apply`, read with
`jsk kb show` and `jsk kb view`, validated on every load. A target's selection - the bullets
chosen, as ids, kept in the store by the resume_select tool - says what a resume shows;
every render builds from the career and that selection, and `jsk resume check` checks it and
the bullets it selects before anything renders - the last point at which a mistake is still
cheap.

pyoxigraph for the graph record, and pymupdf to read a PDF.
"""
from ... import __version__
from .cliutil import refused, wants_help
from .dispatch import run_in_process, workspace_refusal

# Where `jsk --help` stops: the paragraph naming the dependencies is for whoever opens
# this file. Named once, here, and a test holds the docstring to it, so rewording that
# paragraph fails a test rather than quietly printing it as part of the help.
HELP_ENDS_BEFORE = "\n\npyoxigraph for the graph record"

# The kb adapter's verbs (adapters.cli.kb.VERBS), named here so that dispatching one does
# not import it: `python -m jsk doctor` runs without pyoxigraph.
KB_VERBS = ("apply", "confirm", "show", "view", "query", "export", "check", "log", "path",
            "load", "dump", "pack", "merge")


def resume_check(args):
    """`jsk resume check` (adapters.cli.resume.cmd_resume_check)."""
    from .resume import cmd_resume_check

    return cmd_resume_check(args)


def resume_ship(args):
    """`jsk resume ship` (adapters.cli.ship.main)."""
    from .ship import main as ship

    return ship(args)


def letter_check(args):
    """`jsk letter check LETTER --record R`: the letter gate, its arguments unchanged."""
    from .gates.check import through

    return through("letter.py", args)


def app_freeze(args):
    """`jsk app freeze` (adapters.cli.freeze.main)."""
    from .freeze import main as freeze

    return freeze(args)


def app_drop(args):
    """`jsk app drop` (adapters.cli.drop.main)."""
    from .drop import main as drop

    return drop(args)


def doctor(args):
    """`jsk doctor` (adapters.cli.doctor.cmd_doctor)."""
    from .doctor import cmd_doctor

    return cmd_doctor(args)


def mcp(args):
    """`jsk mcp` (adapters.mcp.main): stdlib-only until it serves, so a plain install says
    the extra is missing instead of failing an import."""
    from ..mcp import main as serve

    return serve(args)


# noun -> verb -> what runs it: a documented script name, run in process through the module
# that binds its ports (dispatch.run_in_process), or a handler taking the arguments after the
# verb. What each one does is said once, in the docstring above, which `jsk --help` prints.
NOUNS = {
    "doctor": {},
    "kb": {"new": "kb.py", **dict.fromkeys(KB_VERBS, "kbcli.py")},
    "resume": {"check": resume_check, "render": "render_resume.py",
               "preview": "preview_templates.py", "fit": "fit_pages.py", "ship": resume_ship},
    "letter": {"check": letter_check},
    "app": {"event": "timeline.py", "freeze": app_freeze, "drop": app_drop},
    "mcp": {},
}

# The scripts that dispatch their own verbs, so they are handed the verb with its arguments.
TAKES_VERB = {"kbcli.py"}

# The nouns whose adapter prints its own usage, verbs and unknown-verb refusal.
OWN_USAGE = {"kb": "kbcli.py"}

# What `jsk <noun> --help` prints for the nouns that do not print their own.
NOUN_USAGE = {
    "resume": ("usage: jsk resume <verb> ...\n"
               "  check TARGET | RENDER | DIR        the record gate; parse and prose; "
               "or all four\n"
               "  render TARGET [--out DIR] [...]    a target's selection to a .tex; --pdf "
               "compiles it\n"
               "  preview TARGET --out DIR           the same resume in every template\n"
               "  fit TEX [--target-pages N]         fit a render to a page budget\n"
               "  ship TARGET [...]                  validate, render and gate, in one pass\n"
               "  (TARGET: an application's <stem>, or resumes/<name>)"),
    "letter": ("usage: jsk letter <verb> ...\n"
               "  check LETTER --record TARGET   a cover letter's length, prose and numbers"),
    "app": ("usage: jsk app <verb> ...\n"
            "  event APP KIND --date D                      add what happened next\n"
            "  freeze APP --submitted D|false --channel T   archive a sent application\n"
            "  drop APP [--reason T] [--dry-run]            set an unsent application aside"),
}

# Commands that went, with what replaced them. Said by name rather than as an unknown
# command: a shell history or an old mode file still holds them, and "unknown command"
# reads as a broken install. A pair is (the command now, the arguments its fix shows when
# none were given); the call's own arguments are shown when there are some.
RETIRED = {
    "index": "it read user-knowledgebase.md, and the career is career/store/ now.\n"
             "fix:  the assessment_derive tool (jsk mcp) matches the career against a "
             "posting;\n      `jsk kb view` reads it",
    "migrate": "it moved a user-knowledgebase.md into the career, and jsk no longer reads "
               "the Markdown format.\n"
               "fix:  `jsk kb new PATH --name NAME` starts a career/store/; the "
               "resume_select tool (jsk mcp) chooses a resume from it",
    "new": ("jsk kb new", "PATH --name NAME"),
    "match": "in 6.0 - it matched a posting made from files, which jsk no longer makes.\n"
             "fix:  the assessment_derive tool (jsk mcp) matches a graph-native "
             "application's posting against the career",
    "validate": ("jsk resume check", "<stem>"),
    "check": ("jsk resume check", "resume.pdf"),
    "check --only letter": ("jsk letter check", "cover-letter.txt --record <stem>"),
    "gates": ("jsk resume check", "<out-dir>"),
    "render": ("jsk resume render", "<stem>"),
    "preview": ("jsk resume preview", "<stem> --out DIR"),
    "fit": ("jsk resume fit", "resume.tex --target-pages 2"),
    "ship": ("jsk resume ship", "<stem>"),
    "event": ("jsk app event", "applications/<dir> KIND --date YYYY-MM-DD"),
    "freeze": ("jsk app freeze", "applications/<dir> --submitted YYYY-MM-DD --channel TEXT"),
    # 6.0 retired the pipeline that made an application from files (Ruling 1 of
    # docs/superpowers/plans/2026-10-03-retire-file-pipeline.md): each verb is named with the
    # tool that does its work on a graph-native application, as 5.1's WARN named it.
    "posting": "in 6.0 - the posting noun served applications made from files, which jsk no "
               "longer makes.\n"
               "fix:  the posting_capture, posting_decide and posting_complete tools (jsk mcp) "
               "keep an application's advert and its requirements in the graph",
    "posting fetch": "in 6.0 - it wrote an application's posting.md, and jsk no longer makes "
                     "an application from files.\n"
                     "fix:  the posting_capture tool (jsk mcp) stores the advert in the graph: "
                     "posting_capture(app, url=)",
    "posting extract": "in 6.0 - it numbered posting.md's lines for decisions.txt.\n"
                       "fix:  the app_show tool (jsk mcp), part lines, shows a captured "
                       "advert's numbered lines",
    "posting build": "in 6.0 - it wrote a posting graph from decisions.txt.\n"
                     "fix:  the posting_decide and posting_complete tools (jsk mcp) write the "
                     "requirements and settle them",
    "tailor": "in 6.0 - the tailor noun served applications made from files, which jsk no "
              "longer makes.\n"
              "fix:  the assessment_derive, assessment_review and assessment_complete tools "
              "(jsk mcp) match, review and settle a graph-native application",
    "tailor match": "in 6.0 - it matched a posting made from files and folded its gaps.txt "
                    "in.\n"
                    "fix:  the assessment_derive tool (jsk mcp) matches; assessment_review "
                    "and assessment_complete take the review",
    "tailor prepare": "in 6.0 - it gathered an assessment's digest and drafted gaps.txt for "
                      "an application made from files.\n"
                      "fix:  the assessment_derive tool (jsk mcp) returns the rows, flags and "
                      "questions; app_show reads the rest",
}

# The nouns 6.0 retired whole, their verbs with them: `jsk posting build` is said as itself
# when RETIRED names it, and as its noun otherwise.
RETIRED_NOUNS = ("posting", "tailor")


def without_only_letter(args):
    """`args` less `--only letter`, or None when they do not ask for the letter gate.

    Args:
        args: the arguments after the retired `check`.

    Returns:
        The other arguments, in order, or None.
    """
    for at in range(len(args) - 1):
        if args[at] == "--only" and args[at + 1] == "letter":
            return args[:at] + args[at + 2:]
    return None


def retired(sub, rest):
    """Say that `jsk <sub>` went and what replaced it.

    Args:
        sub: the retired command.
        rest: its arguments, which the fix repeats under the new name.

    Returns:
        2, the exit code of a call made wrongly.
    """
    letter = without_only_letter(rest) if sub == "check" else None
    if letter is not None:
        sub, rest = "check --only letter", letter
    said = RETIRED[sub]
    if isinstance(said, str):
        print(f"jsk {sub} was retired: {said}")
        return 2
    command, example = said
    args = " ".join(f'"{a}"' if " " in a else a for a in rest) or example
    print(f"jsk {sub} was retired: it is {command} now.\nfix:  {command} {args}")
    return 2


def usage():
    """Print `jsk --help`: the docstring's menu, without the paragraph for contributors.

    Returns:
        2, the exit code of a bare `jsk`.
    """
    print(str(__doc__).strip().split("\n\n", 1)[1].split(HELP_ENDS_BEFORE, 1)[0])
    return 2


def noun_usage(noun, asked):
    """Print what a noun's verbs are.

    Args:
        noun: one of NOUN_USAGE.
        asked: whether it was asked for with --help, rather than given no verb.

    Returns:
        0 when asked, else 2.
    """
    print(NOUN_USAGE[noun])
    return 0 if asked else 2


def run(noun, verb, rest):
    """Run one noun's verb, after the refusal every command reading the record shares.

    Args:
        noun: a key of NOUNS.
        verb: a key of NOUNS[noun].
        rest: the arguments after the verb.

    Returns:
        The verb's exit code.
    """
    refusal = workspace_refusal(noun, rest)
    if refusal:
        return refused(refusal)
    target = NOUNS[noun][verb]
    if callable(target):
        return target(rest)
    return run_in_process(target, ([verb] if target in TAKES_VERB else []) + list(rest))


def main(argv):
    """`jsk`: find the noun and its verb, and run it in this interpreter.

    Args:
        argv: the whole argv, the program name first.

    Returns:
        The exit code: the verb's, 0 for help and the version, 2 for a call made wrongly.
    """
    args = argv[1:]
    if not args:
        return usage()
    if args[0] in ("-h", "--help", "help"):
        usage()
        return 0
    if args[0] in ("--version", "-V", "version"):
        print(f"jsk {__version__}")
        return 0
    noun, rest = args[0], args[1:]
    if noun == "doctor":
        return doctor(rest)
    if noun == "mcp":
        return mcp(rest)
    if noun in NOUNS:
        verbs = NOUNS[noun]
        verb = rest[0] if rest else None
        if verb in verbs:
            return run(noun, verb, rest[1:])
        if noun in OWN_USAGE:
            return run_in_process(OWN_USAGE[noun], rest)
        if verb is None or wants_help(rest):
            return noun_usage(noun, verb is not None)
        print(f"unknown verb: jsk {noun} {verb}")
        print(f"fix:  one of {', '.join(verbs)} - or run jsk {noun} --help")
        return 2
    if noun in RETIRED_NOUNS:
        verb = f"{noun} {rest[0]}" if rest else noun
        return retired(verb if verb in RETIRED else noun, rest[1:])
    if noun in RETIRED:
        return retired(noun, rest)
    print(f"unknown command: {noun}")
    print(f"fix:  one of {', '.join(NOUNS)} - or run jsk --help")
    return 2
