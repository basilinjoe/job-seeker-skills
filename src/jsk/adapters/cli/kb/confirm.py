"""`jsk kb confirm`: its three forms, the confirmation planned (application/record/confirm.py)
and written through the logged write, or a selection's summary or headline confirmed in its
graph. `--summary|--headline <resume.json>` exits 2 naming the target form: 6.0 retired it
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2)."""
from ....application.guards import is_resume_json, resume_json_refusal
from ..presenters import usage
from .write import refused, write_logged


def cmd_confirm(args, flags, root, today):
    """jsk kb confirm <id>... --answer "what the person said"
       jsk kb confirm <id>... --source <file> --quote "the document's words"
       jsk kb confirm --summary <stem>|resumes/<name> --answer "what the person said"
       jsk kb confirm --headline <stem>|resumes/<name> --answer "what the person said"

    The only way an entry becomes j:confirmed. Ask the person; record their answer in their
    words. Each entry named is confirmed, every open question about it is answered today,
    and the log keeps the answer beside the ids - the audit trail of why it is confirmed.
    An answer that says nothing ("yes", "ok", "confirmed") is refused, and so is one that
    only names a document ("From resume.pdf"): nothing would check the document says it.

    --source/--quote confirm from a document in the workspace instead: the quote must be
    in it word for word, every number in each entry's claims must be in the quote, and so
    must four in five of a bullet's words - a clause the document lacks is the session's.
    The log keeps `From <file>: "<quote>"`. A .docx is refused; a .pdf needs pymupdf.

    --summary confirms the summary of a graph-native application's selection (`<stem>`) or
    a general resume's (`resumes/<name>`): its selection graph keeps the answer and the
    text's hash, so an edit to the text afterwards drops it back to inferred. --headline
    does the same for its headline - the posting's title, which the person must stand
    behind before it renders under their name. A resume.json in place of the target was
    read until 6.0, and is refused now, naming the target form.
    """
    from ....application.record import confirm as C
    from ....application.record.refusals import Failing, Problems, Refused, Unclean
    from ....domain.record.writer import curies
    from ..compose.record import load
    from ....infra import files, pdf
    from ....infra.oxigraph import record as R

    answer, summary, headline, source, quote = (
        flags.get(f) for f in ("--answer", "--summary", "--headline", "--source", "--quote"))
    if (source is not None or quote is not None) and answer is not None:
        return usage("--source/--quote and --answer are two ways to confirm - pass one")
    if (source is None) != (quote is None):
        return usage('--source and --quote go together: the file, and the words in it')
    if summary is not None and headline is not None:
        return usage("--summary and --headline confirm one block each - pass one")
    for flag, value in (("--summary", summary), ("--headline", headline)):
        if value is None:
            continue
        if is_resume_json(value):
            print("\n".join(resume_json_refusal(
                f"jsk kb confirm {flag} <resume.json>",
                f'jsk kb confirm {flag} <stem> --answer "..." (or resumes/<name>), or the '
                "career_confirm tool with target and block (jsk mcp)")))
            return 2
        if args or answer is None:
            return usage(f'jsk kb confirm {flag} <stem>|resumes/<name> --answer "what the '
                         f'person said" - the {flag[2:]} alone, no ids, and the person\'s '
                         'answer')
        return confirm_summary(value, answer, root, key=flag[2:])
    if not args or (answer is None and source is None):
        return usage('jsk kb confirm takes ids and --answer "what the person said", or '
                     '--source <file> --quote "its words"')
    try:
        answer = C.answer_of(answer, source, quote, root, files=files, read_pdf=pdf.read_pdf)
        store = load(root)
        plan = C.confirmation(store, args, quote, today, state=R.state)
    except (Refused, Problems, Failing, Unclean) as err:
        return refused(err)
    if plan is None:
        print("nothing to change: every one of them is confirmed already")
        return 0
    return write_logged(store, root, plan.quads, "confirm", f"Confirmed {curies(plan.ids)}.",
                        touched=plan.touched, answer=answer, today=today)


def confirm_summary(named, answer, root, key="summary"):
    """`jsk kb confirm --summary` (or `--headline`, `key`) on a target: the block confirmed
    in its selection graph, and the diff of the selection printed. Returns the exit code."""
    from ....application.record.refusals import Refused
    from ....application.render.selection import parse_ref
    from ....domain.record.state import diff
    from ..compose import selection

    ref = selection.ref_for(named, root=root)
    target = (parse_ref(ref) or ("", ""))[1] if ref else named
    try:
        done = selection.confirm(root, target, key, answer)
    except Refused as err:
        return refused(err)
    if done.new is None:
        print(f"nothing to change: the {key} is confirmed already")
        return 0
    label = f"{target}/resume"
    print(diff(done.old, done.new, label), end="")
    print(f"confirmed the {key} in {named}")
    return 0
