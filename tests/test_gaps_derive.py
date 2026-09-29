"""gapsderive: the assessment the match already knows, over the match fixtures.

tests/match_fixtures/ carries every bucket between its four postings, so each basis
sentence is pinned against a real match result, not a hand-built one.
"""
import datetime
import re
import time
import unittest
from pathlib import Path

from jsk.graph import gapsderive as G
from jsk.graph import match as M
from jsk.graph import ontology as O
from jsk.graph import store

FIXTURES = Path(__file__).parent / "match_fixtures"
TODAY = datetime.date(2026, 9, 24)
POSTINGS = ("contoso", "fabrikam", "northwind", "tailspin")


def req(asked, verdict="satisfied", necessity="required"):
    return {"asked": asked, "verdict": verdict, "necessity": necessity}


class Derive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from appkit import stored_copy
        root = stored_copy(FIXTURES)
        cls.s = store.load(root, vocabulary=root / "vocabulary.ttl")
        cls.r = {p: M.result(cls.s, O.K + "post_" + p, TODAY, 3) for p in POSTINGS}
        cls.d = {p: G.derive(cls.r[p], cls.s) for p in POSTINGS}

    def row(self, posting, slug):
        return next(x for x in self.d[posting].rows if x.slug == slug)

    def test_one_row_per_requirement_with_the_posting_ttl_slugs(self):
        for p in POSTINGS:
            text = (FIXTURES / "applications" / p / "posting.ttl").read_text(encoding="utf-8")
            ids = set(re.findall(rf"k:req_{p}_(\w+)", text))
            d = self.d[p]
            self.assertEqual((d.posting, d.stem), (f"k:post_{p}", p))
            self.assertEqual([x.slug for x in d.rows],
                             [q["id"].removeprefix(f"k:req_{p}_") for q in self.r[p]["requirements"]])
            self.assertEqual({x.slug for x in d.rows}, ids)

    def test_satisfied(self):
        x = self.row("contoso", "k8s")
        self.assertEqual((x.matched, x.evidence, x.basis),
                         ("satisfied", ("k:prj_events",), "confirmed on prj_events"))

    def test_unevidenced(self):
        x = self.row("contoso", "dotnet")
        self.assertEqual((x.matched, x.evidence, x.basis),
                         ("unevidenced", ("k:prj_events", "k:prj_identity"),
                          "carried by prj_events (tag), prj_identity (tag) only"))
        self.assertEqual(self.row("northwind", "python").basis,
                         "carried by prj_data (unconfirmed) only")

    def test_near(self):
        x = self.row("contoso", "eks")
        self.assertEqual((x.matched, x.evidence, x.basis),
                         ("partial", ("k:prj_data",), "prj_data: holds broader c:kubernetes"))
        iac = self.row("contoso", "iac")
        self.assertEqual(iac.evidence, ("k:prj_data", "k:prj_events", "k:prj_identity"))
        # One project's reason per ` / `: a reason holds its own `;`.
        self.assertEqual(len(iac.basis.split(" / ")), 3)

    def test_missing(self):
        x = self.row("fabrikam", "angular")
        self.assertEqual((x.matched, x.evidence, x.basis),
                         ("unsatisfied", (), "nothing in the record holds c:angular"))

    def test_ambiguous(self):
        x = self.row("contoso", "go")
        self.assertEqual((x.matched, x.evidence, x.basis),
                         ("indeterminate", (), "names several concepts: c:go-game, c:golang"))

    def test_candidate(self):
        x = self.row("tailspin", "azure_kubernetes")
        self.assertEqual((x.matched, x.basis), ("indeterminate", "no concept holds it"))

    def test_implicit(self):
        x = self.row("contoso", "mentoring")
        self.assertEqual((x.matched, x.evidence, x.basis), (None, (), G.IMPLICIT))

    def test_no_fixture_row_is_flagged(self):
        # Every satisfied fixture requirement names one thing, so the flag has nothing to list.
        self.assertEqual([x.slug for p in POSTINGS for x in self.d[p].rows if x.flags], [])

    def test_derive_reads_the_confirmed_bullets_for_the_flag(self):
        # prj_events' confirmed kubernetes bullet says "on AKS with Kafka".
        r = dict(self.r["contoso"])
        r["requirements"] = [dict(q, asked="Container platforms (AKS, Nomad)")
                             if q["id"] == "k:req_contoso_k8s" else q
                             for q in r["requirements"]]
        x = next(x for x in G.derive(r, self.s).rows if x.slug == "k8s")
        self.assertEqual((x.flags, x.flag_text),
                         (("listed-names",), "names Nomad; the evidence never does"))

    def test_fit_over_the_fixtures(self):
        self.assertEqual({p: self.d[p].fit for p in POSTINGS},
                         {"contoso": "partial", "fabrikam": "poor", "northwind": "partial",
                          "tailspin": "strong"})

    def test_questions_in_the_analysts_order_without_markers_or_slots(self):
        q = self.d["fabrikam"].questions
        self.assertTrue(q[0].startswith("**unsatisfied** .NET Framework: required"))
        self.assertTrue(q[1].startswith("**tag-only** SQL Server"))
        self.assertTrue(q[-1].startswith("**missing-metric**"))
        for p in POSTINGS:
            for line in self.d[p].questions:
                self.assertFalse(line.startswith("- "), line)
                self.assertNotIn("<!-- jsk:", line)
        kinds = [line.split("**")[1] for line in self.d["contoso"].questions]
        self.assertEqual(kinds, ["broader-held", "implied", "tag-only", "missing-metric",
                                 "ambiguous", "unknown-term"])

    def test_derive_is_fast(self):
        big = max(POSTINGS, key=lambda p: len(self.r[p]["requirements"]))
        start = time.perf_counter()
        G.derive(self.r[big], self.s)
        self.assertLess(time.perf_counter() - start, 1.0)


class SlugOf(unittest.TestCase):
    def test_a_built_posting_and_a_migrated_one(self):
        """A migrated posting's requirement ids need not carry its stem: on the real corpus
        post_elevenlabs_creative_studio asks req_elevenlabs_api_design, and the stem-stripped
        slug came out `k:req_…`, which the writer refused."""
        self.assertEqual(G.slug_of("k:req_contoso_k8s", "contoso"), "k8s")
        self.assertEqual(G.slug_of("k:req_elevenlabs_api_design", "elevenlabs_creative_studio"),
                         "elevenlabs_api_design")
        self.assertRegex(G.slug_of("k:req_elevenlabs_api_design", "elevenlabs_creative_studio"),
                         rf"\A{O.SLUG}\Z")


class Fit(unittest.TestCase):
    def fit(self, *reqs):
        return G.fit_default({"requirements": list(reqs)})

    def test_poor_when_a_required_one_is_unsatisfied(self):
        self.assertEqual(self.fit(req("a"), req("b", "unsatisfied")), "poor")

    def test_strong_when_every_required_one_is_satisfied(self):
        self.assertEqual(self.fit(req("a"), req("b", "unsatisfied", "preferred")), "strong")

    def test_partial_otherwise(self):
        self.assertEqual(self.fit(req("a"), req("b", "partial")), "partial")
        self.assertEqual(self.fit(req("a", "satisfied", "preferred")), "partial")   # none required


class ListedNames(unittest.TestCase):
    def test_fires_on_products_the_evidence_never_names(self):
        self.assertEqual(
            G.listed_names(req("Vector databases (Pinecone, Weaviate, Milvus)"),
                           ["Built a Postgres+pgvector store."]),
            "names Pinecone, Weaviate, Milvus; the evidence never does")

    def test_names_only_the_missing_items(self):
        self.assertEqual(
            G.listed_names(req("Vector databases (Pinecone, Weaviate, Milvus)"),
                           ["Moved search from Pinecone to Milvus."]),
            "names Weaviate; the evidence never does")

    def test_quiet_when_every_item_is_named(self):
        self.assertIsNone(G.listed_names(req("Gemini, Cursor, and Claude"),
                                         ["Shipped with Gemini and Cursor, reviewed by Claude."]))

    def test_the_heading_is_not_an_item(self):
        self.assertEqual(G.listed_names(req("SQL Server: Stored procedures, queries"), []),
                         "names Stored procedures, queries; the evidence never does")

    def test_quiet_when_nothing_is_listed(self):
        self.assertIsNone(G.listed_names(req("Kubernetes"), []))
        self.assertIsNone(G.listed_names(req("CI/CD"), []))

    def test_never_fires_on_a_row_that_is_not_satisfied(self):
        for verdict in ("partial", "unevidenced", "unsatisfied", "indeterminate", None):
            self.assertIsNone(G.listed_names(
                req("Vector databases (Pinecone, Weaviate, Milvus)", verdict), []))


if __name__ == "__main__":
    unittest.main()
