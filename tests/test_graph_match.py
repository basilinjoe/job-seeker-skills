"""The graph simulation's scenarios, through `jsk match`'s queries.

tests/match_fixtures/ is the simulation's career and four postings written as Turtle, with
the simulation's vocabulary as a test-only vocabulary.ttl so the answers below - worked
by hand in docs/superpowers/experiments/2026-09-24-graph-simulation/ - do not move when
the shipped vocabulary grows. One deliberate difference: the simulation called a
requirement with only near carriers `missing`; the P2 spec gives it its own bucket,
`near`, because "you hold something close" is a different conversation from "you do not".
"""
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

from jsk.domain import ontology as O
from jsk.adapters.cli.compose import match
from jsk.domain.matching import cover, model, resolve
from jsk.adapters.cli.compose import record

FIXTURES = Path(__file__).parent / "match_fixtures"
TODAY = datetime.date(2026, 9, 24)

# Which projects honestly carry each requirement - the simulation's TRUTH, by hand.
TRUTH = {
    ("contoso", "K8s"): {"events", "data"}, ("contoso", "Terraform"): {"events", "data"},
    ("contoso", "Infrastructure as Code"): set(), ("contoso", "Azure AD"): {"identity"},
    ("contoso", "Go"): set(), ("contoso", ".NET"): {"events", "identity"}, ("contoso", "EKS"): set(),
    ("contoso", "K3s"): set(), ("contoso", "Team leadership"): {"events"},
    ("fabrikam", ".NET Framework"): set(), ("fabrikam", "SQL Server"): {"portal"},
    ("fabrikam", "Angular"): set(), ("fabrikam", "Terraform"): {"events", "data"},
    ("northwind", "Python"): {"data"}, ("northwind", "Kafka"): {"events", "identity"},
    ("northwind", "Terraform"): {"events", "data"},
    ("northwind", "Event-driven architecture"): {"events", "identity"},
    ("northwind", "Computing"): set(), ("northwind", "JavaScript"): {"game"},
    ("tailspin", "Terraform"): {"events", "data"}, ("tailspin", "Kubernetes"): {"events", "data"},
    ("tailspin", "AWS"): set(),
    ("tailspin", "Azure Kubernetes"): {"events"},   # a true synonym nobody declared
}


STORED = []


def load(root=None):
    """The fixture - in a store, as jsk keeps a record - with its own vocabulary. `root`
    is a copy already seeded; by default one copy of the fixture, made once."""
    if root is None:
        if not STORED:
            from appkit import stored_copy
            STORED.append(stored_copy(FIXTURES))
        root = STORED[0]
    return record.load(root, vocabulary=Path(root) / "vocabulary.ttl")


def post(name):
    return O.K + "post_" + name


def short(iri):
    return iri.rsplit("/", 1)[-1].replace("prj_", "")


def by_label(matches):
    return {m.requirement.asked: m for m in matches.values()}


def carriers(m):
    return {short(p): (short(h), hops, imp) for p, (h, hops, imp) in m.carriers.items()}


class Scenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load()
        cls.m = {p: by_label(match.match(cls.s, post(p)))
                 for p in ("contoso", "fabrikam", "northwind", "tailspin")}

    def test_s0_the_fixture_validates(self):
        # One warning, and it is the point: "Go" is the language and the board game.
        self.assertEqual([f.text() for f in self.s.fails()], [])
        self.assertEqual([(f.rule, f.focus) for f in self.s.warns()],
                         [("label-clash", "c:golang")])

    def test_s1_labels_resolve_ambiguity_and_unknowns_are_named(self):
        c = self.m["contoso"]
        got = {t: (c[t].resolution.state, [short(x) for x in c[t].resolution.concepts])
               for t in ("K8s", ".NET", "Azure AD", "Go", "K3s")}
        self.assertEqual(got, {"K8s": ("resolved", ["kubernetes"]),
                               ".NET": ("resolved", ["dotnet"]),
                               "Azure AD": ("resolved", ["entra-id"]),       # a former label
                               "Go": ("ambiguous", ["go-game", "golang"]),
                               "K3s": ("candidate", [])})

    def test_s2_narrower_counts_as_broader_one_way_only(self):
        c = self.m["contoso"]
        self.assertEqual(carriers(c["K8s"])["events"], ("aks", 1, False))
        self.assertEqual((c["EKS"].state, {short(p): w for p, w in c["EKS"].near.items()}),
                         ("near", {"data": "holds broader c:kubernetes"}))

    def test_s3_the_hop_limit(self):
        # aks -> azure -> cloud-platform -> computing is three hops.
        n = self.m["northwind"]["Computing"]
        self.assertEqual((n.state, n.carriers), ("missing", {}))

    def test_two_hops_still_count(self):
        # Not one of the simulation's: every scenario there joins at 0 or 1 hop, or fails
        # at 3, so nothing pinned the second hop. aks -> azure -> cloud-platform is two.
        s = edited("# == Requirements\n",
                   '# == Requirements\n\nk:req_tailspin_cloud j:posting k:post_tailspin ;\n'
                   '    j:asked "Cloud platform" ; j:necessity j:preferred ;\n'
                   '    j:quote "AWS helps" .\n', "applications/tailspin/posting.ttl")
        cloud = by_label(match.match(s, post("tailspin")))["Cloud platform"]
        self.assertEqual(carriers(cloud), {"events": ("aks", 2, False),
                                           "identity": ("bicep", 2, False)})

    def test_s4_distinct_walls(self):
        f = self.m["fabrikam"]
        self.assertEqual((f[".NET Framework"].carriers, f["Angular"].carriers), ({}, {}))

    def test_s5_implies_never_carries_a_required_requirement(self):
        iac = self.m["contoso"]["Infrastructure as Code"]
        eda = self.m["northwind"]["Event-driven architecture"]
        self.assertEqual((iac.state, sorted(short(p) for p in iac.near)),
                         ("near", ["data", "events", "identity"]))
        self.assertEqual(sorted(carriers(eda)), ["events", "identity"])    # preferred: carries

    def test_s6_precision_and_recall_against_the_truth(self):
        pairs = {(p, t, short(proj)) for p, ms in self.m.items() for t, m in ms.items()
                 for proj in m.carriers}
        truth = {(p, t, proj) for (p, t), projs in TRUTH.items() for proj in projs}
        tp = len(pairs & truth)
        self.assertEqual((round(tp / len(pairs), 3), round(tp / len(truth), 3)), (1.0, 0.958))
        self.assertEqual(truth - pairs, {("tailspin", "Azure Kubernetes", "events")})

    def test_s7_cover_the_posting_not_just_the_top_scores(self):
        n = match.match(self.s, post("northwind"))
        top = [short(r.project) for r in match.rank(self.s, post("northwind"), n, TODAY)][:2]
        chosen, uncovered = cover.cover(n, 2)
        self.assertEqual(top, ["events", "identity"])        # these two leave Python uncovered
        self.assertEqual(([short(p) for p in chosen], uncovered), (["data", "events"], []))

    def test_s11_the_questions_a_tailoring_round_should_ask(self):
        qs = match.questions(self.s, match.match(self.s, post("contoso")))
        self.assertEqual([(q.requirement, q.kind, [short(d) for d in q.detail]) for q in qs], [
            (".NET", "tag-only", ["events", "identity"]),
            ("EKS", "broader-held", ["data"]),
            ("Go", "ambiguous", ["go-game", "golang"]),
            ("Infrastructure as Code", "implied", ["data", "events", "identity"]),
            ("K3s", "unknown-term", []),
        ])

    def test_an_unknown_term_is_offered_the_concepts_nearest_it(self):
        """An advert's phrase is rarely a label: "event streaming architecture" names no
        concept, but it shares two of its three words with one, the rare ones. The rare word
        leads - every -architecture concept shares "architecture", only one shares "event"."""
        near = match.nearest(self.s)
        self.assertEqual(near("event streaming architecture")[0],
                         O.C + "event-driven-architecture")
        self.assertEqual(near("K3s"), ())
        self.assertEqual(near("experience and skills"), ())         # filler names nothing
        self.assertEqual(near("AD"), (O.C + "entra-id",))           # a former label counts

    def test_one_shared_word_is_not_a_suggestion(self):
        # "documentation" is rare - one concept has it - but it is one word in three.
        s = edited("c:mentoring a j:Capability",
                   'c:clinical-documentation a j:Capability ; j:label "Clinical documentation" .\n'
                   "c:mentoring a j:Capability")
        near = match.nearest(s)
        self.assertEqual(near("clinical documentation"), (O.C + "clinical-documentation",))
        self.assertEqual(near("clear technical documentation"), ())

    def test_a_concept_whose_whole_name_the_phrase_holds_is_offered(self):
        # An advert wraps the term in its own words: "clear" weighs nothing, so the phrase
        # holding all of c:technical-documentation's id is the signal - its labels present,
        # which is what a name held only through its bag of every label's words would miss.
        s = edited("c:mentoring a j:Capability",
                   'c:clinical-documentation a j:Capability ; j:label "Clinical documentation" .\n'
                   'c:technical-documentation a j:Capability ; j:label "technical writing" .\n'
                   "c:mentoring a j:Capability")
        near = match.nearest(s)
        # Words no concept has outweigh the shared ones, so only the whole name finds it.
        wrapped = "clear, concise, well-organised technical documentation"
        self.assertEqual(near(wrapped), (O.C + "technical-documentation",))
        self.assertEqual(near("clear, concise, careful technical writing")[0],
                         O.C + "technical-documentation")
        self.assertNotIn(O.C + "golang", near("go-to-market planning"))     # "go" is too short

    def test_a_retired_concept_is_never_offered(self):
        # A merge retires the concept an older posting still names. It is that posting's
        # answer and the phrase holds its whole id, and neither makes it a suggestion.
        s = edited("c:mentoring a j:Capability",
                   'c:stream-plumbing a j:Capability ; j:retired "2026-09-26"^^xsd:date ;\n'
                   '    j:reason "Merged into c:kafka." .\n'
                   "c:mentoring a j:Capability",
                   also=[('j:asked "Computing" ; j:necessity j:preferred ;',
                          'j:asked "Stream plumbing" ; j:necessity j:preferred ; '
                          'j:concept c:stream-plumbing ;', "applications/northwind/posting.ttl")])
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertNotIn(O.C + "stream-plumbing", match.nearest(s, post=post("contoso"))("stream plumbing"))

    def test_another_postings_answer_is_offered_first(self):
        # northwind's analyst said "stream plumbing" meant Kafka; no concept's words say so.
        s = edited('j:asked "Computing" ; j:necessity j:preferred ;',
                   'j:asked "Stream plumbing" ; j:necessity j:preferred ; j:concept c:kafka ;',
                   "applications/northwind/posting.ttl")
        near = match.nearest(s, post=post("contoso"))
        self.assertEqual(near("stream plumbing"), (O.C + "kafka",))
        self.assertEqual(near("plumbing of event streams")[0], O.C + "kafka")     # 2 of 3 words
        self.assertEqual(near("event streaming architecture")[0],
                         O.C + "event-driven-architecture")                  # 1 of 3: no
        self.assertEqual(match.nearest(s, post=post("northwind"))("stream plumbing"), ())

    def test_the_questions_offer_an_answer_given_elsewhere(self):
        # contoso asks about K3s; had northwind's analyst named it, contoso is told.
        s = edited('j:asked "Computing" ; j:necessity j:preferred ;',
                   'j:asked "K3s" ; j:necessity j:preferred ; j:concept c:kubernetes ;',
                   "applications/northwind/posting.ttl")
        qs = {q.requirement: q for q in match.questions(s, match.match(s, post("contoso")))}
        self.assertEqual([short(d) for d in qs["K3s"].detail], ["kubernetes"])

    def test_the_match_prints_the_nearest_concepts_beside_an_unknown_term(self):
        from jsk.adapters.cli.compose import match as M
        from jsk.application.tailor import match_text
        r = M.result(self.s, post("contoso"), TODAY, 2)
        q = {"kind": "unknown-term", "requirement": "event streaming",
             "detail": ["c:event-driven-architecture"]}
        r["questions"] = [q]
        self.assertIn("- **unknown-term** event streaming: no concept has this label - nearest "
                      "c:event-driven-architecture; name the one meant with j:concept, or add it "
                      "to the vocabulary?", match_text.markdown(r))


class Ranking(unittest.TestCase):
    def test_scores_worked_by_hand(self):
        # northwind: events carries Kafka, Terraform (required, x3) and EDA (preferred, x1):
        # 6 + 1 + strength 5 x2 + recency 2026 (+1) = 18. identity: Kafka 3 + EDA 1 + 8 +
        # 2022, four years (+0.5) = 12.5. data: Python, Terraform 6 + 4 + 2020, six years
        # (+0.5) = 10.5. portal 6 + 0.5. game: JavaScript 1 + 4 + 2016, ten years (0) = 5.
        s = load()
        rows = match.rank(s, post("northwind"), match.match(s, post("northwind")), TODAY)
        self.assertEqual([(short(r.project), r.score) for r in rows],
                         [("events", 18), ("identity", 12.5), ("data", 10.5), ("portal", 6.5),
                          ("game", 5)])


def edited(old, new, file="career/kb.ttl", also=()):
    """The fixture with one edit - and `also`, more (old, new, file) edits - loaded."""
    tmp = tempfile.mkdtemp()
    shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
    for was, now, name in ((old, new, file), *also):
        path = Path(tmp) / name
        text = path.read_text(encoding="utf-8")
        assert was in text, was
        path.write_text(text.replace(was, now), encoding="utf-8", newline="\n")
    try:
        from appkit import seed
        seed(tmp)
        return load(tmp)
    finally:
        shutil.rmtree(tmp)


class Resolution(unittest.TestCase):
    def test_the_analysts_concept_settles_an_ambiguity(self):
        s = edited('j:asked "Go" ; j:necessity j:preferred ;',
                   'j:asked "Go" ; j:necessity j:preferred ; j:concept c:golang ;',
                   "applications/contoso/posting.ttl")
        go = by_label(match.match(s, post("contoso")))["Go"]
        self.assertEqual((go.resolution.via, go.state), ("concept", "missing"))

    def test_an_advert_listing_alternatives_is_met_by_any_one(self):
        # "EKS or AKS": events holds only AKS, data only the broader Kubernetes. Alone, EKS
        # is near; with AKS named as an alternative, events carries it and its confirmed
        # bullet showing AKS is the evidence - read through the concept it holds.
        s = edited('j:asked "EKS" ; j:necessity j:preferred ;',
                   'j:asked "EKS" ; j:necessity j:preferred ; j:concept c:eks, c:aks ;',
                   "applications/contoso/posting.ttl")
        eks = by_label(match.match(s, post("contoso")))["EKS"]
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual((eks.state, [short(c) for c in eks.concepts], carriers(eks)),
                         ("matched", ["aks", "eks"], {"events": ("aks", 0, False)}))
        self.assertEqual(match.evidence(s, O.K + "prj_events", eks.concepts), "confirmed")
        self.assertEqual({short(p): w for p, w in eks.near.items()},
                         {"data": "holds broader c:kubernetes"})

    def test_an_id_beats_a_label_clash(self):
        # "Go-game" normalises to the id c:go-game, which "Go" never would.
        s = edited('j:asked "Go" ;', 'j:asked "Go-game" ;', "applications/contoso/posting.ttl")
        go = by_label(match.match(s, post("contoso")))["Go-game"]
        self.assertEqual((go.resolution.via, [short(c) for c in go.resolution.concepts]),
                         ("id", ["go-game"]))


    def test_a_label_as_messily_written_still_resolves(self):
        s = edited('j:asked "K8s" ;', 'j:asked "  k8S  " ;', "applications/contoso/posting.ttl")
        k8s = by_label(match.match(s, post("contoso")))["  k8S  "]
        self.assertEqual((k8s.state, [short(c) for c in k8s.resolution.concepts]),
                         ("matched", ["kubernetes"]))

    def test_a_persons_label_that_collides_is_asked_not_crashed(self):
        # "Apache Kafka" is a shipped label, not an id; "Kafka" would stay resolved, since
        # it is the id c:kafka and an id beats any clash.
        s = edited('c:team-leadership a j:Capability ; j:label "Team leadership" .',
                   'c:team-leadership a j:Capability ; j:label "Apache Kafka", "Team leadership" .')
        req = model.Requirement(O.K + "req_x", "Apache Kafka", "Apache Kafka", "required")
        got = resolve.resolve(req, match.labels(s), match.concepts(s))
        self.assertEqual((got.state, [short(c) for c in got.concepts]),
                         ("ambiguous", ["kafka", "team-leadership"]))
        self.assertEqual([f.text() for f in s.fails()], [])

    def test_a_posting_with_nothing_required_has_an_empty_cover(self):
        self.assertEqual(cover.cover({}, 3), ([], []))

    def test_an_id_that_is_also_anothers_label_is_asked_not_assumed(self):
        # A person's own slug meets free advert text: were the board game c:go, "Go" would
        # silently mean it. An id wins only when no other concept goes by that label.
        s = edited("c:go-game", "c:go")
        go = by_label(match.match(s, post("contoso")))["Go"]
        self.assertEqual((go.state, [short(c) for c in go.resolution.concepts]),
                         ("ambiguous", ["go", "golang"]))


class Cover(unittest.TestCase):
    def test_among_equally_small_covers_the_stronger_one(self):
        # tailspin's required Terraform and Kubernetes are each carried by events and by
        # data. Either alone covers them; events scores 17 with confirmed evidence, data
        # 10.5 with a tag. The cover goes on the resume, so it is events.
        s = load()
        m = match.match(s, post("tailspin"))
        chosen, _ = cover.cover(m, 3, match.rank(s, post("tailspin"), m, TODAY))
        self.assertEqual([short(p) for p in chosen], ["events"])

    def test_an_unresolved_requirement_is_not_reported_as_uncarried(self):
        # Required and ambiguous: it may well be carried, once someone says what it means.
        s = edited('j:asked "Go" ; j:necessity j:preferred ;', 'j:asked "Go" ; j:necessity j:required ;',
                   "applications/contoso/posting.ttl")
        _, uncovered = cover.cover(match.match(s, post("contoso")), 3)
        self.assertNotIn("Go", uncovered)
        self.assertIn("Infrastructure as Code", uncovered)


class Retired(unittest.TestCase):
    def test_a_retired_project_carries_nothing(self):
        s = edited('k:prj_data j:name "Data" ;',
                   'k:prj_data j:name "Data" ; j:retired "2026-01-01"^^xsd:date ; '
                   'j:reason "Folded into events." ;')
        k8s = by_label(match.match(s, post("contoso")))["K8s"]
        self.assertEqual(sorted(carriers(k8s)), ["events"])

    def test_a_disputed_bullet_is_not_evidence(self):
        s = edited('j:text "Wrote the platform\'s Terraform." ;\n    j:shows c:terraform ;\n'
                   '    j:provenance j:confirmed .',
                   'j:text "Wrote the platform\'s Terraform." ;\n    j:shows c:terraform ;\n'
                   '    j:provenance j:disputed .')
        self.assertEqual(match.evidence(s, O.K + "prj_events", O.C + "terraform"), "tag")

    def test_a_retired_bullet_is_not_evidence(self):
        s = edited('j:shows c:terraform ;',
                   'j:shows c:terraform ; j:retired "2026-01-01"^^xsd:date ; '
                   'j:reason "Superseded." ;')
        self.assertEqual(match.evidence(s, O.K + "prj_events", O.C + "terraform"), "tag")


class RecordFaults(unittest.TestCase):
    """A number in a selected bullet that no metric backs is a round-1 question, asked of
    the person - on the ElevenLabs run it surfaced only at export, and the author reworded
    300-400 to 300-800 to fit an unrelated metric."""

    TERRAFORM = "Wrote the platform's Terraform."

    def faults(self, s, name="contoso"):
        from jsk.adapters.cli.compose import match as M
        from jsk.application.tailor import match_text as M_match_text
        r = M.result(s, post(name), TODAY, 3)
        return [q for q in r["questions"] if q["kind"] == "missing-metric"], M_match_text.markdown(r)

    def test_a_selected_bullets_uncited_numbers_are_one_question(self):
        s = edited(self.TERRAFORM, "Wrote the platform's Terraform across a 300-400 module estate.")
        qs, md = self.faults(s)
        mine = [q for q in qs if q["bullet"] == "k:ach_events_terraform"]
        self.assertEqual([(q["numbers"], q["cites"]) for q in mine], [(["300", "400"], [])])
        self.assertIn("- **missing-metric** k:ach_events_terraform: '300' and '400' in "
                      "k:ach_events_terraform are in no metric (it cites none) - what are the "
                      "figures, and where do they come from (dashboards, retros, release "
                      "notes)? Or should the words change?", md)
        # Asked after the requirements' own questions.
        kinds = [line.split("**")[1] for line in md.split("## Questions")[1].splitlines()
                 if line.startswith("- **")]
        self.assertEqual(kinds[-len(qs):], ["missing-metric"] * len(qs))
        self.assertNotIn("missing-metric", kinds[:-len(qs)])

    def test_a_number_its_metric_holds_asks_nothing(self):
        qs, _ = self.faults(load())
        self.assertNotIn("k:ach_events_team", [q["bullet"] for q in qs])   # "6", met_team 6
        self.assertNotIn("k:ach_identity_sso", [q["bullet"] for q in qs])  # "40", met_apps 40

    def test_a_bullet_no_draft_selects_asks_nothing(self):
        # prj_portal carries nothing Contoso asks for, so no draft for it selects the bullet;
        # `jsk kb check` asks about it across the career.
        s = edited("Built the AngularJS front end.", "Built the AngularJS front end for 12 teams.")
        from jsk.gates import numbers
        whole = numbers.untraced(s, [O.K + "ach_portal_frontend"], TODAY)
        self.assertTrue(whole)                                             # it is a fault
        qs, _ = self.faults(s)
        self.assertNotIn("k:ach_portal_frontend", [q["bullet"] for q in qs])

    def test_a_top_ranked_bullet_is_asked_when_the_selection_picks_nothing(self):
        """On the ElevenLabs career before the run the selection picked nothing - nine
        requirements unresolved, the rest tag-only - so this asked nothing while `jsk kb
        check` named six faults the author then met mid-export."""
        import types
        from unittest import mock
        s = edited(self.TERRAFORM, "Wrote the platform's Terraform across a 300-400 module estate.")
        empty = types.SimpleNamespace(projects=[], bullets={}, skills=[], gaps=[])
        with mock.patch("jsk.adapters.cli.compose.match.select", return_value=empty):
            qs, _ = self.faults(s)
        self.assertIn("k:ach_events_terraform", [q["bullet"] for q in qs])

    def test_a_workspace_without_a_career_still_matches(self):
        from jsk.adapters.cli.compose import match as M
        s = load()
        del s.parsed["kb"]
        self.assertEqual(M.record_faults(s, post("contoso"), TODAY, 3), [])


class Narrowing(unittest.TestCase):
    def test_unlabel_takes_a_shipped_label_away(self):
        s = edited("c:go-game a j:Domain ;", 'c:golang j:unlabel "Go" .\n\nc:go-game a j:Domain ;')
        go = by_label(match.match(s, post("contoso")))["Go"]
        self.assertEqual([short(c) for c in go.resolution.concepts], ["go-game"])
        self.assertEqual([f.text() for f in s.findings], [])     # and the clash is gone

    def test_unlink_takes_a_shipped_edge_away(self):
        s = edited("c:go-game a j:Domain ;", "c:aks j:unlink c:kubernetes .\n\nc:go-game a j:Domain ;")
        k8s = by_label(match.match(s, post("contoso")))["K8s"]
        self.assertEqual(sorted(carriers(k8s)), ["data"])       # events held only AKS

    def test_the_file_is_not_touched(self):
        before = (FIXTURES / "vocabulary.ttl").read_bytes()
        edited("c:go-game a j:Domain ;", 'c:golang j:unlabel "Go" .\n\nc:go-game a j:Domain ;')
        self.assertEqual((FIXTURES / "vocabulary.ttl").read_bytes(), before)


class Verdicts(unittest.TestCase):
    """The Verdict the match derives: the most the record supports, which gaps.txt may lower
    and never raise."""

    @classmethod
    def setUpClass(cls):
        from jsk.adapters.cli.compose import match as M
        s = load()
        cls.r = {p: M.result(s, post(p), TODAY, 3) for p in ("contoso", "northwind", "fabrikam")}
        cls.v = {(p, q["asked"]): q["verdict"] for p, r in cls.r.items()
                 for q in r["requirements"]}

    def test_each_bucket_and_evidence_level(self):
        self.assertEqual({k: self.v[k] for k in [
            ("contoso", "Azure AD"),              # matched, confirmed
            ("contoso", ".NET"),                  # matched, tags only
            ("northwind", "Python"),              # matched, an unconfirmed bullet
            ("contoso", "EKS"),                   # near
            ("fabrikam", "Angular"),              # missing
            ("contoso", "Go"),                    # ambiguous
            ("contoso", "K3s"),                   # candidate
            ("contoso", "Mentoring")]},           # implicit: not assessed
            {("contoso", "Azure AD"): "satisfied", ("contoso", ".NET"): "unevidenced",
             ("northwind", "Python"): "unevidenced", ("contoso", "EKS"): "partial",
             ("fabrikam", "Angular"): "unsatisfied", ("contoso", "Go"): "indeterminate",
             ("contoso", "K3s"): "indeterminate", ("contoso", "Mentoring"): None})

    def test_one_confirmed_carrier_among_tags_satisfies(self):
        self.assertEqual(self.v[("contoso", "K8s")], "satisfied")

    def test_the_table_prints_it(self):
        from jsk.application.tailor import match_text as M
        out = M.markdown(self.r["contoso"])
        self.assertIn("| Requirement | Need | State | Verdict | Carried by | Evidence |", out)
        self.assertIn("| Mentoring | implicit | implicit | - |", out)
        self.assertIn("| EKS | preferred | near | partial |", out)


class GapsFlags(unittest.TestCase):
    """`jsk match APP --gaps` / `--draft-gaps`: gaps.txt checked, the assessment and gaps.md
    written. The rules themselves are tests/test_gaps_build.py's."""

    GAPS = "applications/contoso/gaps"

    def setUp(self):
        from appkit import seed

        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        shutil.copytree(FIXTURES, self.tmp, dirs_exist_ok=True)
        seed(self.tmp)
        self.app = Path(self.tmp) / "applications" / "contoso"
        self.txt = self.app / "gaps.txt"

    def main(self, *argv, app=None):
        import contextlib
        import io

        from jsk.adapters.cli import match as M
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = M.main([str(app or self.app), "--today", "2026-09-24", *map(str, argv)])
        return code, out.getvalue()

    def assessed(self):
        import appkit
        return appkit.has(self.tmp, self.GAPS)

    def test_the_application_is_matched(self):
        code, out = self.main()
        self.assertEqual(code, 0, out)
        self.assertIn("# Match - ", out)
        self.assertFalse(self.assessed())                  # a plain match writes nothing

    def test_a_posting_ttl_path_is_refused_with_the_application_form(self):
        code, out = self.main(app=self.app / "posting.ttl")
        self.assertEqual(code, 2, out)
        self.assertIn("jsk tailor match takes the application now, not its posting.ttl", out)
        self.assertIn(f"fix:  jsk tailor match {self.app}", out)

    def test_a_folder_that_is_not_an_application_is_refused(self):
        code, out = self.main(app=Path(self.tmp) / "career")
        self.assertEqual(code, 2, out)
        self.assertIn("not an application", out)

    def test_draft_writes_the_derived_assessment_then_gaps_txt(self):
        code, out = self.main("--draft-gaps", self.txt)
        self.assertEqual(code, 0, out)
        self.assertIn(f"0 FAIL, 0 WARN - wrote {self.GAPS} and gaps.md", out)
        self.assertIn(f"wrote {self.txt}: 10 requirements, 4 slots to fill", out)
        self.assertTrue(self.assessed())
        self.assertFalse((self.app / "gaps.ttl").exists())
        # The draft's slots are a FAIL, and a FAIL writes nothing.
        before = (self.app / "gaps.md").read_bytes()
        code, out = self.main("--gaps", self.txt)
        self.assertEqual(code, 1)
        self.assertIn("4 FAIL, 0 WARN - nothing written", out)
        self.assertEqual((self.app / "gaps.md").read_bytes(), before)

    def test_a_filled_gaps_txt_writes_both(self):
        self.txt.write_text("fit: partial\neligibility: meets it\n"
                            "k8s | partial | one AKS cluster\n", encoding="utf-8")
        code, out = self.main("--gaps", self.txt)
        self.assertEqual((code, out.splitlines()[-1]),
                         (0, f"{self.txt}: 0 FAIL, 0 WARN - wrote {self.GAPS} and gaps.md"))
        self.assertIn("partial (match: satisfied)",
                      (self.app / "gaps.md").read_text(encoding="utf-8"))

    def test_a_raised_verdict_fails_and_writes_nothing(self):
        """.NET is carried only by tags: `satisfied` is a claim the record does not make."""
        self.txt.write_text("dotnet | satisfied | it is on the projects\n", encoding="utf-8")
        code, out = self.main("--gaps", self.txt)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  gaps.txt line 1: dotnet: satisfied, above the match's unevidenced",
                      out)
        self.assertIn("the career needs the tag or the confirmation", out)
        self.assertFalse(self.assessed())

    def test_draft_refuses_a_gaps_txt_that_exists(self):
        self.txt.write_text("the analyst's work\n", encoding="utf-8")
        code, out = self.main("--draft-gaps", self.txt)
        self.assertEqual(code, 1)
        self.assertIn("exists", out)
        self.assertIn("fix:", out)
        self.assertEqual(self.txt.read_text(encoding="utf-8"), "the analyst's work\n")

    def test_a_gaps_md_is_refused(self):
        code, out = self.main("--gaps", self.app / "gaps.md")
        self.assertEqual(code, 1)
        self.assertIn("gaps.md is written by jsk now", out)

    def test_another_directory_or_no_file_is_refused(self):
        code, out = self.main("--gaps", Path(self.tmp) / "gaps.txt")
        self.assertEqual(code, 1)
        self.assertIn("not this application's gaps.txt", out)
        code, out = self.main("--gaps", self.txt)
        self.assertEqual(code, 1)
        self.assertIn("no such file", out)

    def test_gaps_and_draft_gaps_together_is_a_usage_error(self):
        code, out = self.main("--gaps", self.txt, "--draft-gaps", self.txt)
        self.assertEqual(code, 2)
        self.assertIn("usage:", out)


if __name__ == "__main__":
    unittest.main()
