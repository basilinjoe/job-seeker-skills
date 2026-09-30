"""The concepts a phrase may mean: the nearest to an unresolved label, and those an advert
line names by a whole label."""
from .. import ontology as O

FILLER = {"a", "an", "and", "or", "the", "of", "in", "on", "with", "for", "to", "at", "as",
          "by", "experience", "skills", "strong", "knowledge", "years", "understanding"}


def words(text):
    """A phrase's content words, lowercased, a plural `s` dropped: "integration patterns"
    and c:integration-pattern share both."""
    import re
    out = set()
    for w in re.split(r"[^a-z0-9+#]+", text.lower()):
        if w and w not in FILLER:
            out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


COVER = 0.5   # the share of a label's weight a concept's words must carry to be offered


def nearest(queries, limit=3, post=None):
    """A function from an unresolved label to the concepts closest to it. First what other
    postings' analysts named for the same label, or for one sharing most of its words;
    then the concepts whose whole id or label the phrase contains; then the concepts whose
    id and labels share its words, a rare word counting for more:
    "architecture" names forty concepts and says little, "integration" names five. A
    concept is offered only if the words it shares carry half the label's weight, so one
    shared word in three is not a suggestion: "clear technical documentation" is not
    c:clinical-documentation. `post` is the posting asking, whose own answers are not
    offered back to it. Only a suggestion - the analyst names the one meant with
    `j:concept`, or none.

    Args:
        queries: a RecordQueries over a loaded workspace.
        limit: how many concepts a label is offered at most.
        post: the posting asking, or None.

    Returns:
        near(label) -> a tuple of at most `limit` concept iris, nearest first.
    """
    past = queries.answered(post)
    bags, names = {}, {}
    for c in queries.concepts():
        bags[c] = words(c[len(O.C):].replace("-", " "))
        names[c] = [set(bags[c])]        # a copy: the bag grows by the labels below
    for c, label in queries.label_pairs():
        bags.setdefault(c, set()).update(words(label))
        names.setdefault(c, []).append(words(label))
    for c in queries.retired_concepts():
        bags.pop(c, None)         # no longer meant: never a suggestion
        names.pop(c, None)
    df = {}
    for bag in bags.values():
        for w in bag:
            df[w] = df.get(w, 0) + 1
    unseen = max((1 / n for n in df.values()), default=1)   # a word no concept has: the rarest

    def near(label):
        mine = words(label)
        ranked = []
        for (asked, c), posts in past.items():
            if O.norm(asked) == O.norm(label):
                ranked.append((0, 0, -len(posts), c))
            elif mine and len(mine & words(asked)) * 2 > len(mine):
                ranked.append((1, -len(mine & words(asked)), -len(posts), c))
        # A concept whose whole name the phrase contains: "clear technical documentation"
        # holds c:technical-documentation, whatever "clear" weighs. The longest name first;
        # a one-word name of two letters ("go" in "go-to-market") is too short to count.
        for c, ns in names.items():
            held = [n for n in ns if n and n <= mine and (len(n) > 1 or len(next(iter(n))) > 2)]
            if held:
                n = max(held, key=len)
                ranked.append((2, -len(n), -sum(1 / df[w] for w in n), c))
        out = []
        for *_, c in sorted(ranked):
            if c not in out:
                out.append(c)
        weight = {w: 1 / df[w] if w in df else unseen for w in mine}
        total = sum(weight.values())
        scored = [(sum(weight[w] for w in mine & bag), c) for c, bag in bags.items()
                  if mine & bag]
        scored = [(s, c) for s, c in scored if s >= COVER * total]
        scored.sort(key=lambda s: (-s[0], len(s[1]), s[1]))
        for _, c in scored:
            if c not in out:
                out.append(c)
        return tuple(out[:limit])
    return near


def labels_in(queries):
    """A function from an advert line to the concepts whose whole label it holds, in the
    order the line names them - what `jsk posting extract` proposes beside each line, so
    the analyst accepts or strikes instead of reading the whole vocabulary.

    A label matches as contiguous words, a space or a hyphen between them either way. The
    longest label at a place wins, so "Azure AI Foundry" is not also c:azure. A label of two
    characters or fewer matches only as written: "Go" is the language, "go" in "go live"
    is not. A retired concept is never proposed.

    Args:
        queries: a RecordQueries over a loaded workspace.

    Returns:
        named(line) -> a tuple of concept iris, in the order the line names them.
    """
    import re

    def key(text):
        return re.sub(r"[\s-]+", "-", text.strip().lower())

    retired = queries.retired_concepts()
    meant = {}
    for c, label in queries.label_pairs():
        label = label.strip()
        if label and c not in retired:
            meant.setdefault((label if len(label) <= 2 else key(label)), set()).add(c)
    if not meant:
        return lambda line: ()

    def alternative(label):
        body = r"[\s-]+".join(re.escape(w) for w in re.split(r"[\s-]+", label))
        return body if len(label) <= 2 else f"(?i:{body})"

    found = re.compile(r"(?<![A-Za-z0-9+#])(?:"
                       + "|".join(alternative(k) for k in sorted(meant, key=lambda k: (-len(k), k)))
                       + r")(?![A-Za-z0-9+#])")

    def named(line):
        out = []
        for m in found.finditer(line):
            said = m.group(0)
            for c in sorted(meant.get(said if len(said) <= 2 else key(said), ())):
                if c not in out:
                    out.append(c)
        return tuple(out)
    return named
