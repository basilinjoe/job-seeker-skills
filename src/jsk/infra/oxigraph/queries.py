"""The feature reads over a loaded record, as SPARQL: ports.queries.RecordQueries.

A feature's projection is storage knowledge - that the counts-as paths sit in GRAPH
j:derived, that a retired entry carries j:retired - so the text is here, beside the engine,
and the domain asks for what it needs by method. Each method runs over the Store it was
made with, through Store.select.
"""
from ...domain import ontology as O
from ...domain.matching.model import Requirement, local

PRE = (f"PREFIX j: <{O.J}>\nPREFIX k: <{O.K}>\nPREFIX c: <{O.C}>\n"
       f"PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")


class OxigraphQueries:
    """RecordQueries over one loaded workspace."""

    def __init__(self, store):
        """Ask `store` (a loaded domain.record.store.Store); nothing is read until a method runs."""
        self.store = store

    def metric_facts(self):
        """What the untraced-number check compares.

        Returns:
            (text, cites, versions): each bullet's words, the metrics each cites, and each
            metric's versions as (version, {numbers}, closed day or None). Runs two SELECTs.
        """
        text, cites = {}, {}
        for r in self.store.select(PRE + """SELECT ?a ?t ?m WHERE { ?a a j:Achievement ; j:text ?t
                                        OPTIONAL { ?a j:cites ?m } }"""):
            text[r["a"].value] = r["t"].value
            if "m" in r:
                cites.setdefault(r["a"].value, set()).add(r["m"].value)
        versions = {}
        for r in self.store.select(PRE + """SELECT ?m ?v ?val ?base ?upper ?until WHERE {
                ?v j:of ?m ; j:value ?val OPTIONAL { ?v j:baseline ?base }
                OPTIONAL { ?v j:upper ?upper } OPTIONAL { ?v j:validUntil ?until } }"""):
            # Either end of a range is the career's number: "15-20" states both.
            nums = {float(r[k].value) for k in ("val", "base", "upper") if k in r}
            versions.setdefault(r["m"].value, []).append(
                (r["v"].value, nums, r["until"].value if "until" in r else None))
        return text, cites, versions

    def requirements(self, post):
        """A posting's requirements.

        Args:
            post: the posting's iri.

        Returns:
            [Requirement] in iri order, each with the concepts the analyst named (any one
            satisfies), sorted.
        """
        rows = self.store.select(PRE + f"""
            SELECT ?r ?asked ?quote ?need ?concept WHERE {{
              ?r j:posting <{post}> ; j:asked ?asked ; j:quote ?quote ; j:necessity ?need .
              OPTIONAL {{ ?r j:concept ?concept }} }} ORDER BY ?r""")
        # One row per j:concept: an advert listing alternatives names several.
        found = {}
        for r in rows:
            key = r["r"].value
            if key not in found:
                found[key] = (r["asked"].value, r["quote"].value, local(r["need"].value), set())
            if "concept" in r:
                found[key][3].add(r["concept"].value)
        return [Requirement(iri, asked, quote, need, tuple(sorted(cs)))
                for iri, (asked, quote, need, cs) in found.items()]

    def label_pairs(self):
        """(concept, label) for every label and former label, shipped and the person's own.

        Returns:
            The pairs in the engine's order, labels as written.
        """
        return [(r["c"].value, r["l"].value)
                for r in self.store.select(PRE + """SELECT ?c ?l WHERE { ?c j:label|j:former ?l }""")]

    def concepts(self):
        """Every concept iri any graph states something about.

        Returns:
            A set of iris in the c: namespace.
        """
        return {r["c"].value for r in self.store.select(PRE + """
            SELECT DISTINCT ?c WHERE { GRAPH ?g { ?c ?p ?o }
                                       FILTER(STRSTARTS(STR(?c), STR(c:))) }""")}

    def retired_concepts(self):
        """The concepts a merge or the person retired.

        Returns:
            A set of iris in the c: namespace.
        """
        return {r["c"].value for r in self.store.select(PRE + """SELECT ?c WHERE { ?c j:retired ?x
                                                 FILTER(STRSTARTS(STR(?c), STR(c:))) }""")}

    def paths_to(self, concept):
        """(project, held, hops, implied) for every live project holding something that counts
        as `concept` - the closure's paths run from the held concept up to the asked one.

        Args:
            concept: the asked concept's iri.

        Returns:
            One tuple per path, hops an int and implied a bool.
        """
        rows = self.store.select(PRE + f"""
            SELECT ?proj ?held ?hops ?implied WHERE {{
              ?proj j:uses ?held .
              GRAPH j:derived {{ ?p j:from ?held ; j:to <{concept}> ; j:hops ?hops ;
                                    j:implied ?implied }}
              FILTER NOT EXISTS {{ ?proj j:retired ?x }} }}""")
        return [(r["proj"].value, r["held"].value, int(r["hops"].value),
                 r["implied"].value == "true") for r in rows]

    def broader_held(self, concept):
        """(project, held) where the project holds only something `concept` counts as - the
        reverse direction, which never matches: Kubernetes work is not EKS work.

        Args:
            concept: the asked concept's iri.

        Returns:
            One (project, held) per path of one hop or more, never through an implies edge.
        """
        rows = self.store.select(PRE + f"""
            SELECT ?proj ?held WHERE {{
              ?proj j:uses ?held .
              GRAPH j:derived {{ ?p j:from <{concept}> ; j:to ?held ; j:hops ?h ; j:implied false }}
              FILTER(?h > 0) FILTER NOT EXISTS {{ ?proj j:retired ?x }} }}""")
        return [(r["proj"].value, r["held"].value) for r in rows]

    def evidence_levels(self, project, concepts):
        """The provenances of the project's live bullets that show one of the concepts, or
        something that counts as one without an implies edge. A disputed bullet is left out.

        Args:
            project: the project's iri.
            concepts: one concept iri or several.

        Returns:
            A set of provenance names: confirmed, inferred, unverified.
        """
        wanted = " ".join(f"<{c}>" for c in ((concepts,) if isinstance(concepts, str) else concepts))
        rows = self.store.select(PRE + f"""
            SELECT DISTINCT ?pv WHERE {{
              VALUES ?want {{ {wanted} }}
              ?b j:project <{project}> ; j:shows ?m ; j:provenance ?pv .
              GRAPH j:derived {{ ?p j:from ?m ; j:to ?want ; j:implied false }}
              FILTER(?pv != j:disputed)
              FILTER NOT EXISTS {{ ?b j:retired ?x }} }}""")
        return {local(r["pv"].value) for r in rows}

    def confirmed_texts(self, project, concepts):
        """The words of the bullets that make the evidence confirmed: live, confirmed, and
        showing one of the concepts without an implies edge.

        Args:
            project: the project's iri.
            concepts: one concept iri or several.

        Returns:
            The bullets' words, sorted, so a caller is stable.
        """
        wanted = " ".join(f"<{c}>" for c in ((concepts,) if isinstance(concepts, str) else concepts))
        rows = self.store.select(PRE + f"""
            SELECT DISTINCT ?t WHERE {{
              VALUES ?want {{ {wanted} }}
              ?b j:project <{project}> ; j:shows ?m ; j:provenance j:confirmed ; j:text ?t .
              GRAPH j:derived {{ ?p j:from ?m ; j:to ?want ; j:implied false }}
              FILTER NOT EXISTS {{ ?b j:retired ?x }} }}""")
        return sorted(r["t"].value for r in rows)

    def projects(self):
        """{project: (strength, recency, seniority)} for every live project.

        Returns:
            strength and recency as ints; seniority a level name, or None.
        """
        rows = self.store.select(PRE + """
            SELECT ?p ?s ?r ?sen WHERE { ?p a j:Project ; j:strength ?s ; j:recency ?r .
                                         OPTIONAL { ?p j:seniority ?sen }
                                         FILTER NOT EXISTS { ?p j:retired ?x } }""")
        return {r["p"].value: (int(r["s"].value), int(r["r"].value),
                               local(r["sen"].value) if "sen" in r else None) for r in rows}

    def posting_seniority(self, post):
        """The seniority a posting asks for.

        Args:
            post: the posting's iri.

        Returns:
            A level name, or None when the posting states none.
        """
        rows = self.store.select(PRE + f"SELECT ?s WHERE {{ <{post}> j:seniority ?s }}")
        return local(rows[0]["s"].value) if rows else None

    def posting_of(self, req):
        """The posting a requirement belongs to.

        Args:
            req: the requirement's iri.

        Returns:
            The posting's iri, or None.
        """
        rows = self.store.select(PRE + f"SELECT ?p WHERE {{ <{req}> j:posting ?p }}")
        return rows[0]["p"].value if rows else None

    def answered(self, post=None):
        """{(asked, concept): postings}: what the analyst named for each label on the other
        postings. A retired concept is left out: a merge retires one an older posting still
        names.

        Args:
            post: the posting asking, whose own answers are left out; None leaves none out.

        Returns:
            Each (label as asked, concept named) mapped to the postings that named it.
        """
        out = {}
        for r in self.store.select(PRE + """SELECT DISTINCT ?p ?a ?c WHERE {
                ?r j:posting ?p ; j:asked ?a ; j:concept ?c
                FILTER NOT EXISTS { ?c j:retired ?x } }"""):
            if r["p"].value != post:
                out.setdefault((r["a"].value, r["c"].value), set()).add(r["p"].value)
        return out

    def live_bullets(self):
        """{bullet: (project, rank, provenance)} for every live bullet.

        Returns:
            rank an int, provenance a name (confirmed, inferred, ...).
        """
        rows = self.store.select(PRE + """
            SELECT ?b ?p ?rank ?pv WHERE { ?b j:project ?p ; j:rank ?rank ; j:provenance ?pv .
                                           FILTER NOT EXISTS { ?b j:retired ?x } }""")
        return {r["b"].value: (r["p"].value, int(r["rank"].value), local(r["pv"].value))
                for r in rows}

    def bullet_shows(self):
        """{bullet: the concepts it shows or counts as, without an implies edge}.

        Returns:
            A set of concept iris per bullet that shows one.
        """
        rows = self.store.select(PRE + """
            SELECT ?b ?to WHERE { ?b j:project ?p ; j:shows ?m .
              GRAPH j:derived { ?x j:from ?m ; j:to ?to ; j:implied false } }""")
        out = {}
        for r in rows:
            out.setdefault(r["b"].value, set()).add(r["to"].value)
        return out

    def citing_current(self):
        """Bullets citing a metric that has a current version - the ones export keeps a
        number for.

        Returns:
            A set of bullet iris.
        """
        rows = self.store.select(PRE + """
            SELECT DISTINCT ?b WHERE { ?b j:project ?p ; j:cites ?m . ?v j:of ?m .
                                       FILTER NOT EXISTS { ?v j:validUntil ?u } }""")
        return {r["b"].value for r in rows}
