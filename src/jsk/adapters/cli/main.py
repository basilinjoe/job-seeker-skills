"""jsk - the Job Seeker Skill's command line: `jsk <noun> <verb>`, the noun what you work on.

    jsk doctor                  what works on this machine
    jsk kb new PATH --name NAME scaffold career/store/ - the career and its log at r1 -
                                and applications/
    jsk kb load WORKSPACE|DUMP  fill an empty career/store/, once: from a workspace still laid
                                out as .ttl files, or from a dump
    jsk kb dump [--out FILE]    the whole record as TriG: a backup, and what load reads
    jsk mcp                     serve the career and its applications to an agent as MCP
                                tools, over stdio

`jsk <noun> --help` lists a noun's verbs, and `jsk <noun> <verb> --help` its flags.

Everything else is a tool of `jsk mcp`, not a command (2026-10-04, docs/superpowers/plans/
2026-10-04-mcp-first.md): checking and drafting the record (career_check, career_pack,
career_merge), changing and reading it (career_apply, career_preview, career_confirm,
career_show, career_view, career_query, career_log), rendering, checking and shipping a
resume (resume_check, resume_render, resume_preview, resume_fit, resume_select, resume_update,
resume_ship), a cover letter (letter_check), and an application from its advert to its
outcome (posting_capture, posting_decide, posting_complete, assessment_derive,
assessment_review, assessment_complete, app_list, app_show, app_freeze, app_event, app_drop).
A retired command exits 2 and names its tool.

The career is the graph record, in career/store/: changed through the career_apply tool, read
with the career_show and career_view tools, validated on every load. A target's selection - the bullets
chosen, as ids, kept in the store by the resume_select tool - says what a resume shows;
every render builds from the career and that selection, and the resume_check tool checks it and
the bullets it selects before anything renders - the last point at which a mistake is still
cheap.

pyoxigraph for the graph record, and pymupdf to read a PDF.
"""
from ... import __version__
from .cliutil import refused
from .dispatch import run_in_process, workspace_refusal

# Where `jsk --help` stops: the paragraph naming the dependencies is for whoever opens
# this file. Named once, here, and a test holds the docstring to it, so rewording that
# paragraph fails a test rather than quietly printing it as part of the help.
HELP_ENDS_BEFORE = "\n\npyoxigraph for the graph record"

# The kb adapter's verbs that stay on the command line (check, pack and merge are
# reached through the career_* tools, so adapters.cli.kb.VERBS holds three more),
# named here so that dispatching one does
# not import it: `python -m jsk doctor` runs without pyoxigraph.
KB_VERBS = ("load", "dump")


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
    "mcp": {},
}

# The scripts that dispatch their own verbs, so they are handed the verb with its arguments.
TAKES_VERB = {"kbcli.py"}

# The nouns whose adapter prints its own usage, verbs and unknown-verb refusal.
OWN_USAGE = {"kb": "kbcli.py"}

# Commands that went, with what replaced them. Said by name rather than as an unknown
# command: a shell history or an old mode file still holds them, and "unknown command"
# reads as a broken install. A pair is (the command now, the arguments its fix shows when
# none were given); the call's own arguments are shown when there are some.
RETIRED = {
    "index": "it read user-knowledgebase.md, and the career is career/store/ now.\n"
             "fix:  the assessment_derive tool (jsk mcp) matches the career against a "
             "posting;\n      the career_view tool (jsk mcp) reads it",
    "migrate": "it moved a user-knowledgebase.md into the career, and jsk no longer reads "
               "the Markdown format.\n"
               "fix:  `jsk kb new PATH --name NAME` starts a career/store/; the "
               "resume_select tool (jsk mcp) chooses a resume from it",
    "new": ("jsk kb new", "PATH --name NAME"),
    "match": "in 6.0 - it matched a posting made from files, which jsk no longer makes.\n"
             "fix:  the assessment_derive tool (jsk mcp) matches a graph-native "
             "application's posting against the career",
    # 2026-10-04: the commands these pointed at went too (Ruling 4 of docs/superpowers/plans/
    # 2026-10-04-mcp-first.md), so each is a string naming the tool: a "it is jsk resume
    # render now" would send the reader to another exit 2.
    "validate": "in 6.0 - the record gate is a tool now.\n"
                "fix:  the resume_check tool (jsk mcp): resume_check(target)",
    "check": "in 6.0 - the gates are a tool now.\n"
             "fix:  the resume_check tool (jsk mcp): resume_check(target, only=)",
    "check --only letter": "a cover letter is checked by a tool now.\n"
                           "fix:  the letter_check tool (jsk mcp): letter_check(letter, "
                           "record=<stem>)",
    "gates": "in 6.0 - the gates over a render are a tool now.\n"
             "fix:  the resume_check tool (jsk mcp): resume_check(<out-dir>, record=)",
    "render": "in 6.0 - a render is made by a tool now.\n"
              "fix:  the resume_render tool (jsk mcp): resume_render(target, out=, pdf=)",
    "preview": "in 6.0 - the template preview is a tool now.\n"
               "fix:  the resume_preview tool (jsk mcp): resume_preview(target, out)",
    "fit": "in 6.0 - fitting a render is a tool now.\n"
           "fix:  the resume_fit tool (jsk mcp): resume_fit(tex, target_pages=)",
    "ship": "in 6.0 - a ship is made by a tool now.\n"
            "fix:  the resume_ship tool (jsk mcp): resume_ship(target)",
    "event": "in 6.0 - an event is added by a tool now.\n"
             "fix:  the app_event tool (jsk mcp): app_event(app, kind, date)",
    "freeze": "in 6.0 - a freeze is made by a tool now.\n"
              "fix:  the app_freeze tool (jsk mcp): app_freeze(app, submitted, channel)",
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

# 2026-10-04: the verbs the MCP tools duplicate went too (docs/superpowers/plans/
# 2026-10-04-retire-duplicated-cli.md, Ruling 2). Each is keyed "<noun> <verb>", which main
# checks before dispatch for any noun - `kb` hands the rest of its line to its own adapter -
# and each names the tool that does its work. Nothing is written.
RETIRED.update({
    "kb apply": "in 6.0 - a changeset is merged by a tool now.\n"
                "fix:  the career_preview tool (jsk mcp) returns a changeset's diff and writes "
                "nothing; the career_apply tool validates, writes and logs it",
    "kb confirm": "in 6.0 - an entry is confirmed by a tool now.\n"
                  "fix:  the career_confirm tool (jsk mcp) confirms ids with the person's "
                  "answer, or a source and its quote; with target and block it confirms a "
                  "selection's summary or headline",
    "kb show": "in 6.0 - entries are read by a tool now.\n"
               "fix:  the career_show tool (jsk mcp) returns entries as Turtle, with the "
               "revision a changeset's op:base names",
    "kb view": "in 6.0 - the career is read by a tool now.\n"
               "fix:  the career_view tool (jsk mcp) returns it as Markdown; `jsk kb dump` "
               "writes the whole record as TriG",
    "kb query": "in 6.0 - the named queries are a tool now.\n"
                "fix:  the career_query tool (jsk mcp): career_query(name, args)",
    "kb log": "in 6.0 - the record's history is a tool now.\n"
              "fix:  the career_log tool (jsk mcp): career_log(last)",
    "kb export": "in 6.0 - a selection is chosen and stored by a tool now.\n"
                 "fix:  the resume_select tool (jsk mcp) chooses a target's bullets; the "
                 "app_show tool prints the selection",
    "kb path": "in 6.0 - `jsk doctor` names the workspace.\n"
               "fix:  `jsk doctor`",
    "app freeze": "in 6.0 - a freeze is made by a tool now.\n"
                  "fix:  the app_freeze tool (jsk mcp): app_freeze(app, submitted, channel)",
    "app event": "in 6.0 - an event is added by a tool now.\n"
                 "fix:  the app_event tool (jsk mcp): app_event(app, kind, date)",
    "letter": "in 6.0 - the letter noun had one verb, and a tool does its work.\n"
              "fix:  the letter_check tool (jsk mcp): letter_check(letter, record=<stem>)",
    "letter check": "in 6.0 - a cover letter is checked by a tool now.\n"
                    "fix:  the letter_check tool (jsk mcp): letter_check(letter, record=<stem>)",
})

# 2026-10-04: the rest of what the MCP tools duplicate (docs/superpowers/plans/
# 2026-10-04-mcp-first.md, Ruling 4). The kb adapter still serves check, pack and merge,
# and the tools call it, but `jsk kb check` is refused here before it is dispatched.
RETIRED.update({
    "kb check": "in 6.0 - the record is checked by a tool now.\n"
                "fix:  the career_check tool (jsk mcp): career_check()",
    "kb pack": "in 6.0 - a starter pack is drafted by a tool now.\n"
               "fix:  the career_pack tool (jsk mcp): career_pack(pack=\"capabilities\") returns "
               "a changeset for career_preview",
    "kb merge": "in 6.0 - a merge is drafted by a tool now.\n"
                "fix:  the career_merge tool (jsk mcp): career_merge(concept, into) returns a "
                "changeset for career_preview",
    "resume": "in 6.0 - the resume noun had five verbs, and tools do their work.\n"
              "fix:  the resume_check, resume_render, resume_preview, resume_fit and "
              "resume_ship tools (jsk mcp)",
    "resume check": "in 6.0 - a resume is checked by a tool now.\n"
                    "fix:  the resume_check tool (jsk mcp): resume_check(target, only=, record=)",
    "resume render": "in 6.0 - a render is made by a tool now.\n"
                     "fix:  the resume_render tool (jsk mcp): resume_render(target, out=, pdf=)",
    "resume preview": "in 6.0 - the template preview is a tool now.\n"
                      "fix:  the resume_preview tool (jsk mcp): resume_preview(target, out)",
    "resume fit": "in 6.0 - fitting a render is a tool now.\n"
                  "fix:  the resume_fit tool (jsk mcp): resume_fit(tex, target_pages=)",
    "resume ship": "in 6.0 - a ship is made by a tool now.\n"
                   "fix:  the resume_ship tool (jsk mcp): resume_ship(target)",
    "app": "in 6.0 - the app noun had one verb left, and a tool does its work.\n"
           "fix:  the app_drop tool (jsk mcp): app_drop(app, reason=, dry_run=)",
    "app drop": "in 6.0 - an application is set aside by a tool now.\n"
                "fix:  the app_drop tool (jsk mcp): app_drop(app, reason=, dry_run=)",
})

# The nouns 6.0 retired whole, their verbs with them: `jsk posting build` is said as itself
# when RETIRED names it, and as its noun otherwise.
RETIRED_NOUNS = ("posting", "tailor", "letter", "resume", "app")


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
    if rest and f"{noun} {rest[0]}" in RETIRED:
        return retired(f"{noun} {rest[0]}", rest[1:])
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
    if noun in RETIRED_NOUNS:
        verb = f"{noun} {rest[0]}" if rest else noun
        return retired(verb if verb in RETIRED else noun, rest[1:])
    if noun in RETIRED:
        return retired(noun, rest)
    print(f"unknown command: {noun}")
    print(f"fix:  one of {', '.join(NOUNS)} - or run jsk --help")
    return 2
