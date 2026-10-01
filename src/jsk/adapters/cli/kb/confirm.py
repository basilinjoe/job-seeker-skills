"""`jsk kb confirm`: its three forms, the confirmation planned (application/record/confirm.py)
and written through the logged write, or a resume.json's summary or headline confirmed in
place."""
from ..presenters import usage
from .write import refused, write_logged


def cmd_confirm(args, flags, root, today):
    """jsk kb confirm <id>... --answer "what the person said"
       jsk kb confirm <id>... --source <file> --quote "the document's words"
       jsk kb confirm --summary <resume.json> --answer "what the person said"
       jsk kb confirm --headline <resume.json> --answer "what the person said"

    The only way an entry becomes j:confirmed. Ask the person; record their answer in their
    words. Each entry named is confirmed, every open question about it is answered today,
    and the log keeps the answer beside the ids - the audit trail of why it is confirmed.
    An answer that says nothing ("yes", "ok", "confirmed") is refused, and so is one that
    only names a document ("From resume.pdf"): nothing would check the document says it.

    --source/--quote confirm from a document in the workspace instead: the quote must be
    in it word for word, every number in each entry's claims must be in the quote, and so
    must four in five of a bullet's words - a clause the document lacks is the session's.
    The log keeps `From <file>: "<quote>"`. A .docx is refused; a .pdf needs pymupdf.

    --summary confirms a resume.json's summary: resume.json keeps the answer and the
    text's hash, so an edit to the text afterwards drops it back to inferred. --headline
    does the same for its headline - the posting's title, which the person must stand
    behind before it renders under their name. For a graph-native application (`<stem>`)
    or a general resume (`resumes/<name>`) in place of the resume.json, the block is
    confirmed in its selection graph.
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
    if summary is not None:
        if args or answer is None:
            return usage('jsk kb confirm --summary <resume.json> --answer "what the person '
                         'said" - the summary alone, no ids, and the person\'s answer')
        return confirm_summary(summary, answer, root)
    if headline is not None:
        if args or answer is None:
            return usage('jsk kb confirm --headline <resume.json> --answer "what the person '
                         'said" - the headline alone, no ids, and the person\'s answer')
        return confirm_summary(headline, answer, root, key="headline")
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


def confirm_summary(path, answer, root, key="summary"):
    """`jsk kb confirm --summary` (or `--headline`, `key`): the block confirmed, and the
    diff of resume.json printed. Returns the exit code."""
    from ....application.record.confirm import confirm_summary as confirmed
    from ....application.record.refusals import Refused
    from ....domain.record.state import diff
    from ....infra import files
    from ..compose import resume as short
    from ....application.render.selection import parse_ref
    from ..compose import selection
    from ..compose.timeline import frozen

    ref = selection.ref_for(path, root=root)
    target = (parse_ref(ref) or ("", ""))[1] if ref else None
    label = f"{target}/resume" if target else files.rel(path, root)
    try:
        if target:
            # A graph-native target: the block is in its selection graph, not a file.
            done = selection.confirm(root, target, key, answer)
        else:
            done = confirmed(path, answer, root, files=files, short=short.read,
                             frozen=frozen, key=key)
    except Refused as err:
        return refused(err)
    if done.new is None:
        print(f"nothing to change: the {key} is confirmed already")
        return 0
    print(diff(done.old, done.new, label), end="")
    print(f"confirmed the {key} in {path}")
    return 0
