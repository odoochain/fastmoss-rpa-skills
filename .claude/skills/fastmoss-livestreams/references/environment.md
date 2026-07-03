# Environment & Shell Quirks

Read this before writing any shell command or new evaluate JS for this skill. The project typically runs on **Windows + bash shell** but the same rules apply to any platform; several "normal Linux" idioms break silently on Windows specifically.

> This file mirrors the sister skill `fastmoss-products/references/environment.md`. If both skills are installed in the same project, you only need to read either one — the rules are identical.

## Paths

- Use forward slashes (`/`) in all paths. Backslashes work in some tools but break in JSON strings.
- Use `/dev/null`, NOT `NUL` (Windows) — bash shells handle `/dev/null` correctly even on Windows.
- `~/.kimi-webbridge/` resolves to `<user-home>/.kimi-webbridge/` on any OS.
- Output paths are user-supplied via `--out`. Never assume a specific directory layout — the bundled scripts accept any path and create parent dirs as needed.

## Kimi WebBridge daemon

- Listens on `http://127.0.0.1:10086`.
- Daemon binary: `~/.kimi-webbridge/bin/kimi-webbridge` (status/start/stop/restart/logs subcommands).
- One Chrome/Edge extension connects via WebSocket; the extension ID appears in the `status` JSON.
- If `extension_connected: false` after `start`, ask the user to open their browser (extension only runs when the browser is open).
- If running multiple FastMoss sister skills in parallel, each one defaults to its own session name (`fastmoss-products`, `fastmoss-creators`, `fastmoss-shops`, `fastmoss-livestreams`, etc.) — no conflict.

## Bash + JSON escaping rules

### `curl` with single-line JSON: works
```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"navigate","args":{"url":"https://example.com","newTab":true},"session":"fastmoss-livestreams"}'
```

### Heredoc `<<EOF` with JS regex: BREAKS
Bash eats one backslash layer, so `/\n+/g` arrives malformed → extension returns `"Invalid regular expression: missing /"`.

**Fix**: prefer `.split('\n')` over `.replace(/\n+/g, ...)`. For complex JS, write to a `.js` file and POST via Python `urllib` (no shell layer).

### `curl -d @file.json`: works for any payload
Save the JSON request body to a file, then `curl -d @body.json`. Bypasses shell escaping entirely.

### `jq` may not be installed
The kimi-webbridge `screenshot.sh` helper script depends on `jq` and will fail when it's missing. Decode screenshots manually:

```bash
curl -s -X POST http://127.0.0.1:10086/command \
  -H 'Content-Type: application/json' \
  -d '{"action":"screenshot","args":{"format":"jpeg","quality":75},"session":"fastmoss-livestreams"}' \
  | python -c "import sys,json,base64; open('out.jpeg','wb').write(base64.b64decode(json.load(sys.stdin)['data']['data']))"
```

## Python file encoding

On Windows, Python defaults to GBK for `open()` and `pathlib.Path.read_text()`. CSVs produced by this skill are `utf-8-sig` (BOM) for Excel compatibility. Always read with explicit encoding:

```python
with open('your.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
```

## Browser session

- Default session `"fastmoss-livestreams"` for all calls (isolated from sister skills' sessions). Override via `--session` if needed.
- `close_session` closes ALL tabs in the session — always run at task end.
- `navigate newTab:true` works whether or not the session pre-exists.
