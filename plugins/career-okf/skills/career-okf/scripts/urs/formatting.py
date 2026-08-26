"""Turn URS values into the strings a document actually shows.

Dates, grades, quantities, and the fold to ASCII. Nothing here reads a view, a
profile or a record - these are pure functions over single values, which is why
they can be tested and reasoned about on their own.

Split out of plan.py: resolving *what* a document says is a different job from
formatting *how* a single value reads.
"""

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ASCII_FOLD = {
    "·": "|", "•": "-", "–": "-", "—": "-", "−": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", "→": " to ", "➡": " to ", " ": " ",
    "é": "e", "è": "e", "í": "i", "ó": "o", "ú": "u",
    "á": "a", "ç": "c", "ñ": "n", "ü": "u", "ö": "o",
    "ä": "a", "ß": "ss", "™": "(TM)", "®": "(R)", "©": "(C)",
}

def fold_ascii(text):
    if text is None:
        return None
    out = "".join(ASCII_FOLD.get(ch, ch) for ch in text)
    return "".join(ch if ord(ch) < 128 else "?" for ch in out)


def fmt_instant(inst, ongoing_label="Present"):
    if not inst:
        return ongoing_label
    value = inst.get("value", "")
    precision = inst.get("precision", "year")
    if inst.get("display"):
        return inst["display"]
    parts = value.split("-")
    if precision == "year" or len(parts) == 1:
        return parts[0]
    month = MONTHS[int(parts[1]) - 1] if 1 <= int(parts[1]) <= 12 else parts[1]
    return f"{month} {parts[0]}"


def fmt_period(period):
    """`Jun 2023 - Present`. A plain hyphen, because ats-rules.md requires one."""
    if not period:
        return ""
    start = fmt_instant(period.get("start"))
    state = period.get("state", "unknown")
    if state == "ongoing":
        return f"{start} - Present"
    if state == "ended":
        return f"{start} - {fmt_instant(period.get('end'))}"
    return start


def period_key(period):
    """Sort key: newest first when reversed. Missing dates sort oldest."""
    start = (period or {}).get("start") or {}
    return start.get("value", "0000")


def fmt_grade(grade):
    if not grade:
        return None
    scheme = grade.get("scheme")
    value = grade.get("value")
    label = grade.get("label")
    text = None
    if value is not None:
        if scheme == "in-cgpa-10":
            text = f"CGPA {value}/10"
        elif scheme == "in-percentage":
            text = f"{value}%"
        elif scheme == "us-gpa-4":
            text = f"GPA {value}/4.0"
        elif scheme == "de-note":
            text = f"Note {value}"
        elif scheme == "fr-20":
            text = f"{value}/20"
        else:
            scale = grade.get("scale") or {}
            text = f"{value}/{scale['max']}" if "max" in scale else str(value)
    if label:
        return f"{text}, {label}" if text else label
    return text


def fmt_quantity(q):
    if not q:
        return ""
    value = q.get("value")
    shown = f"{value:,.0f}" if isinstance(value, (int, float)) and value == int(value) else str(value)
    bits = [b for b in (q.get("currency"), shown, q.get("unit")) if b]
    return " ".join(bits)
