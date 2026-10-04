# Six slash commands: intake, review, and no pipeline

Date: 2026-10-04. Branch `feat/graph-native-mcp`, plugin still unreleased as 6.0.0.

## The decision

A review of the plugin's eight slash commands (2026-10-04) found them hard to choose between:
- `gaps` and `refresh` read as one job;
- `braindump` and `setup`'s import both turned material into the career;
- `ship` froze an application without saying so;
- one folder had four names;
- the argument hints looked like flags of retired commands;
- the grants did not match the work.

The person ruled (2026-10-04):

| Before | After |
|---|---|
| `/jsk:braindump`, and `setup`'s phase 3 import | `/jsk:intake`: anything the person brings - an old resume, writing, a bundle, or talk |
| `/jsk:gaps`, `/jsk:refresh` | `/jsk:review`: one pass over the career - what is new since last time, what is weak in what is there, what needs re-confirming |
| `/jsk:pipeline` | removed, with its mode |
| `/jsk:setup` | the toolchain and the workspace, then hands to intake |
| `/jsk:resume`, `/jsk:tailor`, `/jsk:ship` | unchanged in behaviour; `ship` still records the application as sent (`app_freeze`) and says so |

## Rulings

1. **Six commands: `setup`, `intake`, `review`, `resume`, `tailor` and `ship`.**
   - The commands and their mode files go together: `commands/braindump.md`, `gaps.md`,
     `refresh.md` and `pipeline.md` are deleted, and so are `references/mode-braindump.md`,
     `mode-gaps.md`, `mode-refresh.md` and `mode-pipeline.md`.
   - `references/mode-intake.md` and `mode-review.md` replace them. Each command is a skill call
     with the mode's name, as now.
   - A slash command is not the `jsk` CLI's frozen surface, so a removed one gets no stub. README's
     6.0 notes name the change.
2. **Intake owns turning material into the career.**
   - `mode-intake.md` holds braindump's procedure (let them finish; keep their words verbatim under
     `sources/<yyyy-mm-dd>-braindump.md`; the extractor; one `career_apply`).
   - It also holds `setup`'s document import (keep the document verbatim under `sources/`; read it
     critically; the extractor; confirm what the document states with `source=` and `quote=`) and
     the older-bundle import.
   - It then "goes deeper" on what a document never holds, as setup did when it switched to
     braindump.
   - `mode-setup.md` keeps phases 1, 2 and 4 (toolchain, gaps in the toolchain, proof). Its phase 3
     creates the workspace (`jsk kb new`, or `jsk kb load` of a dump) and then reads
     `mode-intake.md` for whatever the person brings.
3. **Review is one pass, ordered.**
   - `mode-review.md` starts from the record's own state (`career_check`, `career_log`, and the
     `open`, `unconfirmed`, `stale` and `absences` queries, from refresh's "Orient first").
   - Then it asks what happened since the last pass, refresh's half.
   - Then it works through the audit: the `jsk-kb-auditor`'s `audit.gaps.md`, in the order the
     auditor writes it, which is gaps' half.
   - What both did (re-confirming, closing an absence) is said once.
   - The merged file is shorter than the two it replaces.
   - The tailoring round's gap rounds stay in `mode-tailor.md`. Wherever `mode-gaps.md` was named
     as the shared format, `mode-review.md` is named.
4. **Pipeline goes entirely.**
   - The board and chasing flow is deleted.
   - The tools stay: `app_list` reads the applications, and `app_event` records a reply, an
     interview or an outcome.
   - SKILL.md says so in one line under the tools, so a "they replied" still has somewhere to go.
     It is not a mode.
   - `mode-tailor.md`'s own "have I applied here before" check stays.
5. **What each command says.**
   - Each description says when to use the command, and names the neighbour it could be confused
     with: review against intake, resume against tailor, and ship as the last step of both.
   - The record is "the career" throughout and the folder "the workspace". "Knowledge base" goes
     from the commands and the mode prose. The `jsk kb` verbs keep their names, because the CLI is
     frozen.
   - Argument hints are plain words, not flags: "optionally a template, ats-max or a page count",
     not `--template NAME`. Each hint is quoted the same way.
6. **Grants match the work.** Each command's `allowed-tools` lists what its mode does, and no
   more:
   - `Bash` only where the mode runs a shell command (`setup`: `jsk doctor`, `jsk kb new|load`).
   - `Task` wherever the mode sends an agent (intake and setup send the extractor; review sends the
     auditor; tailor, resume and ship send theirs).
   - `Write`/`Edit` only where the mode itself writes a file (intake's `sources/` copy).
   - `mcp__plugin_jsk_graph__*` everywhere.
   - `tests/test_plugin_surface.py` pins the rule. A command whose mode sends an agent holds
     `Task`, only `setup` holds `Bash`, and a planted violation fails.
7. **The prose follows.** SKILL.md's mode table and description, the auditor's description, the
   cross-references, README, QUICKSTART and ARCHITECTURE. The `test_budget.py` caps hold: the
   intake path replaces the braindump path, with a cap raised only with a dated measurement.
   `src/jsk/domain/gates/prose_rules.py`'s comment that names `mode-gaps.md` names
   `mode-review.md`.

## Status

- Not started.
