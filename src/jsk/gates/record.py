#!/usr/bin/env python3
"""The record gate: a short resume.json, and the career bullets it selects.

Usage: jsk validate <resume.json> [--strict] [--max-findings N]
       python -m jsk.gates.record <resume.json> [--strict] [--max-findings N]
       --strict            treat warnings as failures
       --max-findings N    print at most N failures and N warnings (default 25;
                           0 prints every one)

Exit 0 = safe to render. Exit 1 = do not render this. Exit 2 = usage, or no career to
check it against.

It replaced two gates (2026-09-25). validate_urs checked a 41KB URS record against itself
and claims.py checked that record against career/kb.ttl; the record was a copy of the
career, and most of what the two asked was whether the copy had drifted. The short file
holds ids and settings, so what is left to ask is of the file and of the career bullets
it names:

  FAIL  the file's shape: an unknown key, a wrong type, no bullets (short.shape)
  FAIL  an id kb.ttl does not hold, a retired one, a bullet whose project has no role
        (short.ids)
  FAIL  a number in a selected bullet no current version of a metric it cites holds -
        untraced - or one only a replaced version holds - superseded (numbers.untraced)
  FAIL  a career that does not validate, or that log.ttl does not vouch for
  WARN  a vocabulary label in a bullet its project does not hold
  WARN  "N years of X" in the headline, the summary or a bullet, beyond the roles
        behind the projects holding X
  WARN  a bracket in the summary or a bullet - almost always a placeholder

The label and years checks read prose, where a word can be a technology or not ("Go"),
so they warn, as they did in the claims gate. The rest read ids and numbers.
"""
import datetime
import os
import re
import sys

from ..graph import ontology as O
from .report import show

MAX_FINDINGS = 25

# "8 years of Kubernetes", "8+ yrs of hands-on K8s", "8 years' experience with Kafka".
YEARS = re.compile(r"(?<![\d.])(\d{1,2})\+?\s*(?:years?|yrs?)(?:'|’)?\s+"
                   r"(?:of\s+)?(?:(?:hands-on|professional|production|commercial)\s+)?"
                   r"(?:experience\s+(?:in|with)\s+)?", re.I)


def line(check, focus, detail, fix):
    return f"{check} {focus} - {detail}\n        fix: {fix}"


# --- the vocabulary in prose --------------------------------------------------------

def label_pattern(label):
    """A label as it may appear in prose. Written as the vocabulary writes it, except
    that the first letter may change case at the start of a sentence - "Kafka" and
    "kafka", "Team leadership" and "team leadership". A label of three characters or
    fewer matches only as written: "Go" is the language, "go" is a verb."""
    body = re.escape(label)
    if len(label) > 3 and label[0].isalpha():
        body = f"[{label[0].lower()}{label[0].upper()}]" + re.escape(label[1:])
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])")


class Vocabulary:
    """Every label and former label the workspace holds, and the concepts each names."""

    def __init__(self, store):
        from ..graph.queries import PRE

        self.labels = {}
        for r in store.select(PRE + "SELECT ?c ?l WHERE { ?c j:label|j:former ?l }"):
            self.labels.setdefault(r["l"].value, set()).add(r["c"].value)
        # Longest first, so ".NET Framework" is read before ".NET" inside it.
        self.patterns = [(label, label_pattern(label))
                         for label in sorted(self.labels, key=lambda s: (-len(s), s))]

    def named(self, text):
        """[(label, {concepts})] named in `text`, longest first, never overlapping."""
        taken, found = [], []
        for label, pattern in self.patterns:
            for m in pattern.finditer(text):
                if any(m.start() < b and a < m.end() for a, b in taken):
                    continue
                taken.append((m.start(), m.end()))
                found.append((label, self.labels[label]))
        return found


def curie(iri):
    from ..graph.writer import curie as c
    return c(iri)


# --- the checks ---------------------------------------------------------------------

def career_refusal(store):
    """A FAIL line when the career cannot be trusted to check against, else None.

    Carried from the claims gate: a provenance raised by hand in kb.ttl, never adopted,
    renders as confirmed - and with no copy of the career left to compare, the log is
    the only thing that would notice."""
    from ..graph import record as R

    broken = [f for f in store.fails() if f.rule != "log-sync"
              and not f.file.startswith("applications/")]
    if broken:
        return line("career-invalid", "career/kb.ttl",
                    f"the career record has {len(broken)} failures, so nothing in this "
                    "resume can be checked against it", "`jsk kb check` lists them")
    st = R.state(store)
    if st.kind != "clean":
        return line("career-unlogged", "career/kb.ttl",
                    f"kb.ttl is not what log.ttl last recorded ({st.kind}"
                    + (f": {st.detail}" if st.detail else "") + ") - a provenance raised by "
                    "hand would render unseen",
                    "run `jsk kb adopt`: it logs the edit and lists every provenance it raised")
    return None


def numbers_lines(store, bullets, today):
    """numbers.untraced as FAIL lines: the untraced of a bullet in one, each superseded
    number in its own - it names the version that replaced it."""
    from . import numbers

    out = []
    for f in numbers.untraced(store, bullets, today):
        ident = f.bullet[len(O.K):]
        for s in f.superseded:
            metric = s["version"].rsplit(".v", 1)[0]
            current = ", ".join(curie(v) for v in current_versions(store, metric)) or "none"
            out.append(line("number-superseded", ident,
                            f"'{s['number']}' is {curie(s['version'])}'s number, replaced on "
                            f"{s['until']} (current: {current})",
                            f"state the current number - `jsk kb show {curie(metric)}` - or, "
                            "if the old one is still true, record that in kb.ttl first"))
        if f.numbers:
            names = ", ".join(curie(m) for m in f.cites) or "no metric - it cites none"
            many = len(f.numbers) > 1
            out.append(line("number-untraced", ident,
                            f"{numbers.quoted(f.numbers)} {'are' if many else 'is'} in no current "
                            f"version of what it cites ({names})",
                            "ask the person for the figure and its source, record it with "
                            "`jsk kb apply` and cite it (j:cites) from the bullet - or change "
                            "the words; never borrow another metric's number"))
    return out


def current_versions(store, metric):
    from ..graph.queries import PRE

    return sorted(r["v"].value for r in store.select(
        PRE + f"SELECT ?v WHERE {{ ?v j:of <{metric}> FILTER NOT EXISTS {{ ?v j:validUntil ?u }} }}"))


def prose(doc, career, bullets):
    """(where, text) of what renders as words: the headline, the summary - the file's,
    else the career's positioning, which renders in its place - and each bullet."""
    me = O.K + "person"
    if career.get(me, "headline"):
        yield "headline", career.get(me, "headline")
    summary = doc.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("text"), str):
        yield "summary", summary["text"]
    elif career.get(me, "positioning"):
        yield "positioning", career.get(me, "positioning")
    for b in bullets:
        if career.get(b, "text"):
            yield b[len(O.K):], career.get(b, "text")


def label_lines(store, career, bullets, vocabulary):
    """Check 4 of the claims gate: a technology named in a bullet is one its project
    holds - "EKS" under a project that ran on AKS is a claim of experience nobody had."""
    from ..graph.named import holdings

    held = holdings(store)
    out = []
    for b in bullets:
        project = career.get(b, "project")
        for label, concepts in vocabulary.named(career.get(b, "text") or ""):
            if not concepts & held.get(project, set()):
                names = ", ".join(sorted(curie(c) for c in concepts))
                out.append(line("label-unheld", b[len(O.K):],
                                f"names {label!r} ({names}), which {curie(project)} does not "
                                "hold", f"drop it from the bullet, or add it to {curie(project)} "
                                "in kb.ttl if the work really used it"))
    return out


def years_lines(store, texts, vocabulary, today):
    """Check 6 of the claims gate: "N years of X" against the roles behind the projects
    holding X."""
    from ..graph.named import experience_of, holdings

    held = holdings(store)
    out = []
    for where, text in texts:
        for m in YEARS.finditer(text):
            rest = text[m.end():]
            label = next((lab for lab, pat in vocabulary.patterns if pat.match(rest)), None)
            if label is None:
                continue
            claimed = int(m.group(1))
            concepts = vocabulary.labels[label]
            months = max(experience_of(store, c, today, held)[0] for c in concepts)
            if claimed * 12 > months:
                out.append(line("years-overstated", where,
                                f"claims {claimed} years of {label}; the roles behind the "
                                f"projects holding it cover {months // 12}y{months % 12}m",
                                f"state what the roles cover (`jsk kb query experience "
                                f"{curie(sorted(concepts)[0])}`), or add the work that makes up "
                                "the rest to kb.ttl"))
    return out


def bracket_lines(texts):
    """A bracket in words that render. The builder warns of the same at render time;
    here it is said before anything is rendered, where the fix is still one edit."""
    return [line("bracket", where, f"{text[:60]!r} - almost always a leftover placeholder",
                 "write the words the bracket stands for, or drop them")
            for where, text in texts if where != "headline" and ("[" in text or "]" in text)]


def findings(doc, store, today=None):
    """(fails, warns): every finding for a short file - a dict, or a path to one - over
    a loaded workspace."""
    from ..graph import record as R
    from ..resume import short
    from ..resume.career import Career

    today = today or datetime.date.today()
    if not isinstance(doc, dict):
        doc = short.read(doc)
    refusal = career_refusal(store)
    if refusal:
        return [refusal], []
    fails = short.shape(doc)
    if fails:
        # Until the shape is right the ids may not be lists of ids at all.
        return fails, []
    fails = short.ids(doc, store)
    career = Career(store.graph(R.KB))
    live = set(career.live("Achievement"))
    bullets = [b for b in (O.K + i for i in doc["bullets"]) if b in live]
    fails += numbers_lines(store, bullets, today)
    vocabulary = Vocabulary(store)
    texts = list(prose(doc, career, bullets))
    warns = label_lines(store, career, bullets, vocabulary)
    warns += years_lines(store, texts, vocabulary, today)
    warns += bracket_lines(texts)
    return fails, warns


def parse(argv):
    """(path or None, strict, limit, problem)."""
    args, strict, limit, positional = list(argv), False, MAX_FINDINGS, []
    while args:
        token = args.pop(0)
        if token == "--strict":
            strict = True
        elif token == "--max-findings":
            raw = args.pop(0) if args else None
            if raw is None or not raw.isdigit():
                return None, strict, limit, (f"--max-findings needs a whole number, got {raw!r}\n"
                                             "fix:  --max-findings 50   - or 0 to print every "
                                             "finding")
            limit = int(raw) or None
        elif token.startswith("-"):
            return None, strict, limit, f"unknown flag: {token}\n{__doc__.split(chr(10) * 2)[1]}"
        else:
            positional.append(token)
    if len(positional) != 1:
        return None, strict, limit, __doc__.split("\n\n")[1]
    return positional[0], strict, limit, None


def main(argv):
    from ..cliutil import wants_help

    if wants_help(argv[1:]):
        print(__doc__.split("\n\n")[1])
        return 0
    path, strict, limit, problem = parse(argv[1:])
    if problem:
        print(problem)
        return 2
    from ..resume import short

    try:
        doc = short.read(path)
        root = short.workspace(path)
    except short.ShortError as err:
        print(f"FAIL  {err}")
        print(f"fix:  {err.fix}")
        return 2
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  the record gate needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    from ..graph import record as R
    from ..graph import store as S

    store = S.load(root)
    fails, warns = findings(doc, store)
    if strict:
        fails, warns = fails + warns, []
    st = R.state(store)
    at = f" r{st.log_revision}" if st.log_revision else ""
    print(f"checking: {os.path.basename(path)}   against: career/kb.ttl{at}")
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    show(fails, "FAIL", limit)
    show(warns, "warn", limit)
    print("\nPASS - safe to render" if not fails
          else "\nDO NOT RENDER - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
