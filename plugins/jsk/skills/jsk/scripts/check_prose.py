#!/usr/bin/env python3
"""Check a generated resume against the rules in references/writing-rules.md

Usage: python3 check_prose.py resume.tex
       python3 check_prose.py resume.txt

On Windows use `python` or `py -3` in place of `python3`.

The sibling gate to check_ats.py. That one verifies a document *parses*; this one
verifies it *reads* - and reports how much of it is quantified, which nothing
else measures: validate_urs.py checks that a number in prose traces to a metric,
never that any number is there at all. A bullet in the third person - "the platform followed him
through his promotion" - is not a parsing defect, so check_ats.py passes it with
0 failures and is right to. Nothing else was checking.

Exit 0 = pass. Exit 1 = do not send this file. Exit 2 = usage error.
No third-party dependencies.
"""
import sys, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    # Reused rather than reimplemented. validate_urs.numerals() already knows
    # that a year, a glued designator (p95, S3, H100) and a standard's number
    # (ISO 27001) are not claims, and a second detector without those
    # exclusions would report a resume as unquantified because it mentions
    # 2019. This gate stays runnable where that file is absent - SKILL.md's
    # "installed as SKILL.md alone" case - by dropping the coverage line
    # rather than failing.
    from validate_urs import numerals
except ImportError:                                          # pragma: no cover
    numerals = None

# --- fail: a resume is implied first person, and these are never the subject ---
# `they/them/their` are excluded deliberately. "Migrated their estate to Azure"
# is ordinary and correct - the ambiguity is real, so those only warn.
THIRD_PERSON = r"\b(he|him|his|she|her|hers|himself|herself)\b"
AMBIGUOUS_PERSON = r"\b(they|them|their|theirs|themselves)\b"

# --- a sentence that stops before its object ---
# The repo's own history carries "improved overall productivity of the organisation
# by" with no number. Curated rather than a general part-of-speech rule, and split
# in two because English lets a sentence end on a particle: "the platforms other
# teams build on" is finished, "increased productivity by" is not.
DANGLING_HARD = ("a", "an", "the", "and", "or", "but", "by", "of", "from", "into",
                 "onto", "than", "per", "using", "including", "such", "that",
                 "which", "between", "while", "when", "where")
DANGLING_SOFT = ("to", "with", "for", "through", "across", "via", "as")

# --- warn: activity dressed as achievement, per writing-rules.md "Cut on sight" ---
BANNED = ("responsible for", "worked on", "involved in", "gained experience in",
          "acquired knowledge of", "assisted with", "helped with", "participated in",
          "duties included", "tasked with", "exposure to", "familiar with")

# --- warn: the no-throat-clearing rule. A bullet opens on what they did. ---
# Suffix rules catch most of it ("Architected", "Owned"); the list carries the
# irregulars and the few present-tense forms that are legitimate on a resume.
VERBS = {
    "built", "led", "ran", "grew", "cut", "drove", "won", "sold", "spoke", "wrote",
    "rebuilt", "rewrote", "broke", "chose", "set", "kept", "held", "brought",
    "began", "left", "met", "took", "made", "gave", "found", "sent", "spent",
    "taught", "put", "shrank", "sped", "beat", "oversaw", "undertook", "rose",
    "own", "build", "lead", "run", "design", "architect", "deliver", "ship",
}
VERB_SUFFIXES = ("ed", "ised", "ized", "ated", "ected", "ored", "ered")

NEAR_DUPLICATE = 0.75          # Jaccard over word sets; 1.0 is an exact repeat
WORD = re.compile(r"[a-z0-9']+")

# --- reading the .tex the PDF is built from ---
ITEM = "\\item"
# A control sequence is a backslash and letters; `\&` and friends are not, which
# is why the unescape below runs first and is left alone by this.
TEX_COMMAND = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
PREAMBLE_CMD = re.compile(
    r"\\(?:documentclass|usepackage|setlength|newcommand|setlist|pagestyle|begin|end)\b")
TEX_UNESCAPE = [
    ("\\&", "&"), ("\\%", "%"), ("\\$", "$"), ("\\#", "#"),
    ("\\_", "_"), ("\\{", "{"), ("\\}", "}"),
]


def read_tex(path):
    """[(is_bullet, text)] one entry per paragraph, in document order.

    The .tex is read rather than the PDF it compiles to, for two reasons. A
    bullet is unambiguous here - it is `\\item`, not a glyph a text extractor may
    or may not have kept - and reading it needs no third-party library, which
    keeps this gate runnable on a machine that cannot render.
    """
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("%"):
                continue
            bullet = line.startswith(ITEM)
            if bullet:
                line = line[len(ITEM):]
            elif PREAMBLE_CMD.match(line):
                continue
            text = strip_tex(line)
            if text:
                out.append((bullet, text))
    return out


def strip_tex(line):
    """The words a reader sees, with the markup taken off."""
    for escaped, plain in TEX_UNESCAPE:
        line = line.replace(escaped, plain)
    line = TEX_COMMAND.sub(" ", line)
    line = line.replace("{", " ").replace("}", " ")
    return " ".join(line.split())


def read_txt(path):
    """The plain-text variant, where mode-resume.md step 6 prefixes list items '- '."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return [(bool(re.match(r"^\s*-\s+", l)), re.sub(r"^\s*-\s+", "", l.rstrip()))
                for l in f if l.strip()]


def dangling_tail(line):
    """(word, hard) for a line ending on a word that leaves the clause unfinished."""
    stripped = re.sub(r"[\s.;:,]+$", "", line)
    words = WORD.findall(stripped.lower())
    if not words:
        return None
    last = words[-1]
    if last in DANGLING_HARD:
        return last, True
    if last in DANGLING_SOFT:
        return last, False
    return None


def opens_on_a_verb(text):
    """writing-rules.md: the Z position is where seniority shows, and it comes last -
    which only works if the bullet opens on the action rather than on context."""
    for word in WORD.findall(text.lower())[:3]:
        if word in VERBS or (len(word) > 4 and word.endswith(VERB_SUFFIXES)):
            return True
    return False


def overlap(a, b):
    x, y = set(WORD.findall(a.lower())), set(WORD.findall(b.lower()))
    return len(x & y) / len(x | y) if x | y else 0.0


def check(paragraphs):
    """(fails, warns). Paragraphs are [(is_bullet, text)]."""
    fails, warns = [], []
    lines = [(bullet, line.strip())
             for bullet, body in paragraphs
             for line in body.split("\n") if line.strip()]
    text = "\n".join(t for _, t in lines)
    bullets = [t for b, t in lines if b]

    reported = set()
    for m in re.finditer(THIRD_PERSON, text, re.I):
        word = m.group(0).lower()
        if word in reported:
            continue
        reported.add(word)
        line = text[text.rfind("\n", 0, m.start()) + 1:].split("\n")[0]
        fails.append(f"third person {m.group(0)!r} - a resume is implied first "
                     f"person: {line[:70]!r}")
    seen = set()
    for m in re.finditer(AMBIGUOUS_PERSON, text, re.I):
        word = m.group(0).lower()
        if word in seen:
            continue
        seen.add(word)
        warns.append(f"{word!r} appears - fine about a client or a team, wrong about "
                     f"the subject; check which this is")

    brackets = re.findall(r"\[[^\[\]]{0,60}\]", text)
    if brackets:
        shown = ", ".join(repr(b) for b in brackets[:4])
        more = f" (+{len(brackets) - 4} more)" if len(brackets) > 4 else ""
        fails.append(f"unresolved placeholder(s): {shown}{more} - worse than omitting "
                     f"the number")
    if re.search(r"\[(?![^\[\]]{0,60}\])", text):
        fails.append("unmatched open bracket '[' - almost always a leftover placeholder")

    for _, line in lines:
        tail = dangling_tail(line)
        if not tail:
            continue
        word, hard = tail
        message = f"sentence stops mid-clause on {word!r}: {line[-60:]!r}"
        (fails if hard else warns).append(message)

    lowered = text.lower()
    for phrase in BANNED:
        if phrase in lowered:
            warns.append(f"{phrase!r} - activity, not achievement; "
                         f"writing-rules.md says cut on sight")

    for i, a in enumerate(bullets):
        for b in bullets[i + 1:]:
            score = overlap(a, b)
            if score >= NEAR_DUPLICATE:
                kind = "duplicate" if score == 1.0 else f"{score:.0%} overlap"
                warns.append(f"near-{kind} bullets: {a[:50]!r} / {b[:50]!r}")

    for bullet in bullets:
        if not opens_on_a_verb(bullet):
            warns.append(f"bullet does not open on a verb: {bullet[:60]!r}")

    quantified = None
    if numerals is not None and bullets:
        unquantified = [b for b in bullets if not numerals(b)]
        quantified = len(bullets) - len(unquantified)
        # Listed rather than counted, because the useful output is *which*
        # bullets, and capped because a wholly unquantified draft would
        # otherwise bury every other finding. Deliberately never a failure and
        # never a threshold: a gate that demands a number is a gate that gets
        # fed an invented one, which is the exact failure provenance exists to
        # prevent. writing-rules.md names the metrics worth chasing, and
        # mode-gaps.md is where the chasing happens - with the person present.
        for bullet in unquantified[:4]:
            warns.append(f"no metric in bullet: {bullet[:60]!r}")
        if len(unquantified) > 4:
            warns.append(f"...and {len(unquantified) - 4} more bullets carry no number - "
                         f"writing-rules.md anchors Y on latency, defect rate, "
                         f"release frequency, onboarding time, users served")

    return fails, warns, quantified


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not argv:
        print("usage: check_prose.py resume.tex | resume.txt")
        return 2
    path = argv[0]
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2

    def unreadable(reason):
        print(f"checking: {os.path.basename(path)}")
        print("\nFAIL 1   WARN 0")
        print(f"  FAIL  not a readable document: {reason}")
        print("\nDO NOT SEND - fix the failures above")
        return 1

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".tex":
            paragraphs = read_tex(path)
        elif ext in (".txt", ".md"):
            paragraphs = read_txt(path)
        else:
            print(f"unsupported file type {ext!r} - pass the .tex or the .txt variant")
            return 2
    except OSError as e:
        return unreadable(str(e))

    fails, warns, quantified = check(paragraphs)
    bullets = sum(1 for b, t in paragraphs if b and t.strip())

    counts = f"paragraphs: {len(paragraphs)}   bullets: {bullets}"
    if quantified is not None and bullets:
        counts += f"   quantified: {quantified}/{bullets} ({quantified * 100 // bullets}%)"
    print(f"checking: {os.path.basename(path)}")
    print(counts)
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    for f in fails:
        print("  FAIL  " + f)
    for w in warns:
        print("  warn  " + w)
    print("\nPASS - prose rules satisfied" if not fails
          else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
