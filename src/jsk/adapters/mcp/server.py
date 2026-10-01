"""The MCP tools: the career and graph-native applications, read and written as typed calls.

Ruling 18 of docs/superpowers/plans/2026-10-01-graph-native-applications-mcp.md names the
eighteen tools and their parameters; this module registers them on a FastMCP server and
holds no logic a CLI test could not reach. Each tool binds through adapters/cli/compose/ -
native.py for an application, career.py for the career - and turns what comes back into
JSON.

Ruling 16: every result is `{"ok": true, ...}` or `{"ok": false, "findings": [...]}`, each
finding `{severity, text, fix}`. A refusal (application or record) is its findings, never a
traceback; an unexpected exception is one FAIL naming the tool, its traceback on stderr, and
the server keeps serving - the precedent is dispatch.call_gate. Ruling 17: the clock is read
once per call (session.today) and passed down. Ruling 14: a writing tool's compose function
takes the writers' turn for that call alone; reads share session.py's cached record.

stdout is the protocol's channel under stdio, so each call runs with stdout pointed at
stderr: a stray print anywhere below would otherwise corrupt the session's next message.

Long reads page (`offset`, `limit`) and stay under ~10k tokens by default: Claude Code
warns at 10k and saves a result past 25k to a file (P0 results, item 5).

Three tools and one branch of career_confirm wrap P3b's use cases (the selection and the
ship), which are not merged yet. They are registered with their final schemas and look up
their compose functions by name at each call (PENDING); until those exist they answer
"not built yet" as a FAIL finding.
"""
import contextlib
import dataclasses
import importlib
import sys
import traceback
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from . import session as S
from .schemas import Ask, Drop, Header, Requirement, Verdict

# Characters of the career's Markdown one career_view page carries: about 7.5k tokens at
# four characters a token, under the 10k at which Claude Code warns (P0 results, item 5).
VIEW_PAGE = 30000
# Advert lines one app_show page carries. A line with its concepts and flags runs to some
# 300 characters as JSON; 80 of them is about 6k tokens, and most adverts fit in one page.
LINES_PAGE = 80
# How many projects of the match's ranking assessment_derive returns: the cover uses at
# most three (application/posting/native.COVER), and the rest is for the reviewer's eye.
RANKING = 10

# Where P3b's compose functions are looked for, in order, by name: native.py holds P3a's
# wrappers, and a module of the selection's own is the other likely home.
PENDING = ("native", "selection")

# The parts app_show reads. `selection` is P3b's; until application/tailor/show.py knows
# it, asking for it is answered as not built yet.
PARTS = Literal["posting", "lines", "requirements", "review", "assessment", "selection"]


def finding(severity, text, fix=None):
    """One finding as JSON, its fix in one spelling: its words alone, or None."""
    fix = (fix or "").strip()
    return {"severity": severity, "text": str(text),
            "fix": fix.removeprefix("fix:").strip() or None}


def result(findings=(), **data):
    """A tool's answer: ok unless a finding is a FAIL, the findings, then the data.

    Args:
        findings: (severity, text, fix) triples, or finding dicts.
        **data: the rest of the answer.
    """
    found = [f if isinstance(f, dict) else finding(*f) for f in findings]
    return {"ok": not any(f["severity"] == "FAIL" for f in found), "findings": found,
            **data}


def failed(*findings):
    """A refusal: ok false and its findings, each (severity, text, fix)."""
    return result(findings)


def plain(value):
    """`value` as JSON's types: a dataclass as a dict, a tuple or set as a list."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(plain(v) for v in value)
    return value


def fields(value) -> dict[str, Any]:
    """`value` (a dataclass or a dict) as a dict of its fields in JSON's types, to spread
    into result()."""
    out = plain(value)
    if not isinstance(out, dict):
        raise TypeError(f"expected a result with fields, got {type(value).__name__}")
    return out


def curies(iris):
    """Sorted curies of `iris`."""
    from ...domain.record.writer import curie

    return sorted(curie(i) for i in iris)


def refusal_findings(err):
    """The findings a refusal raised below carries, or None for an exception that is not
    one. Every refusal type the use cases raise is here, so none reaches the catch-all."""
    from ...application.record.refusals import Failing, Problems, Unclean
    from ...application.record.refusals import Refused as RecordRefused
    from ...domain.posting.errors import Refused
    from ...domain.record.parsed import GraphError
    from ...domain.record.state import RecordError
    from ..cli.presenters import GUIDE

    if isinstance(err, Refused):
        return [("FAIL", m, f) for m, f in err.problems]
    if isinstance(err, RecordRefused):
        return [("FAIL", line, err.fix) for line in err.lines] or [("FAIL", str(err), err.fix)]
    if isinstance(err, Problems):
        return [("FAIL", d, f) for d, f in err.problems]
    if isinstance(err, Failing):
        return [("FAIL", f"{f.file}{' ' + f.focus if f.focus else ''} - {f.detail}", f.fix)
                for f in err.findings] or [("FAIL", err.title, None)]
    if isinstance(err, Unclean):
        message, fix = GUIDE.get(err.state.kind, (None, "`jsk kb check` says why"))
        return [("FAIL", message or err.state.detail or err.state.kind, fix)]
    if isinstance(err, (RecordError, GraphError)):
        return [("FAIL", str(err), err.fix)]
    return None


class Tools:
    """The calls every tool makes alike, over one Session."""

    def __init__(self, session):
        self.session = session

    def call(self, tool, fn, writes=False):
        """`fn(root, today)`'s answer, or the findings of why there is none.

        Args:
            tool: the tool's name, for a FAIL an unexpected exception becomes.
            fn: (root, today) -> the answer, a dict made by result().
            writes: whether it may write, so the read cache is dropped after it.
        """
        from ...application.guards import unloaded_refusal

        root = self.session.workspace()
        if root is None:
            return failed(("FAIL", "no workspace: no career/store/ here or above, and no "
                                   f"{S.ROOT_ENV}",
                           "`jsk kb new PATH --name NAME` creates one; start the server "
                           f"inside it, or set {S.ROOT_ENV}"))
        unloaded = unloaded_refusal(root)
        if unloaded:
            return failed(("FAIL", unloaded[0], unloaded[1]))
        today = S.today()
        try:
            with contextlib.redirect_stdout(sys.stderr):
                return fn(root, today)
        except Exception as err:                # noqa: BLE001 - the server outlives one tool
            # A refusal is the answer; anything else is a bug in what the tool called, and
            # one bad call must not take the session's other tools down with it (Ruling 16).
            found = refusal_findings(err)
            if found is not None:
                return failed(*found)
            traceback.print_exc(file=sys.stderr)
            return failed(("FAIL", f"{tool} raised {type(err).__name__}: {err}",
                           "the traceback is on the server's stderr; the same call through "
                           "`jsk` shows it too - report it"))
        finally:
            if writes:
                self.session.wrote()

    def pending(self, tool, name):
        """P3b's compose function `name`, or None while it is not built."""
        for module in PENDING:
            try:
                found = importlib.import_module(f"..cli.compose.{module}", __package__)
            except ImportError:
                continue
            fn = getattr(found, name, None)
            if callable(fn):
                return fn
        return None

    @staticmethod
    def not_built(tool):
        """The answer a P3b tool gives until its use case is merged."""
        return failed(("FAIL", "not built yet",
                       f"{tool} arrives with the selection's use cases (P3b of the plan); "
                       "until then the file path's `jsk kb export` and `jsk resume ship` do "
                       "its work"))


def page(text, offset, limit):
    """(the slice of `text` from `offset`, cut back to a line's end, the next offset or None)."""
    offset = max(0, offset)
    chunk = text[offset:offset + max(1, limit)]
    end = offset + len(chunk)
    if end < len(text):
        cut = chunk.rfind("\n")
        if cut > 0:
            chunk = chunk[:cut + 1]
            end = offset + len(chunk)
    return chunk, (end if end < len(text) else None)


def written_of(w):
    """A logged write of the career, as JSON."""
    if w is None:
        return result(changed=False, written=False)
    return result(changed=True, written=w.written, revision=w.revision, diff=w.diff,
                  minted=curies(w.minted), touched=curies(w.touched), notes=list(w.notes))


def build(session=None):
    """The FastMCP server with its eighteen tools, over `session` (a fresh Session when None)."""
    tools = Tools(session or S.Session())
    srv = FastMCP("jsk")
    for register in (career_reads, career_writes, applications, postings, assessments,
                     resumes):
        register(srv, tools)
    return srv


def described(srv):
    """description -> the decorator registering a tool on `srv` with it. Unstructured: a
    typed result would add an output schema to every definition (tests/test_budget.py)."""
    def tool(description):
        return srv.tool(description=description, structured_output=False)
    return tool


def career_reads(srv, tools):
    """career_view, career_show, career_query and career_log, from the read cache."""
    from ..cli.compose import career

    tool, load = described(srv), tools.session.load

    @tool("The career as Markdown, paged. section: one section only. Next page: pass `next`.")
    def career_view(section: str | None = None, offset: int = 0,
                    limit: int = VIEW_PAGE) -> dict:
        def run(root, today):
            text, nxt = page(career.view(root, section, load=load), offset, limit)
            return result(text=text, offset=offset, next=nxt)
        return tools.call("career_view", run)

    @tool("Entries by id as Turtle, with the revision a changeset's op:base names. "
          "bullets: a project's name and bullets only.")
    def career_show(ids: list[str], bullets: bool = False) -> dict:
        def run(root, today):
            shown = career.show(root, ids, bullets, load=load)
            missing = [("FAIL",) + e.missing for e in shown.entries if e.missing]
            return result(missing, base=shown.log_revision,
                          entries=[{"id": e.text, "graphs": [
                              {"graph": g, "heading": h, "turtle": t} for g, h, t in e.graphs]}
                              for e in shown.entries if not e.missing])
        return tools.call("career_show", run)

    @tool("A named query (as `jsk kb query`): rows as JSON. args: its arguments; for "
          "concepts, terms to find the nearest concepts to.")
    def career_query(name: str, args: list[str] | None = None) -> dict:
        def run(root, today):
            got = career.query(root, name, args or (), today=today, load=load)
            if isinstance(got, dict):
                return result(near={t: {"columns": list(c), "rows": plain(r)}
                                    for t, (c, r) in got.items()})
            columns, rows = got
            return result(columns=list(columns), rows=plain(rows))
        return tools.call("career_query", run)

    @tool("The record's history, newest first.")
    def career_log(last: int = 10) -> dict:
        def run(root, today):
            if last < 1:
                return failed(("FAIL", f"last {last}: a count, 1 or more", "pass 1 or more"))
            return result(entries=[{"revision": e.revision, "date": e.date, "by": e.by,
                                    "summary": e.summary, "minted": curies(e.minted),
                                    "touched": curies(e.touched)}
                                   for e in career.log(root, last, load=load)])
        return tools.call("career_log", run)


def career_writes(srv, tools):
    """career_preview, career_apply and career_confirm: each write in its own turn."""
    from ..cli.compose import career

    tool = described(srv)

    @tool("Dry-run a TriG changeset: the diff and findings; nothing written.")
    def career_preview(changeset: str) -> dict:
        def run(root, today):
            return written_of(career.apply_changeset(root, changeset, dry_run=True,
                                                     today=today))
        return tools.call("career_preview", run)

    @tool("Apply a TriG changeset: validated, written and logged. New claims arrive inferred.")
    def career_apply(changeset: str) -> dict:
        def run(root, today):
            return written_of(career.apply_changeset(root, changeset, today=today))
        return tools.call("career_apply", run, writes=True)

    @tool("Confirm entries (ids) with the person's own answer, or a document's source and "
          "quote; or a selection's summary or headline (target, block).")
    def career_confirm(ids: list[str] | None = None, target: str | None = None,
                       block: Literal["summary", "headline"] | None = None,
                       answer: str | None = None, source: str | None = None,
                       quote: str | None = None) -> dict:
        def run(root, today):
            if (source is None) != (quote is None):
                return failed(("FAIL", "source and quote go together: the file, and the "
                                       "words in it", "pass both, or answer instead"))
            if source is not None and answer is not None:
                return failed(("FAIL", "answer, or source and quote: two ways to confirm",
                               "pass one"))
            if target is not None or block is not None:
                if ids or target is None or block is None or answer is None:
                    return failed(("FAIL", "a selection's block is confirmed alone: target, "
                                           "block and the person's answer, no ids",
                                   "pass target, block and answer"))
                fn = tools.pending("career_confirm", "confirm_summary")
                if fn is None:
                    return Tools.not_built("career_confirm (target, block)")
                return result(**fields(fn(root, target, block, answer, today=today)))
            if not ids or (answer is None and source is None):
                return failed(("FAIL", "confirm takes ids and the person's answer, or a "
                                       "source and its quote",
                               "pass ids with answer (their words), or source and quote"))
            return written_of(career.confirm_ids(root, ids, answer=answer, source=source,
                                                 quote=quote, today=today))
        return tools.call("career_confirm", run, writes=True)


def applications(srv, tools):
    """app_list and app_show, from the read cache."""
    from ..cli.compose import native

    tool, ports = described(srv), tools.session.ports

    @tool("Every application and general resume: kind, posting and review state, stage.")
    def app_list() -> dict:
        def run(root, today):
            return result(**fields(native.list_apps(root, today=today, ports=ports())))
        return tools.call("app_list", run)

    @tool("One part of a graph-native application as JSON. lines pages by offset and limit.")
    def app_show(app: str, part: PARTS, offset: int = 0, limit: int = LINES_PAGE) -> dict:
        def run(root, today):
            from ...application.tailor.show import PARTS as KNOWN

            if part == "selection" and part not in KNOWN:
                return Tools.not_built("app_show (selection)")
            got = native.show(root, app, part, today=today, ports=ports())
            if part == "lines":
                start = max(0, offset)
                end = start + max(1, limit)
                rows = list(got)
                return result(lines=plain(rows[start:end]), total=len(rows),
                              next=end if end < len(rows) else None)
            return result(**{str(part): plain(got)})
        return tools.call("app_show", run)


def postings(srv, tools):
    """posting_capture, posting_decide and posting_complete."""
    from ..cli.compose import native

    tool = described(srv)

    @tool("Store an advert - fetched from url, or pasted text - as a draft posting's "
          "numbered lines. replace: capture again, dropping its review and assessment.")
    def posting_capture(app: str, url: str | None = None, text: str | None = None,
                        company: str | None = None, title: str | None = None,
                        captured: str | None = None, replace: bool = False) -> dict:
        def run(root, today):
            done = native.capture(root, app, url=url, text=text, company=company,
                                  title=title, captured=captured, replace=replace, today=today)
            return result(**fields(done))
        return tools.call("posting_capture", run, writes=True)

    @tool("Upsert requirement rows and drops into a posting, each checked against its line; "
          "a FAIL writes nothing. remove: slugs to delete.")
    def posting_decide(app: str, header: Header | None = None,
                       requirements: list[Requirement] | None = None,
                       drops: list[Drop] | None = None,
                       remove: list[str] | None = None) -> dict:
        def run(root, today):
            done = native.decide(root, app, header=dict(header) if header else None,
                                 rows=requirements or (), drops=drops or (),
                                 remove=remove or (), today=today)
            return result(done.findings, target=done.target, requirements=done.requirements,
                          state=done.state, written=list(done.written))
        return tools.call("posting_decide", run, writes=True)

    @tool("Settle a posting: every qualification line used or dropped, the rules clean; "
          "then complete.")
    def posting_complete(app: str) -> dict:
        def run(root, today):
            done = native.complete_posting(root, app, today=today)
            return result(done.findings, target=done.target, requirements=done.requirements,
                          state=done.state, written=list(done.written))
        return tools.call("posting_complete", run, writes=True)


def assessments(srv, tools):
    """assessment_derive, assessment_review and assessment_complete."""
    from ..cli.compose import native

    tool = described(srv)

    @tool("Match the posting, fold the stored review in, write the assessment; its rows, "
          "fit and questions.")
    def assessment_derive(app: str) -> dict:
        def run(root, today):
            a = native.derive_assessment(root, app, today=today)
            r = a.result
            return result(a.findings, fit=a.fit, eligibility=a.eligibility,
                          rows=plain(a.rows), questions=plain(a.questions),
                          short=list(a.short), surplus=list(a.surplus),
                          cover=plain(r.get("cover")),
                          ranking=plain((r.get("ranking") or [])[:RANKING]),
                          warnings=plain(r.get("warnings") or []), written=list(a.written))
        return tools.call("assessment_derive", run, writes=True)

    @tool("Upsert the review: fit, eligibility, verdicts (lowered only, with a reason, or "
          "keep), and the short, surplus and asks lists, each replaced when given.")
    def assessment_review(app: str, fit: str | None = None, eligibility: str | None = None,
                          verdicts: list[Verdict] | None = None,
                          short: list[str] | None = None, surplus: list[str] | None = None,
                          asks: list[Ask] | None = None) -> dict:
        def run(root, today):
            warned = [("WARN", f"asks[{i}]: `about` is not kept by the review yet; the "
                               "question is stored without it", None)
                      for i, a in enumerate(asks or (), 1) if a.get("about")]
            done = native.review(root, app, fit=fit, eligibility=eligibility,
                                 verdicts=verdicts or (), short=short, surplus=surplus,
                                 asks=None if asks is None else [a["question"] for a in asks],
                                 today=today)
            return result(list(done.findings) + warned, target=done.target, state=done.state,
                          fit=done.fit, written=list(done.written))
        return tools.call("assessment_review", run, writes=True)

    @tool("Settle the review: every flag answered, no FAIL against the match; then complete.")
    def assessment_complete(app: str) -> dict:
        def run(root, today):
            done = native.complete_review(root, app, today=today)
            return result(done.findings, target=done.target, state=done.state, fit=done.fit,
                          written=list(done.written))
        return tools.call("assessment_complete", run, writes=True)


def resumes(srv, tools):
    """resume_select, resume_update and resume_ship: P3b's, looked up at each call."""
    tool = described(srv)

    @tool("Choose a resume's bullets and store the selection. target: an application's stem "
          "or resumes/<name>.")
    def resume_select(target: str, mode: Literal["from_match", "ranked"],
                      replace: bool = False) -> dict:
        def run(root, today):
            fn = tools.pending("resume_select", "selection_select")
            if fn is None:
                return Tools.not_built("resume_select")
            return result(**fields(fn(root, target, mode, replace=replace, today=today)))
        return tools.call("resume_select", run, writes=True)

    @tool("Change a stored selection. A changed summary or headline text drops back to "
          "inferred.")
    def resume_update(target: str, bullets: list[str] | None = None,
                      roles: list[str] | None = None, skills: list[str] | None = None,
                      names: dict[str, str] | None = None, format: str | None = None,
                      region: str | None = None, pages: int | None = None,
                      ats_pages: int | None = None, floor: str | None = None,
                      summary: str | None = None, headline: str | None = None) -> dict:
        given = {k: v for k, v in (("bullets", bullets), ("roles", roles), ("skills", skills),
                                   ("names", names), ("format", format), ("region", region),
                                   ("pages", pages), ("ats_pages", ats_pages),
                                   ("floor", floor), ("summary", summary),
                                   ("headline", headline)) if v is not None}

        def run(root, today):
            fn = tools.pending("resume_update", "selection_update")
            if fn is None:
                return Tools.not_built("resume_update")
            return result(**fields(fn(root, target, today=today, **given)))
        return tools.call("resume_update", run, writes=True)

    @tool("Record gate, render, fit and every gate, into the application's directory; each "
          "step as JSON.")
    def resume_ship(target: str, ats_max: bool = False, template: str | None = None,
                    pages: int | None = None, fit: bool = True) -> dict:
        def run(root, today):
            fn = tools.pending("resume_ship", "ship_target")
            if fn is None:
                return Tools.not_built("resume_ship")
            return result(**fields(fn(root, target, ats_max=ats_max, template=template,
                                     pages=pages, fit=fit, today=today)))
        return tools.call("resume_ship", run, writes=True)


def serve():
    """Serve the tools over stdio until the client closes the session."""
    build().run("stdio")
