"""The page fitter's levers and its measurements, as pure functions of the .tex's text.

Each lever rewrites one of the knobs emit_latex.py keeps literal and one per line, and
never past the floors `references/ats-rules.md` sets, so the floors are tested without a
TeX engine. The measurements read the page geometry infra/pdf.py returns.
"""
import math
import re

MARGIN_FLOOR_IN = 0.5
FONT_FLOOR_PT = 10.0

# The four knobs emit_latex.py promises to keep literal and one per line.
SECTION_GAP = re.compile(r"(\\setlength\{\\sectiongap\}\{)([\d.]+)pt(\})")
ENTRY_GAP = re.compile(r"(\\setlength\{\\entrygap\}\{)([\d.]+)pt(\})")
TOPSEP = re.compile(r"(topsep=)([\d.]+)pt")
ITEMSEP = re.compile(r"(itemsep=)([\d.]+)pt")
MARGIN = re.compile(r"(margin=)([\d.]+)(in\])")
BODY_FONT = re.compile(r"(\\fontsize\{)([\d.]+)pt\}\{([\d.]+)pt(\})")


# --- the lever plan -------------------------------------------------------------
#
# A state is (spacing, bullet_spacing, margin_inches, font_delta_points). Each step is
# derived from the ORIGINAL document rather than from the previous step, so repeated
# rounding cannot drift a value past a floor. `None` means "leave this alone".

def lever_plan():
    """The levers in the order they are tried, each step carrying the ones before it.

    Returns:
        [(label, state)], cheapest-looking first, the last at every floor.
    """
    steps = []
    for f in (0.75, 0.5, 0.25, 0.0):
        steps.append((f"inter-paragraph spacing x{f:g}", (f, None, None, 0)))
    base = 0.0
    for f in (0.5, 0.0):
        steps.append((f"bullet spacing x{f:g}", (base, f, None, 0)))
    for inches in (0.7, 0.6, 0.55, MARGIN_FLOOR_IN):
        steps.append((f"margins {inches:.2f}in", (base, 0.0, inches, 0)))
    for d in (0.5, 1.0):
        steps.append((f"body font -{d:g}pt", (base, 0.0, MARGIN_FLOOR_IN, d)))
    return steps


# --- LaTeX transforms -----------------------------------------------------------
#
# Each is a pure string -> string, so the floors can be tested without a TeX engine.

def _scale(pattern, tex, factor, groups=3):
    """`tex` with each `pattern` match's point value (group 2) multiplied by `factor`.

    Args:
        pattern: a knob's regex; group 1 precedes the value, groups 3.. follow its "pt".
        tex: the .tex text.
        factor: the multiplier.
        groups: the pattern's last group.

    Returns:
        The rewritten text.
    """
    def fix(m):
        value = float(m.group(2)) * factor
        tail = "".join(m.group(i) for i in range(3, groups + 1))
        return f"{m.group(1)}{value:g}pt{tail}"
    return pattern.sub(fix, tex)


def scale_spacing(tex, factor):
    """Section and entry gaps. A lever must only ever remove space."""
    tex = _scale(SECTION_GAP, tex, factor)
    return _scale(ENTRY_GAP, tex, factor)


def scale_bullet_spacing(tex, factor):
    """The lists' topsep and itemsep, scaled by `factor`; the rest of `tex` untouched."""
    tex = _scale(TOPSEP, tex, factor, groups=2)
    return _scale(ITEMSEP, tex, factor, groups=2)


def set_margins(tex, inches):
    """Never below the 0.5in floor, whatever the caller asks for."""
    inches = max(float(inches), MARGIN_FLOOR_IN)
    return MARGIN.sub(lambda m: f"{m.group(1)}{inches:g}{m.group(3)}", tex)


def shrink_font(tex, delta_pt):
    """Lower the body size by delta, never below the 10pt floor."""
    def fix(m):
        size = max(float(m.group(2)) - float(delta_pt), FONT_FLOOR_PT)
        return f"{m.group(1)}{size:g}pt}}{{{size * 1.2:g}pt{m.group(4)}"
    return BODY_FONT.sub(fix, tex)


def apply_state(tex, state):
    """`tex` with every lever `state` sets applied (see lever_plan for a state's shape).

    Args:
        tex: the original .tex text - never a previous step's.
        state: (spacing, bullet_spacing, margin_inches, font_delta_points), None or 0
            leaving that knob alone.

    Returns:
        The rewritten text.
    """
    spacing, bullet, margin_in, font_delta = state
    if spacing is not None:
        tex = scale_spacing(tex, spacing)
    if bullet is not None:
        tex = scale_bullet_spacing(tex, bullet)
    if margin_in is not None:
        tex = set_margins(tex, margin_in)
    if font_delta:
        tex = shrink_font(tex, font_delta)
    return tex


def describe(state):
    """Every lever a state moves, in plan order, each at the value it sets.

    The plan's labels name only the step that was reached, and each step carries the
    ones before it: "margins 0.60in" is also no paragraph and no bullet spacing. `jsk
    ship` prints this line, so what it says it applied is everything it applied."""
    spacing, bullet, margin_in, font_delta = state
    moved = []
    if spacing is not None:
        moved.append(f"inter-paragraph spacing x{spacing:g}")
    if bullet is not None:
        moved.append(f"bullet spacing x{bullet:g}")
    if margin_in is not None:
        moved.append(f"margins {margin_in:g}in")
    if font_delta:
        moved.append(f"body font -{font_delta:g}pt")
    return ", ".join(moved)


def current_margin_in(tex):
    """The margin `tex` sets, in inches, or None when it sets none."""
    m = MARGIN.search(tex)
    return float(m.group(2)) if m else None


def body_font_pt(tex):
    """The body size `tex` sets, in points, or None when it sets none."""
    m = BODY_FONT.search(tex)
    return float(m.group(2)) if m else None


# --- measurement ----------------------------------------------------------------

def fill_percent(page):
    """How far down `page` (one of infra.pdf.measure's) its text reaches, in percent."""
    h = page["height"] or 1
    return 100.0 * page["bottom"] / h


def diagnose(pages, target, bottom_margin_pt):
    """Why the document spills: what opened the overflow page, and what room was left.

    This is the measurement the issue says was taken last instead of first. A block
    held together either fits in the remaining space or it does not, and trimming
    words elsewhere cannot change that unless it frees a whole line.
    """
    if len(pages) <= target or target < 1:
        return None
    spilled = pages[target]
    previous = pages[target - 1]
    free = previous["height"] - bottom_margin_pt - previous["bottom"]
    return {
        "text": spilled["first_text"],
        "needs": spilled["first_height"],
        "free": max(free, 0.0),
    }


def lines_over(pages, target, margin_pt, line_pt):
    """About how many body lines the pages past the budget hold, less the room left
    on the last page inside it. 0 when the document fits.

    The Arrow run (2026-09-29) was told only that it could not fit, and cut three
    confirmed bullets to make room nobody had measured. A line count says how much
    evidence the budget costs, which is what the person deciding the cut needs."""
    if len(pages) <= target or target < 1 or line_pt <= 0:
        return 0
    last = pages[target - 1]
    free = max(last["height"] - margin_pt - last["bottom"], 0.0)
    spill = sum(max(p["bottom"] - p.get("top", margin_pt), 0.0) for p in pages[target:])
    return max(math.ceil((spill - free) / line_pt), 1)
