---
description: Install this checkout's jsk CLI and plugin locally, replacing the cached plugin copy
allowed-tools: Bash
---

Install the working tree of this repo as the local `jsk`: the `jsk-resume` CLI and the `jsk` Claude Code
plugin. Run each step, stop at the first failure, and report what it printed.

## Why the plugin needs a reinstall

`claude plugin update` compares version numbers. While `plugin.json` still says the version that is
installed, it reports "already at the latest version" and leaves the cached copy under
`~/.claude/plugins/cache/` as it was, so edits to `plugins/jsk/` never reach the session. The cached
copy for that version is deleted so the install has to copy the tree again.

## 1. Versions agree

```bash
cd "$(git rev-parse --show-toplevel)"
P=$(jq -r .version plugins/jsk/.claude-plugin/plugin.json)
M=$(jq -r '.plugins[] | select(.name=="jsk") | .version' .claude-plugin/marketplace.json)
echo "plugin.json $P   marketplace.json $M"
[ "$P" = "$M" ] || { echo "FAIL  the two plugin versions differ - make them agree first"; exit 1; }
```

## 2. The CLI is an editable install of this checkout

```bash
cd "$(git rev-parse --show-toplevel)"
ROOT=$(pwd -W 2>/dev/null || pwd)
LOC=$(python -m pip show jsk-resume 2>/dev/null | sed -n 's/^Editable project location: //p')
if [ -n "$LOC" ] && [ "$(cd "$LOC" && (pwd -W 2>/dev/null || pwd))" = "$ROOT" ]; then
  echo "ok    jsk-resume is editable from $LOC - it already runs the working tree"
else
  python -m pip install -e '.[all]'
fi
jsk --version
```

## 3. The plugin, reinstalled from the working tree

```bash
cd "$(git rev-parse --show-toplevel)"
P=$(jq -r .version plugins/jsk/.claude-plugin/plugin.json)
claude plugin marketplace list 2>&1 | grep -q "job-seeker-skills" \
  || claude plugin marketplace add "$(pwd)"
claude plugin marketplace update job-seeker-skills
claude plugin uninstall jsk@job-seeker-skills 2>/dev/null || true
rm -rf "$HOME/.claude/plugins/cache/job-seeker-skills/jsk/$P"
claude plugin install jsk@job-seeker-skills
```

## 4. Verify

```bash
cd "$(git rev-parse --show-toplevel)"
P=$(jq -r .version plugins/jsk/.claude-plugin/plugin.json)
if diff -rq plugins/jsk "$HOME/.claude/plugins/cache/job-seeker-skills/jsk/$P"; then
  echo "ok    the installed plugin matches plugins/jsk/"
else
  echo "FAIL  the installed plugin differs from plugins/jsk/ (listed above)"; exit 1
fi
claude plugin list 2>&1 | grep -A3 "jsk@job-seeker-skills"
```

## Report

Say, in a few lines: the version installed, whether the CLI was reinstalled or was already editable, and
whether the plugin matches the tree. End with: restart Claude Code (or start a new session) for the skill to
load the new files.
