"""The record gate over one target's selection: its career loaded, then every finding asked.

It replaced two gates (2026-09-25). validate_urs checked a 41KB URS record against itself
and claims.py checked that record against career/kb.ttl; the record was a copy of the
career, and most of what the two asked was whether the copy had drifted. The short file
holds ids and settings, so what is left to ask is of the file and of the career bullets
it names:

  FAIL  the file's shape: an unknown key, a wrong type, no bullets (short.shape)
  FAIL  an id the career does not hold, a retired one, a bullet whose project has no role
        (short.ids)
  FAIL  a number in a selected bullet no current version of a metric it cites holds -
        untraced - or one only a replaced version holds - superseded (numbers.untraced)
  FAIL  a career that does not validate, or that its log does not vouch for
  WARN  a vocabulary label in a bullet its project does not hold
  WARN  "N years of X" in the headline, the summary or a bullet, beyond the roles
        behind the projects holding X
  WARN  a bracket in the summary or a bullet - almost always a placeholder

The label and years checks read prose, where a word can be a technology or not ("Go"),
so they warn, as they did in the claims gate. The rest read ids and numbers.

The career's feature reads come in as `queries` (ports.queries.RecordQueries) and the
career's standing with its log as `state`; this reads the selection, loads its workspace and
folds the warnings into the failures under --strict. It prints nothing:
adapters/cli/gates/record.py says what it found. The record is a target's selection graph,
the short file's dict as resume.json held it until 6.0
(docs/superpowers/plans/2026-10-03-retire-file-pipeline.md, P2), when the file went.
"""
import re
from dataclasses import dataclass

from ...domain import ontology as O
from ...domain.gates.report import line
from ...domain.record.writer import curie
from .result import GateResult, GateStopped

# "8 years of Kubernetes", "8+ yrs of hands-on K8s", "8 years' experience with Kafka".
YEARS = re.compile(r"(?<![\d.])(\d{1,2})\+?\s*(?:years?|yrs?)(?:'|’)?\s+"
                   r"(?:of\s+)?(?:(?:hands-on|professional|production|commercial)\s+)?"
                   r"(?:experience\s+(?:in|with)\s+)?", re.I)


@dataclass(frozen=True)
class RecordResult(GateResult):
    """The record gate's verdict, with the career revision it was checked against."""

    name: str
    revision: int | None        # the log's revision; None when the log has none


def record_gate(path, *, strict, read, workspace, has_engine, career, findings, state,
                today):
    """Check the selection a target's ref names against the career it sits in.

    Args:
        path: the target's ref (application/render/selection.py), whose selection graph
            `read` gives.
        strict: treat warnings as failures.
        read: ref -> the selection as a dict (compose.resume.read).
        workspace: ref -> the workspace root it names (compose.resume.workspace).
        has_engine: () -> whether the graph engine can be imported.
        career: root -> the loaded workspace (compose.resume.career).
        findings: (doc, store, today, target) -> (fails, warns) (compose.gates.findings);
            target names the selection, as the tools name it.
        state: store -> the career and its log's State (infra.oxigraph.record.state).
        today: the date the years claims are measured to.

    Returns:
        A RecordResult. Loads the workspace.

    Raises:
        ShortError: no target's ref, no selection, or a store that will not open - each
            carrying .fix.
        GateStopped: "no-engine" (exit 1) when the graph engine is not installed.
    """
    from ..render.selection import shown_name, target_name

    doc = read(path)
    root = workspace(path)
    if not has_engine():
        raise GateStopped("no-engine", None, 1)
    store = career(root)
    fails, warns = findings(doc, store, today, target_name(path))
    if strict:
        fails, warns = fails + warns, []
    return RecordResult(fails=tuple(fails), warns=tuple(warns), name=shown_name(path),
                        revision=state(store).log_revision)


# --- the vocabulary in prose --------------------------------------------------------

def label_pattern(label):
    """A label as it may appear in prose.

    Written as the vocabulary writes it, except that the first letter may change case at
    the start of a sentence - "Kafka" and "kafka", "Team leadership" and "team
    leadership". A label of three characters or fewer matches only as written: "Go" is
    the language, "go" is a verb.

    Args:
        label: a vocabulary label.

    Returns:
        The compiled pattern.
    """
    body = re.escape(label)
    if len(label) > 3 and label[0].isalpha():
        body = f"[{label[0].lower()}{label[0].upper()}]" + re.escape(label[1:])
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])")


class Vocabulary:
    """Every label and former label the workspace holds, and the concepts each names."""

    def __init__(self, queries):
        """Read the labels.

        Args:
            queries: a RecordQueries over the loaded workspace; its label_pairs are read.
        """
        self.labels = {}
        for c, label in queries.label_pairs():
            self.labels.setdefault(label, set()).add(c)
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


# --- the checks ---------------------------------------------------------------------

def career_refusal(store, state):
    """A FAIL line when the career cannot be trusted to check against, else None.

    Carried from the claims gate: a provenance raised outside `jsk kb`, never logged,
    renders as confirmed - and with no copy of the career left to compare, the log is
    the only thing that would notice. In career/store/ every jsk write lands with its log
    entry, so the two part only when something else wrote the store.

    Args:
        store: the loaded workspace.
        state: store -> the career and its log's State (infra.oxigraph.record.state).

    Returns:
        The FAIL line, or None.
    """
    from ...domain.naming import is_own
    from ...domain.record.state import KB

    # An application's or a general resume's own graph is not the career: a fault in a
    # selection is that selection's, which the shape and id checks name. Only
    # applications/ was left out until 6.0 made a general resume a record (2026-10-04).
    broken = [f for f in store.fails() if f.rule != "log-sync" and not is_own(f.file)]
    if broken:
        return line("career-invalid", KB,
                    f"the career record has {len(broken)} failures, so nothing in this "
                    "resume can be checked against it", "`jsk kb check` lists them")
    st = state(store)
    if st.kind == "clean":
        return None
    detail = f"{st.kind}" + (f": {st.detail}" if st.detail else "")
    if st.kind in ("missing", "empty"):
        return line("career-missing", "career/store/", "the store holds no career to check "
                    "this resume against", "`jsk kb load` a workspace or a dump into it")
    return line("career-unlogged", KB,
                f"the career in career/store/ is not what its log last recorded ({detail}) - "
                "a provenance raised outside jsk would render unseen",
                "`jsk kb load .jsk/backup.trig` into an empty workspace restores the last "
                "write jsk made")


def numbers_lines(queries, bullets):
    """numbers.untraced as FAIL lines: the untraced of a bullet in one, each superseded
    number in its own - it names the version that replaced it.

    Args:
        queries: a RecordQueries over the loaded workspace.
        bullets: the selected achievement iris, in order.

    Returns:
        The FAIL lines.
    """
    from ...domain.gates.numbers import quoted
    from . import numbers

    out = []
    for f in numbers.untraced(queries, bullets):
        ident = f.bullet[len(O.K):]
        for s in f.superseded:
            metric = s["version"].rsplit(".v", 1)[0]
            current = ", ".join(curie(v) for v in queries.current_versions(metric)) or "none"
            out.append(line("number-superseded", ident,
                            f"'{s['number']}' is {curie(s['version'])}'s number, replaced on "
                            f"{s['until']} (current: {current})",
                            f"state the current number - `jsk kb show {curie(metric)}` - or, "
                            "if the old one is still true, record that in the career first"))
        if f.numbers:
            names = ", ".join(curie(m) for m in f.cites) or "no metric - it cites none"
            many = len(f.numbers) > 1
            out.append(line("number-untraced", ident,
                            f"{quoted(f.numbers)} {'are' if many else 'is'} in no current "
                            f"version of what it cites ({names})",
                            "ask the person for the figure and its source, record it with "
                            "`jsk kb apply` and cite it (j:cites) from the bullet - or change "
                            "the words; never borrow another metric's number"))
    return out


def prose(doc, career, bullets):
    """(where, text) of what renders as words: the headline, the summary - the file's,
    else the career's positioning, which renders in its place - and each bullet.

    Args:
        doc: the resume.json.
        career: the career graph (domain.record.career.Career).
        bullets: the selected live achievement iris.

    Returns:
        A generator of (where, text).
    """
    me = O.K + "person"
    headline = doc.get("headline")
    if isinstance(headline, dict) and isinstance(headline.get("text"), str):
        yield "headline", headline["text"]
    elif career.get(me, "headline"):
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
    holds - "EKS" under a project that ran on AKS is a claim of experience nobody had.

    Args:
        store: the loaded workspace.
        career: the career graph.
        bullets: the selected live achievement iris.
        vocabulary: the workspace's Vocabulary.

    Returns:
        The WARN lines.
    """
    from ..record.holdings import holdings

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
                                "with `jsk kb apply` if the work really used it"))
    return out


def years_lines(store, texts, vocabulary, today):
    """Check 6 of the claims gate: "N years of X" against the roles behind the projects
    holding X.

    Args:
        store: the loaded workspace.
        texts: (where, text) of what renders as words.
        vocabulary: the workspace's Vocabulary.
        today: the date the roles' months are measured to.

    Returns:
        The WARN lines.
    """
    from ..record.holdings import experience_of, holdings

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
                                "the rest with `jsk kb apply`"))
    return out


def bracket_lines(texts):
    """A bracket in words that render. The builder warns of the same at render time;
    here it is said before anything is rendered, where the fix is still one edit.

    Args:
        texts: (where, text) of what renders as words.

    Returns:
        The WARN lines.
    """
    return [line("bracket", where, f"{text[:60]!r} - almost always a leftover placeholder",
                 "write the words the bracket stands for, or drop them")
            for where, text in texts if where != "headline" and ("[" in text or "]" in text)]


def findings(doc, store, today, *, queries, state, target=None):
    """Every finding for a short file over a loaded workspace.

    Args:
        doc: the resume.json, as a dict.
        store: the loaded workspace.
        today: the date the years claims are measured to.
        queries: a RecordQueries over `store`.
        state: store -> the career and its log's State (infra.oxigraph.record.state).
        target: the graph-native selection's name (`<stem>`), so a hint names the tool;
            None for a resume.json.

    Returns:
        (fails, warns): the FAIL and WARN lines. Runs the store's SELECTs.
    """
    from ...domain.record.career import Career
    from ...domain.record.state import KB
    from ...domain.resume import short

    refusal = career_refusal(store, state)
    if refusal:
        return [refusal], []
    fails = short.shape(doc, target)
    if fails:
        # Until the shape is right the ids may not be lists of ids at all.
        return fails, []
    fails = short.ids(doc, store)
    career = Career(store.graph(KB))
    live = set(career.live("Achievement"))
    bullets = [b for b in (O.K + i for i in doc["bullets"]) if b in live]
    fails += numbers_lines(queries, bullets)
    vocabulary = Vocabulary(queries)
    texts = list(prose(doc, career, bullets))
    warns = label_lines(store, career, bullets, vocabulary)
    warns += years_lines(store, texts, vocabulary, today)
    warns += bracket_lines(texts)
    return fails, warns
