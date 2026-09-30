"""A changeset merged into the career, and the refusals only the career can answer.

changeset.py has already refused what a changeset may never say. What is left needs the
record: does the entry exist, is anything pointing at it, was this metric version sent,
did somebody change the same entry since the changeset was drafted.

Four things happen that the changeset did not ask for, because a record that let them
be skipped would be wrong without anyone noticing:

- a claim changed is a claim unconfirmed: the entry drops to j:inferred;
- an entry left inferred gets a question, so confirming it is on somebody's list;
- a new bullet gets its id from its project and its words;
- a sent metric version never changes: a new value becomes the next version.
"""
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from ..domain import ontology as O
from .changeset import OP, Refusal, Refused, curie

PROVENANCE = O.J + "provenance"
# A version's number: changing these on a sent version makes a new version instead.
VERSIONED = {"value", "baseline", "upper", "qualifier", "kind"}
# What a new version does not inherit from the one it replaces.
NOT_INHERITED = {"validFrom", "validUntil", "provenance", "note", "retired", "reason"}
# Words that say nothing about what a bullet is; left out of the id minted for it.
STOP = frozenset("""a an the and or but of to in on for with by at from as into onto over under
via per its their our my his her was were is are be been being that this these those which who
whom than then so across up down out off it we i they them us me all any each more most""".split())


@dataclass
class Edit:
    quads: list                      # the career after the change, as quads
    touched: set = field(default_factory=set)
    minted: set = field(default_factory=set)
    notes: list = field(default_factory=list)


def node(iri):
    import pyoxigraph as ox
    return ox.NamedNode(iri)


def date(day):
    import pyoxigraph as ox
    return ox.Literal(day.isoformat(), datatype=ox.NamedNode(O.XSD + "date"))


def local(p):
    return p.value[len(O.J):] if p.value.startswith(O.J) else None


def values(triples, s, p):
    return {o for t_s, t_p, o in triples if t_s == s and t_p == p}


def claimed(triples, s, names):
    """(predicate, object) of what `s` claims through the predicates `names`."""
    return {(p, o) for t, p, o in triples if t == s and local(p) in names}


def carried_versions(store):
    """{metric version iri: [application iris]} - versions an application sent."""
    out = defaultdict(list)
    for r in store.select(f"PREFIX j: <{O.J}> SELECT ?v ?a WHERE {{ ?a j:carriedVersion ?v }}"):
        out[r["v"].value].append(r["a"].value)
    return out


def log_entries(store):
    """[(revision, {ids touched or minted})] from the log, oldest first. An entry whose
    revision is not an integer is left out: tier 1 FAILs it, and that stops the write."""
    from .record import LOG, revision_of

    if LOG not in store.parsed:
        return []
    by: defaultdict = defaultdict(lambda: {"ids": set()})     # and "revision": int
    for q in store.graph(LOG):
        e = by[q.subject.value]
        if local(q.predicate) == "revision" and revision_of(q.object) is not None:
            e["revision"] = revision_of(q.object)
        elif local(q.predicate) in ("touched", "minted"):
            e["ids"].add(q.object.value)
    return sorted((e["revision"], e["ids"]) for e in by.values() if "revision" in e)


def started_over(store):
    """The revisions `jsk new` wrote: r1, and each --force start-over since."""
    from .record import LOG, revision_of

    if LOG not in store.parsed:
        return []
    by, revs = {}, {}
    for q in store.graph(LOG):
        if local(q.predicate) == "by":
            by[q.subject.value] = q.object.value
        elif local(q.predicate) == "revision" and revision_of(q.object) is not None:
            revs[q.subject.value] = revision_of(q.object)
    return sorted(r for s, r in revs.items() if by.get(s) == O.J + "new")


def taken_ids(store):
    """Every id the record has ever used: what exists, what the log says existed, and every
    k: id any record graph names, as subject or object.

    The last is what survives `jsk kb load` of an older backup: the log no longer
    remembers a bullet or a metric version minted since, but an application that sent it
    still names it - and a new entry minted onto that id would read, in that application,
    as what it sent.
    """
    import pyoxigraph as ox

    ids = set(store.homes)
    for _, named in log_entries(store):
        ids |= named
    for parsed in store.parsed.values():
        for q in parsed.quads:
            for t in (q.subject, q.object):
                if isinstance(t, ox.NamedNode) and t.value.startswith(O.K):
                    ids.add(t.value)
    return ids


def sent_elsewhere(store):
    """k: ids an application graph names that no graph defines: what was sent, and has
    since left the career - by a delete, or by `jsk kb load` of an older backup."""
    import pyoxigraph as ox

    out = {}
    for name, parsed in store.parsed.items():
        if parsed.kind != "application":
            continue
        for q in parsed.quads:
            if isinstance(q.object, ox.NamedNode) and q.object.value.startswith(O.K) \
                    and q.object.value not in store.homes:
                out.setdefault(q.object.value, name)
    return out


def words(text):
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [w for w in re.findall(r"[a-z]+", folded) if w not in STOP and len(w) > 1]


def mint_bullet(project, text, taken):
    """ach_<project stem>_<three content words>, then four; None when both are taken or
    the text has no words - the changeset then names the bullet itself."""
    stem = project[len(O.K) + len("prj_"):]
    found = words(text)
    for n in (3, 4):
        iri = f"{O.K}ach_{stem}_{'_'.join(found[:n])}"
        if found and iri not in taken:
            return iri
    return None


def same_bullet(triples, project, text):
    """The live bullet of `project` whose text is `text`, or None."""
    of, says, retired = node(O.J + "project"), node(O.J + "text"), node(O.J + "retired")
    for s, p, o in triples:
        if p == says and o.value == text and (s, of, project) in triples \
                and not values(triples, s, retired):
            return s
    return None


def mint_question(about, taken):
    base = f"{O.K}q_{about[len(O.K):].replace('.', '_')}"
    iri, n = base, 2
    while iri in taken:
        iri, n = f"{base}_{n}", n + 1
    return iri


def apply(store, cs, today):
    """The career `cs` makes, as an Edit. Raises Refused with every reason it cannot."""
    import pyoxigraph as ox

    from .record import KB

    refusals = []

    def refuse(s, detail, fix):
        refusals.append(Refusal(curie(s.value) if isinstance(s, ox.NamedNode) else "", detail, fix))

    before = {(q.subject, q.predicate, q.object) for q in store.graph(KB)}
    in_kb = {s for s, _, _ in before}
    carried = carried_versions(store)
    # Ids the changeset names are taken too: a bullet minted onto one would merge with it.
    taken = taken_ids(store) | {s.value for s, _, _ in cs.add + cs.set + cs.retire + cs.delete
                                if isinstance(s, ox.NamedNode)}
    after = set(before)
    redirects = defaultdict(dict)          # sent version -> {predicate: objects}

    def exists(s):
        # A concept the shipped vocabulary defines exists: the career may extend or narrow it.
        return s in in_kb or (s.value.startswith(O.C) and s.value in store.homes)

    def sent(s, what):
        apps = ", ".join(curie(a) for a in sorted(carried[s.value]))
        refuse(s, f"{what}, but it was sent in {apps}", "a sent version never changes: add "
               "the new number as the next version (k:met_x.vN), and jsk closes this one")

    base_conflicts(store, cs, refuse)

    entries = {s for s, p, o in cs.delete if o == ox.NamedNode(OP + "Entry")}
    for s, p, o in cs.delete:
        if s.value in carried:
            sent(s, "op:delete")
        elif s in entries:
            if s not in in_kb:
                refuse(s, "op:delete of an entry the career does not hold", "check the id")
            after -= {t for t in after if t[0] == s}
        elif (s, p, o) not in before:
            refuse(s, f"has no {curie(p.value)} {name_of(o)} to delete", "check it against "
                   f"`jsk kb show {curie(s.value)}`")
        else:
            after.discard((s, p, o))

    grouped = defaultdict(set)
    for s, p, o in cs.set:
        grouped[(s, p)].add(o)
    for (s, p), objs in grouped.items():
        if not exists(s):
            refuse(s, "op:set on an entry that does not exist", "op:add it instead")
        elif s.value in carried and local(p) in VERSIONED:
            redirects[s][p] = objs
        elif s.value in carried:
            sent(s, f"op:set {curie(p.value)}")
        else:
            after -= {t for t in after if t[0] == s and t[1] == p}
            after |= {(s, p, o) for o in objs}

    def add(s, p, o):
        if s.value in carried:
            sent(s, f"op:add {curie(p.value)}")
            return
        # changeset.check refused every subject that is not a jsk id, so it names a class.
        pred = (O.class_named(s.value).preds.get(name)
                if (name := local(p)) else None)
        others = values(after, s, p) - {o}
        if pred and pred.card in "1?" and others and (s, p) not in grouped:
            refuse(s, f"already has {curie(p.value)} {name_of(sorted(others, key=str)[0])}",
                   "op:set replaces it; op:add only adds")
            return
        after.add((s, p, o))

    blanks = defaultdict(list)
    for s, p, o in cs.add:
        if isinstance(s, ox.BlankNode):
            blanks[s].append((p, o))
        else:
            add(s, p, o)

    # An id an application sent, that the career no longer holds, is not free to define
    # again: that application would then read as having sent the new entry.
    gone = sent_elsewhere(store)
    for s in sorted({s for s, _, _ in cs.add if isinstance(s, ox.NamedNode)} - in_kb,
                    key=lambda s: s.value):
        if s.value in gone:
            refuse(s, f"was sent in {gone[s.value]}, and the career no longer defines it",
                   "a sent id is never reused: give the new entry another id "
                   "(a metric's next free version number)")

    minted_bullets = []
    for props in blanks.values():
        project = next(o for p, o in props if local(p) == "project")
        text = next((o.value for p, o in props if local(p) == "text"), "")
        if O.class_of(project.value) != "Project":
            refuse(project, "a new bullet's j:project is not a k:prj_ id", "point it at its project")
            continue
        same = same_bullet(after, project, text)
        if same is not None:
            # Re-running an apply must not mint the bullet twice: the same words under
            # the same project are the same bullet, and what the changeset says is added
            # to it like any op:add.
            for p, o in props:
                add(same, p, o)
            continue
        iri = mint_bullet(project.value, text, taken | {x.value for x in minted_bullets})
        if iri is None:
            refuse(project, f"no id could be minted for the bullet {text[:40]!r}",
                   "name it yourself: ach_<project>_<two to four words>")
            continue
        minted_bullets.append(node(iri))
        after |= {(node(iri), p, o) for p, o in props}

    for s, p, o in cs.retire:
        if s.value in carried:
            sent(s, "op:retire")
        elif s not in in_kb:
            refuse(s, "op:retire of an entry the career does not hold", "check the id")
        elif values(after, s, node(O.J + "retired")):
            refuse(s, "is already retired", "leave it, or op:set its j:reason")
        else:
            after |= {(s, node(O.J + "retired"), date(today)), (s, p, o)}

    for e in entries:
        referenced(store, after, e, refuse)
    if refusals:
        raise Refused(refusals)

    edit = Edit([])
    for v, changes in redirects.items():
        new_version(after, v, changes, today, carried, edit, taken)
    close_versions(after, before, today, edit)
    provenance(after, before, cs, minted_bullets, edit)
    questions(after, before, today, taken, edit)

    subjects = {s for s, _, _ in after}
    old = {s for s, _, _ in before}
    edit.minted |= {s.value for s in subjects - old}
    edit.touched = {s.value for s, _, _ in before ^ after} - edit.minted
    for b in minted_bullets:
        edit.notes.append(f"minted {curie(b.value)}")
    edit.quads = [ox.Quad(s, p, o) for s, p, o in after]
    return edit


def name_of(o):
    import pyoxigraph as ox
    return curie(o.value) if isinstance(o, ox.NamedNode) else repr(o.value)


def base_conflicts(store, cs, refuse):
    """op:base rN: refused when an entry this changeset names changed after rN. The log
    records ids, not predicates, so two edits of one entry conflict even when they
    touch different fields - re-reading it is cheap, a silent overwrite is not."""
    import pyoxigraph as ox

    if cs.base is None:
        return
    entries = log_entries(store)
    last = entries[-1][0] if entries else 0
    if cs.base > last:
        refuse(None, f"op:base r{cs.base} is ahead of the log, which ends at r{last}",
               "draft against the record as it is: `jsk kb show` the entries again")
        return
    # `jsk new --force` replaced the whole career and logs no ids: a changeset drafted
    # before it was drafted against a record that is gone, whatever it names.
    restart = max(started_over(store), default=None)
    if restart is not None and restart > cs.base:
        refuse(None, f"the career was started over at r{restart} (`jsk new --force`), after "
                     f"this changeset's op:base r{cs.base}",
               "draft it again against the record as it is now: `jsk kb show` what it names")
        return
    named = {s.value for s, _, _ in cs.add + cs.set + cs.retire + cs.delete
             if isinstance(s, ox.NamedNode)}
    for rev, ids in entries:
        if rev > cs.base:
            for iri in sorted(named & ids):
                refuse(node(iri), f"changed at r{rev}, after this changeset's op:base r{cs.base}",
                       f"re-read it with `jsk kb show {curie(iri)}` and redraft against r{last}")


def referenced(store, after, e, refuse):
    """An entry is deleted only when nothing points at it; otherwise it is retired."""
    from .record import KB
    from ..domain.naming import graph_iri

    if [f for f in store.definitions.get(e.value, []) if f != KB]:
        return      # the shipped vocabulary still defines it: removing the career's part is safe
    refs = sorted({curie(s.value) for s, _, o in after if o == e})
    rows = store.select(f"""PREFIX j: <{O.J}> SELECT DISTINCT ?s WHERE {{ GRAPH ?g {{ ?s ?p <{e.value}> }}
        FILTER(?g != j:derived && ?g != <{graph_iri(KB)}>) FILTER(?p NOT IN (j:touched, j:minted)) }}""")
    refs += sorted(curie(r["s"].value) for r in rows)
    if refs:
        refuse(e, f"is referenced by {', '.join(refs)}",
               "retire it (op:retire with a j:reason) - or remove those references first")


def version_number(iri):
    return int(iri.rsplit(".v", 1)[1])


def versions_of(triples, metric):
    of = node(O.J + "of")
    return sorted({s for s, p, o in triples if p == of and o == metric},
                  key=lambda s: version_number(s.value))


def new_version(after, v, changes, today, carried, edit, taken: "set | frozenset" = frozenset()):
    """A sent version's new number, as the next version of its metric - the next number
    no graph has used, so a version an application still names after `jsk kb load` of an
    older backup is never minted again with another value."""
    of = node(O.J + "of")
    metric = next(o for s, p, o in after if s == v and p == of)
    n = max(version_number(x.value) for x in versions_of(after, metric)) + 1
    while f"{metric.value}.v{n}" in taken or node(f"{metric.value}.v{n}") in {s for s, _, _ in after}:
        n += 1
    new = node(f"{metric.value}.v{n}")
    copy = {(new, p, o) for s, p, o in after if s == v and local(p) not in NOT_INHERITED
            and p not in changes}
    copy |= {(new, p, o) for p, objs in changes.items() for o in objs}
    copy.add((new, node(O.J + "validFrom"), date(today)))
    after |= copy
    apps = ", ".join(curie(a) for a in sorted(carried[v.value]))
    edit.notes.append(f"{curie(v.value)} was sent in {apps}, so it stays as it was: the new "
                      f"number is {curie(new.value)}")


def close_versions(after, before, today, edit):
    """Exactly one version of a metric is current. When this change adds one, the one it
    replaces is closed - the day the new one starts, or today. Closing is the one change
    a sent version takes: its number is what was sent, and that does not change."""
    until, start = node(O.J + "validUntil"), node(O.J + "validFrom")
    new = {s for s, _, _ in after} - {s for s, _, _ in before}
    metrics = {o for s, p, o in after if s in new and p == node(O.J + "of")}
    for m in metrics:
        vs = versions_of(after, m)
        open_ = [x for x in vs if not values(after, x, until)]
        for x in open_[:-1]:
            later = [y for y in vs if version_number(y.value) > version_number(x.value)]
            day = next(iter(values(after, later[0], start)), None) if later else None
            after.add((x, until, day if day is not None else date(today)))
            edit.notes.append(f"closed {curie(x.value)}: {curie(open_[-1].value)} is current")


def provenance(after, before, cs, minted_bullets, edit):
    """A new entry is inferred until confirmed; an entry whose claims changed is too,
    unless the changeset said what it is (it may say anything but confirmed)."""
    stated = {s for s, p, _ in cs.add + cs.set if p.value == PROVENANCE}
    stated |= {b for b in minted_bullets if values(after, b, node(PROVENANCE))}
    inferred = node(O.J + "inferred")
    old = {s for s, _, _ in before}
    for s in sorted({s for s, _, _ in after}, key=lambda s: s.value):
        # apply refuses a career that FAILs, and check() a changeset subject that is not a
        # jsk id, so every subject names a class.
        cls = O.class_named(s.value)
        if not cls.claims or s in stated:
            continue
        if s not in old:
            if not values(after, s, node(PROVENANCE)):
                after.add((s, node(PROVENANCE), inferred))
            continue
        names = O.resets(cls)
        if claimed(before, s, names) != claimed(after, s, names):
            was = values(after, s, node(PROVENANCE))
            # Down to inferred, never up: a disputed or unverified entry reworded is
            # still disputed or unverified.
            if not was or node(O.J + "confirmed") in was:
                after.difference_update({(s, node(PROVENANCE), o) for o in was})
                after.add((s, node(PROVENANCE), inferred))
                changed = sorted({curie(p.value) for p, _ in
                                  claimed(before, s, names) ^ claimed(after, s, names)})
                edit.notes.append(f"{curie(s.value)} is now inferred: {', '.join(changed)} changed")


def questions(after, before, today, taken, edit):
    """Every entry this change left inferred or unverified gets a question about it,
    unless one is already open - otherwise nothing asks for it to be confirmed."""
    import pyoxigraph as ox

    about, answered = node(O.J + "about"), node(O.J + "answered")
    unsure = {node(O.J + "inferred"), node(O.J + "needs-verification")}
    open_about = {o for q, p, o in after if p == about and not values(after, q, answered)}
    changed = {s for s, _, _ in before ^ after}
    minted = set()
    for s in sorted(changed, key=lambda s: s.value):
        if values(after, s, node(PROVENANCE)) & unsure and s not in open_about:
            q = node(mint_question(s.value, taken | minted))
            minted.add(q.value)
            after |= {(q, about, s), (q, node(O.J + "question"), ox.Literal(ask(after, s))),
                      (q, node(O.J + "asked"), date(today))}
            edit.notes.append(f"asked {curie(q.value)} about {curie(s.value)}")


def ask(after, s):
    """The question, ready to ask aloud."""
    def get(pred):
        found = values(after, s, node(O.J + pred))
        return next(iter(found)).value if found else None
    cls = O.class_of(s.value)
    if cls == "Achievement":
        return f"Is this bullet true as written: \"{get('text')}\"?"
    if cls == "MetricVersion":
        metric = next(iter(values(after, s, node(O.J + "of"))))
        subject = next((o.value for t, p, o in after if t == metric and local(p) == "subject"), "it")
        unit = next((o.value for t, p, o in after if t == metric and local(p) == "unit"), "")
        qualifier = get("qualifier")
        now = O.stated(get("value"), get("upper"), qualifier and qualifier[len(O.J):])
        span = f"from {get('baseline')} to {now}" if get("baseline") else now
        return f"Is {span}{' ' + unit if unit else ''} right for {subject}?"
    return f"Is {curie(s.value)} right as now recorded?"
