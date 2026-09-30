"""The feature reads over a loaded record, as SPARQL: ports.queries.RecordQueries.

A feature's projection is storage knowledge - that the counts-as paths sit in GRAPH
j:derived, that a retired entry carries j:retired - so the text is here, beside the engine,
and the domain asks for what it needs by method. Each method runs over the Store it was
made with, through Store.select.
"""
from ...domain import ontology as O

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
