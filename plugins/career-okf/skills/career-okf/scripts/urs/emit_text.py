"""Plain text emitter, for portals with paste-in boxes.

Headings are upper-cased because a plain-text file has no other way to signal
one, and the parser matching on 'EXPERIENCE' is case-insensitive anyway.
"""


def emit(plan):
    out = [plan["name"]]
    out.extend(plan["header_lines"])
    for section in plan["sections"]:
        out.append("")
        if section.get("heading"):
            out.append(section["heading"].upper())
        out.extend(_section(section))
    return "\n".join(out).rstrip() + "\n"


def _section(section):
    kind = section["kind"]
    if kind == "text":
        return list(section["paragraphs"])
    if kind == "lines":
        return list(section["lines"])
    if kind == "rows":
        return [f"{row['label']}: {', '.join(row['items'])}" for row in section["rows"]]
    if kind == "entries":
        lines = []
        for n, entry in enumerate(section["entries"]):
            if n:
                lines.append("")
            if entry.get("org_line"):
                lines.append(_pair(entry["org_line"], entry.get("org_right")))
            for role in entry["roles"]:
                lines.append(_pair(role["left"], role.get("right")))
            lines.extend(entry["lines"])
            lines.extend(f"- {b}" for b in entry["bullets"])
        return lines
    return []


def _pair(left, right):
    return f"{left} | {right}" if right else left
