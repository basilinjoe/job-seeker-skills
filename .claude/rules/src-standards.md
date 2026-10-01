---
paths:
  - "src/**/*.py"
---

# Commenting and coding standards for src/

These follow from how the existing code is written. Match them.

## Commenting

- **Every module opens with a docstring that argues for itself.** It says what the module decides, why the
  boundary sits where it does, and what it deliberately does not do, for example "It prints nothing:
  adapters/cli/gates/record.py says what it found". A gate module lists every FAIL and WARN it can raise.
  When a module replaced something, the docstring names what it replaced and when ("It replaced two gates
  (2026-09-25)").
- **Comments explain why, usually with the incident that made the rule.** For example: "`.title()` would render these
  as 'Ai' / 'Api'; a skills row is the most scanned line on a resume", or "That failed every no-engine run from
  2026-09-01". Never narrate what the code does. Give dates as absolute `YYYY-MM-DD`. Cite the spec or ruling a
  decision came from by path (`docs/superpowers/specs/...`, "Ruling 2").
- **Constants get a comment saying why the value or order is what it is**, not what the constant is.
- **Function docstrings start with a noun phrase saying what is returned**, not an imperative.
  For example: "The title, with its functional gloss when one adds something." Add `Args:`, `Returns:` and `Raises:`
  sections in Google style when the parameters aren't obvious. Callables passed as parameters are described by
  their shape: `read: path -> the file as a dict (compose.resume.read)`.
- **Every suppression explains itself on its own line**: `# noqa: BLE001 - a broken install raises anything; doctor
  reports it missing`. The same goes for pyright ignores, where the comment states the guarantee that makes the
  ignore safe.
- **Prose style in comments and output:** plain declarative British English ("behaviour", "organisation",
  "licence"), full sentences, and no marketing words.

## Coding

- **Placement comes first.** Put a new module in the right ring (`domain`, `ports`, `application`, `infra`,
  `adapters`; `tests/test_layers.py` enforces it). Then:
  - add a line for it in `docs/ARCHITECTURE.md`'s repo layout, or `tests/test_plugin_surface.py` fails;
  - pass anything with I/O (store, files, TeX, network, today's date) in as a parameter, and bind the real one in
    `adapters/cli/compose/`.
- **Type hints:** ports are fully annotated `typing.Protocol`s, and dataclass fields are annotated. The rest of
  `domain` and `application` is mostly unannotated, so don't add annotations wholesale to code you only touch.
  Pyright `basic` must still pass on all five rings.
- **Results:** results are `@dataclass(frozen=True)` values. Domain and application code returns them and never
  prints; adapters print.
- **Use cases:** prefer keyword-only parameters (`*,`) for a use case's ports and flags.
- **Imports:** relative imports within the package. The ontology is imported as `from .. import ontology as O`.
  Optional and heavy dependencies (pyoxigraph, pymupdf) are imported inside the function that needs them.
- **Text I/O:** always pass `encoding="utf-8"`. CI runs on Windows.
- **Command output is a contract:**
  - verdict lines are prefixed `FAIL  `, `WARN  ` or `ok    ` (two-space padding);
  - a refusal carries a `fix` naming the exact command that resolves it;
  - exit codes are uniform: `0` passed, `1` a real finding or an unknowable answer, `2` called wrong
    (`docs/SCRIPTS.md`);
  - something that can't run says so and exits non-zero. It never passes quietly.
- **Exceptions:** catch narrowly. `except Exception` is allowed only with a `noqa: BLE001` reason. Re-raise with
  `from` (ruff `B`).
