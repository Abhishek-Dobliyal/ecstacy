# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- WebSocket sources now stream live into the chart view: batches from
  `SocketSource.stream()` update the current visualization as they arrive.
- Dashboard panels update in place on refresh instead of rebuilding the
  whole grid, preserving each panel's table state (search, sort, hidden
  columns) and skipping widget/CSS reconstruction per tick.
- Manual refresh (`r`) now works on any opened source, not only with
  `--refresh`.

### Changed
- The transform/query bar moved from `/` to `ctrl+f` (`/` stays the table
  search in the table view).
- Scheduler: a source never overlaps its own fetches — ticks arriving while
  the previous fetch runs are skipped, so results can't arrive out of order
  or pile up threads. In-flight workers are cancelled on screen exit, and
  opening with `--refresh` no longer double-fetches at start.
- Table search filtering/sorting and file export run on a worker thread, so
  the UI stays responsive on large frames.
- Table footer now reports "showing X of Y rows" when the 1000-row display
  cap applies.
- Search no longer matches against hidden columns.
- `ecstacy --version` now reports the installed package version.

### Fixed
- Chart refresh no longer drops the active transform query (the view and the
  row-count border reverted to raw data on every tick).
- SQLite `:memory:` sources no longer crash with cross-thread
  `ProgrammingError` under refresh.
- stdin in log format now honors `--max-rows`.
- Duplicate dashboard source ids are rejected with a clear `ConfigError`
  (they previously overwrote each other silently).
- Missing dashboard file raises a clean error instead of opening an empty
  dashboard; invalid dashboard YAML exits cleanly in the CLI.
- Invalid dashboard `refresh` durations are rejected at load time.
- NaN/NaT values render as empty cells in the table, summary card, and JSON
  tree (previously printed literal "nan"/"NaT").
- Bar/proportion charts find category columns under pandas 3 string dtypes
  and no longer soft-crash when category equals value.
- Line charts no longer drop rows where an unrelated y-column is NaN, and
  show a helpful title when no numeric column exists.
- Scatter plots render datetime x-axes in seconds instead of unreadable
  nanosecond integers; single-numeric-column datasets no longer plot a
  meaningless x=y diagonal.
- Sources producing duplicate column names (rest/sql/sqlite/socket) no
  longer crash schema inference.
- Gauge error messages are no longer overwritten by a running animation.
- Dashboard refresh no longer leaks REST/SQLite connections, and the stale
  single-panel subtitle is cleared when switching back to grid layout.
- Home/help text now documents sqlite, box, proportion, summary, refresh,
  and query keys accurately; splash text matches the keys that work.
- Column picker toggles multiple columns without closing.

### Removed
- `PanelConfig.layout` (was parsed but never honored); dashboards using it
  must drop the field.

## [0.5.0] - 2026-07-29

### Changed
- The `pie` visualization is renamed to `proportion` (it draws horizontal
  proportion bars; plotext has no pie primitive). `pie` remains accepted as
  an alias everywhere a visualization name is used, so existing dashboards
  and configs keep working.

## [0.4.2] - 2026-07-29

### Fixed
- Box plot, pie chart, and heatmap now render: the box plot called the
  nonexistent `plt.boxplot()` (now uses `plt.box()` with labels + raw data),
  the heatmap passed correlation values to `matrix_plot()` which expects an
  image-like color matrix (now uses `plt.heatmap()` with the labeled
  correlation DataFrame), and the pie chart relied on a nonexistent
  `plt.pie()` (now draws horizontal proportion bars, as plotext has no pie
  primitive).
- Table column sort now works: DataTable columns were added without keys, so
  a column selection resolved to the string "None" and sorting silently did
  nothing; the column is now resolved by its visual index.
- Switching visualizations no longer traps keyboard input in the
  transform/query bar: after a re-render, focus moves to the table (or is
  cleared), so n/p/arrow bindings keep working. Dashboard panel rebuilds
  reset focus the same way.

### Performance
- Table row building uses `itertuples()` instead of `iterrows()` (10-50x
  faster on large result sets).
- Table search stringifies the frame once and caches it instead of
  re-stringifying every cell on each search.
- Summary card computes all column statistics in a single aggregation pass.
- Log files are read incrementally with `itertools.islice`, so peak memory
  scales with `max_rows` instead of file size.
- REST sources reuse a single `httpx.Client` across fetches (connection
  pooling); added `RestSource.close()`.
- Plot widgets skip redundant redraws when the dataset and column mapping
  are unchanged (theme changes still repaint).
- Bar/pie charts drop a redundant frame copy.

## [0.4.1] - 2026-07-29

### Fixed
- README logo now uses absolute GitHub raw URL so it renders on PyPI.

## [0.4.0] - 2026-07-29

### Added
- Table column picker: press `c` to toggle column visibility via a modal.
- Table multi-column sort: clicking columns builds a multi-column sort
  list; clicking again toggles ascending/descending.
- Table row count footer: shows total rows, filtered count when searching,
  and active sort columns with arrows.
- Table export: press `e` to export the current filtered/sorted view to
  a file (CSV/JSON/Markdown) via a path+format modal.
- Query/transform bar in ChartScreen: press `/` to type a query like
  `where value > 100 | group_by region | agg mean | limit 10` and apply
  it live without leaving the TUI.
- `parse_transform_query()` in transforms.py for parsing pipe-separated
  query strings into Transform objects.
- Box plot visualization (distribution per category or single column).
- Pie/donut chart visualization (proportions by category).
- Summary statistics card (count, mean, median, std, min, max per column).

### Changed
- ChartScreen now has a transform bar Input at the top.
- VIZ_ORDER updated: box, pie, summary added before json.

## [0.3.0] - 2026-07-28

### Added
- Live refresh for single-source views: `--refresh 5s` on `file`, `open`,
  `rest`, `sql`, and `sqlite` commands auto-refreshes the current chart in
  place without remounting. Press `r` for manual refresh. The refresh
  indicator (⟳ Ns) appears in the chart border.
- Full test coverage for GaugeView, JsonTree, and Heatmap widgets.
- Tests for Store pub/sub, error UI paths, and `--max-rows` in TUI mode.

### Fixed
- `_autoparse_dates` now samples the first 100 non-null values before
  attempting a full-series parse, suppressing the pandas "Could not infer
  format" UserWarning on non-date string columns.

### Changed
- ChartScreen now accepts `spec` and `refresh` params; uses the existing
  `Scheduler` abstraction for live refresh (same as dashboards).
- Border subtitle updated to show `r refresh` keybinding.

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
