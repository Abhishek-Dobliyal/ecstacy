# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-07-28

### Changed
- Fixed all 34 ruff lint errors (import sorting, unused imports, quoted
  annotations, deprecated typing imports, line length, dead code).
  `ruff check .` now passes with 0 errors.

### Added
- GitHub Actions CI workflow running pytest + ruff on push and PR
  against Python 3.11, 3.12, and 3.13.

## [0.2.1] - 2026-07-28

### Fixed
- Dashboard initial render race: panels now render only after data arrives
  via the Scheduler's on_data callback, fixing the blank-first-render bug.
- Dashboard refresh race: refresh ticks re-render after fetch completes,
  not before.
- `--max-rows` was ignored by the `open` command (now added to spec params).
- `SourceSpec.from_dict` now raises a friendly `SourceSpecError` instead
  of a raw `KeyError` when `kind` is missing.
- Dashboard `ops.yaml` source path corrected (`./sample.csv`).
- Table sort now covers all rows, not just the first `DEFAULT_MAX_ROWS`.
- SQLite `:memory:` connection is now reused across fetches so tables
  created in one query persist to the next.

### Added
- Full Transform support in dashboard panels: `where`, `group_by`, `select`,
  and `limit` fields on `PanelConfig`, applied before rendering.
- `SourceSpecError` exception class for invalid source specs.
- Table search debounce (150ms) to reduce per-keystroke stringification.
- Chart point cap: line and scatter charts limited to last 1000 points.
- `max_rows` now applied at read time for JSON and log file formats.

### Changed
- Dashboard refresh uses the existing `Scheduler` abstraction instead of
  duplicated `set_interval` + `run_worker` logic.

## [0.2.0] - 2026-07-28

### Added
- Stdin source: `ecstacy file -` (or pipe data in) reads CSV, TSV, JSON, NDJSON,
  and log/text from standard input. Pair with `--format` to override the
  inferred format.
- Headless mode: `--head N` and `--tail N` print rows to stdout and exit
  without launching the TUI. Available on `file`, `open`, `rest`, `sql`, and
  `sqlite`.
- Export: `--export {csv,json,markdown}` writes the dataset to stdout
  (headless) and works with `--head`/`--tail`/`--max-rows`.
- SQLite source via the new `sqlite` command (`ecstacy sqlite "SELECT ..."`
  with `--db path`).
- Excel (.xlsx, .xls) support in the file source via openpyxl, with an
  optional `--sheet` flag.
- User config directory and default `config.yaml` are now auto-created on
  first run (idempotent, never overwrites an existing file).

### Changed
- Bumped to `tabulate` (for Markdown export) and `openpyxl` (for Excel) as
  core dependencies.

### Fixed
- None.

## [0.1.2] - 2026-07-28

### Changed
- Updated all dependencies to their latest versions (textual 8.2.8,
  pandas 3.0.5, numpy 2.4.3+, pyarrow 25.0.0, duckdb 1.5.5, httpx 0.28.1,
  orjson 3.11.9, pyyaml 6.0.3, typer 0.27.0, pydantic 2.13.4,
  websockets 16.1.1, plotext 5.3.2).
- Fixed upper bounds that were blocking latest versions (textual <1 → <9,
  pandas <3 → <4, pyarrow <20 → <26, websockets <15 → <17).

## [0.1.1] - 2026-07-27

### Fixed
- README images now use absolute GitHub URLs so they render on PyPI.

## [0.1.0] - 2026-07-27

### Added
- First public release.
- Textual TUI for terminal data visualization.
- Sources: file (CSV, TSV, JSON, NDJSON, Parquet, log), REST, SQL (DuckDB),
  WebSocket.
- Visualizations: table (sortable and searchable), line, bar, histogram,
  scatter, sparkline, gauge, heatmap, JSON tree.
- Multi-panel dashboards from YAML with grid and single-panel layouts (`m` to
  toggle) and live refresh.
- Layered configuration: defaults, user YAML, project YAML, environment
  variables, CLI overrides (validated with Pydantic).
- Two built-in themes (ecstacy-dark, ecstacy-light) with `t` to toggle.
- Splash screen, home screen, help screen.
- `--max-rows` CLI option to cap rows loaded from file and REST sources.
- Config validation with Pydantic, friendly error messages via `SourceError`,
  `ConfigError`, `TransformError`.
- Plugin registry for sources and visualizations.

### Known limitations
- No export to file yet (CSV/JSON/Markdown/PNG).
- No Excel, SQLite, clipboard, or stdin source yet.
- Live refresh applies to dashboards only (not single-source views).
