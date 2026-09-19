# Environment & Shell Quirks

Read this before writing any shell command or new evaluate JS for this skill. The project typically runs on **Windows + bash shell** but the same rules apply to any platform; several "normal Linux" idioms break silently on Windows specifically.

> This file mirrors the sister skill `fastmoss-products/references/environment.md`. If both skills are installed in the same project, you only need to read either one — the rules are identical.

## Paths

- Use forward slashes (`/`) in all paths. Backslashes work in some tools but break in JSON strings.
- Use `/dev/null`, NOT `NUL` (Windows) — bash shells handle `/dev/null` correctly even on Windows.
- Output paths are user-supplied via `--out`. Never assume a specific directory layout — the bundled scripts accept any path and create parent dirs as needed.

## BrowserSkill daemon

- Daemon binary: `bsk` (CLI tool, installed via `cargo install bsk-cli`)
- Daemon listens on WebSocket (no fixed HTTP port like kimi-webbridge)
- Check health: `bsk doctor --json`
- Start daemon: `bsk daemon start`
- Stop daemon: `bsk daemon stop`
- One Chrome/Edge extension connects via WebSocket; extension status appears in the `doctor` JSON.
- If `extension.connected: false` after `start`, ask the user to open their browser (extension only runs when the browser is open).
- If running multiple FastMoss sister skills in parallel, each one defaults to its own session name (`fastmoss-products`, `fastmoss-shops`, etc.) — no conflict.

## Bash + JSON escaping rules

### `bsk` CLI commands: works
```bash
bsk navigate --session fastmoss-shops "https://example.com"
bsk evaluate --session fastmoss-shops "(() => JSON.stringify({title: document.title}))()"
```

### Heredoc `<<EOF` with JS regex: BREAKS
Bash eats one backslash layer, so `/\n+/g` arrives malformed → extension returns `"Invalid regular expression: missing /"`.

**Fix**: prefer `.split('\n')` over `.replace(/\n+/g, ...)`. For complex JS, write to a `.js` file and call via Python `bsk_client.py` (no shell layer).

### `jq` may not be installed
Decode screenshots manually:

```bash
bsk screenshot --session fastmoss-shops | python -c "import sys,json,base64; open('out.jpeg','wb').write(base64.b64decode(json.load(sys.stdin)['data']['data']))"
```

## Python file encoding

On Windows, Python defaults to GBK for `open()` and `pathlib.Path.read_text()`. CSVs produced by this skill are `utf-8-sig` (BOM) for Excel compatibility. Always read with explicit encoding:

```python
with open('your.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
```

## Browser session

- Default session `"fastmoss-shops"` for all calls (isolated from sister skills' sessions like `fastmoss-products`, `fastmoss-creators`). Override via `--session` if needed.
- `bsk session stop fastmoss-shops` closes ALL tabs in the session — always run at task end.
- `bsk tab create --session fastmoss-shops <url>` works whether or not the session pre-exists.
