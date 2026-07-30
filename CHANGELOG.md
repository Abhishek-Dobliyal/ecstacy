# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.4] - 2026-07-30

### Fixed
- Invisible text in the search and query bars: Textual's `Input` has a
  default `border: tall` that consumed both rows of the `height: 1`
  allocation, leaving zero visible content rows. Added `border: none` to
  both inputs so typed text and the cursor are now visible.
- Escape from search: pressing `escape` while the search or query input
  is focused now unfocuses it instead of popping the screen back to home.
  Press `escape` again to go back. This is the standard "escape once to
  exit search, escape again to exit" UX pattern.
- Input bar layout: the search bar (was inside the table, below the viz
  border title) and the query bar (was above the border title) are now
  side by side in a single row above the viz-holder, each 50% width. The
  search bar is hidden on non-table views. Search text persists across
  viz cycles. Net savings of 2 rows vs the previous stacked layout.

## [0.9.3] - 2026-07-30

### Added
- Dashboard per-panel transform cache: transformed `DataSet` objects are
  cached per panel keyed by upstream dataset identity. On refresh ticks
  where the upstream dataset hasn't changed (e.g. a REST TTL cache hit
  returns the same object), the transform + `infer_schema` are skipped
  entirely — the cached `DataSet` is delivered directly to the widget.

### Changed
- `_build_transformed` optimizes schema construction for simple transforms:
  `where`-only filters reuse the upstream schema (no `infer_schema` call);
  `select`/`limit`-only transforms slice the upstream schema as a subset.
  Only `group_by`/`agg`/`resample` transforms (which change the column set)
  require a full `infer_schema`.
- Panel cache is cleared on layout rebuild (`m` toggle / panel switch) to
  stay safe across panel index changes.

## [0.9.2] - 2026-07-30

### Added
- Dashboard WebSocket streaming: socket sources on a dashboard now stream
  live into panels instead of polling. Stream and poll sources coexist on
  the same dashboard. An initial seed fetch fills panels immediately so
  they don't wait for the first stream batch (up to the socket timeout).
  Stream updates are gated like poll ticks (skipped while a modal is on
  top). Manual refresh (`r`) notifies "stream sources update automatically"
  for stream-only dashboards.
- REST TTL cache: `RestSource` accepts a `ttl` param (seconds, default 0
  = disabled). When set, `fetch()` returns the cached `DataSet` within the
  TTL window, avoiding redundant HTTP requests on dashboard refresh ticks.
  Errors are not cached. Manual refresh (`r`) bypasses the cache via a
  `force` kwarg plumbed through `Scheduler.run_now` → `fetch(force=True)`.

## [0.9.1] - 2026-07-29

### Added
- Progressive loading for file sources: the first 1000 rows (`DEFAULT_MAX_ROWS`)
  are fetched with DuckDB `LIMIT` pushdown and rendered instantly, then the
  full dataset is fetched in the background and delivered to the active widget
  in place. Perceived latency on large files drops from "full parse" to "first
  batch" (~4 ms for 1000 rows vs ~391 ms for 1M). If the full fetch fails, a
  warning notifies the user that they're seeing the first 1000 rows only.
  Skipped when `--max-rows` is set below 1000 or for non-progressive sources
  (REST, SQL, SQLite, socket, stdin).

## [0.9.0] - 2026-07-29

### Added
- Viz widget pooling: `ChartScreen` now lazily creates and pools each viz
  widget on first visit, then reuses it on subsequent `n`/`p` cycles via
  `display` toggle instead of unmounting and re-mounting. Eliminates the
  CSS cascade + layout + focus bookkeeping cost on every viz switch.

### Fixed
- The transform/query bar (`ctrl+f`) and the table search bar (`/`) no
  longer have a decorative round border. The border consumed both rows of
  the `height: 1` allocation, leaving zero visible content rows — typed
  text and the cursor were invisible even though the inputs worked.

## [0.8.0] - 2026-07-29

### Added
- LTTB (Largest-Triangle-Three-Buckets) downsampling for line and scatter
  charts: preserves peaks and valleys that `tail()` silently dropped, at
  ~20 ms for 1M → 1000 points (numpy, no new deps).
- Terminal-budget downsampling: the point cap is now `2× widget width`
  clamped to [200, 2000] instead of a fixed 1000, so render cost is
  O(terminal size), fully decoupled from data size. Falls back to 1000
  before the widget is sized.
- Render-data cache on `PlotWidget`: the prepared plot payload (downsampled
  series, groupby results, correlation matrix) is cached keyed on
  `(dataset identity, mapping, budget)`. Theme toggles re-paint from the
  cache without recomputing the series.
- Worker-thread `_prepare` / `_paint` split: every `PlotWidget` subclass
  runs its pandas/numpy prep (`dropna`, `groupby`, `corr`, LTTB) on a
  worker thread, leaving only plotext rasterization on the UI thread. A
  generation counter discards stale results from cancelled workers.

### Changed
- `PlotWidget` rendering is split into `_prepare(frame, mapping, budget)`
  (pure computation, off-thread) and `_paint(plt, payload, theme)` (plotext
  + colors, UI thread). Subclasses must implement both instead of `_draw`.
- Theme toggle (`t`) is now a repaint, not a recompute: the cached render
  payload is re-painted with new theme colors without re-running the
  pandas/numpy pipeline.
- Downsample ordering fix: `tail(budget)` now runs *before* `dropna` /
  `to_numeric` in line, scatter, histogram, and sparkline, so NaN-removal
  and type coercion run on ≤budget rows instead of the full frame.
- `TableView.set_data` no longer discards the user's sort order and hidden
  columns on every refresh tick — they are preserved when the column set
  is unchanged, and reset only when the schema changes.
- `TableView` string-frame cache is no longer busted unconditionally in
  `set_data`; it invalidates naturally when the frame object changes (as
  on a refresh tick).
- `Scheduler` prunes finished workers from its internal list on each tick,
  preventing unbounded growth over long refresh sessions.

## [0.7.1] - 2026-07-29

### Added
- DuckDB universal reader: CSV, TSV, Parquet, JSON, and NDJSON files are
  now read through DuckDB's native C++/Rust parsers with `LIMIT` pushdown
  and automatic type inference (including TIMESTAMP/DATE). Excel, log,
  and stdin remain on their existing pandas paths.
- `keep_raw` parameter on `Source.fetch()`: the JSON-tree viz's raw
  payload is only retained when the json viz is actually selected,
  cutting peak memory from O(file size) to O(rows returned) for JSON
  sources in the common case. Threaded from `app.py` (single-source) and
  `dashboard.py` (per-source, precomputed from panel viz names).
- JSON/Parquet load benchmarks in `tests/benchmarks/`.

### Changed
- CSV 1M-row load: ~868 ms -> ~391 ms (2.2x faster, measured via
  `scripts/profile_load.py`). The 192 ms date-parsing cost drops to
  ~22 ms because DuckDB infers TIMESTAMP natively.
- Duplicate-column naming changed from `value.1` (pandas convention) to
  `value_1` (DuckDB convention), matching `deduplicate_columns`'s
  existing `_1` suffix.

## [0.7.0] - 2026-07-29

### Added
- `socket` source supports headless `--head`, `--tail`, and `--export`
  (csv/json/markdown), matching file/rest/sql/sqlite.
- Dashboard YAML rejects unknown top-level fields (e.g. a `refreh:` typo)
  with a `ConfigError` instead of silently dropping them.
- Unknown source params (e.g. `max_row:` instead of `max_rows:`) are now
  rejected with a `SourceError` at source creation, not silently swallowed.
- Dtype diet: `DataSet.from_dataframe` downcasts integers (int64->int8/16/32),
  floats (float64->float32), and low-cardinality strings to `category`,
  cutting memory on loaded frames. Transform-derived frames opt out via
  `diet=False` to preserve aggregate precision.
- Benchmark harness: `pytest-benchmark` budgets for CSV load (<= 1.5x raw
  `pd.read_csv`), 100k-row filter/transform, and 1M-point line downsample
  (<= 50 ms). Gated behind `--run-bench` so normal `pytest` runs skip them.
  `scripts/profile_load.py` reports peak RSS + cProfile hotspots per format.

### Changed
- Background refresh timers (dashboard + chart) pause while a modal screen
  is on top, so fetches and widget rebuilds no longer run invisibly under
  help/open/export modals.
- A source fetch that completes after the user navigated away no longer
  pushes a `ChartScreen` on top of wherever they are. The originating
  screen is recorded at open time and checked before the push.

### Removed
- `ecstacy.core.store.Store` (write-only, read by nothing in production).
  `EcstacyApp.store` and the `DashboardScreen` store parameter are gone.

## [0.6.1] - 2026-07-29

### Fixed
- README downloads badge now uses the pepy.tech badge (the shields.io
  PyPI badge was rate-limited upstream and showed a stale count).
- An unknown `--format` (e.g. `--format csvv`) now raises a clear error
  instead of silently reading the file as a log.
- WebSocket connect now respects `--timeout` (previously only per-message
  receives timed out).
- `--sheet 0` is treated as sheet index 0, not a sheet named "0".

## [0.6.0] - 2026-07-29

### Added
- WebSocket sources now stream live into the chart view: batches from
  `SocketSource.stream()` update the current visualization as they arrive.
- Dashboard panels update in place on refresh instead of rebuilding the
  whole grid, preserving each panel's table state (search, sort, hidden
  columns) and skipping widget/CSS reconstruction per tick.
- Manual refresh (`r`) now works on any opened source, not only with
  `--refresh`.
- `sql` (DuckDB) sources accept `--max-rows`, matching `sqlite`.

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
- Read-only CLI commands (`themes`, `charts`, `config path`) no longer
  create the user config file as a side effect; it's created on TUI launch.
- `--max-rows` help text reflects all supported sources; dashboards no
  longer pass it to socket sources (it was silently ignored).

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
- Dead code: `Store.subscribe`/`Listener` (no consumers), `Registry.add`,
  `Transform.extra`, `Meta.status`/`Meta.detail`, `Source.params`,
  single-column `sort_frame` (superseded by `sort_frame_multi`), and the
  pre-validation query pass in `Transform.apply` (`where` now runs once).

### Performance
- File sources cache their date-column decisions, so refresh ticks re-parse
  only known date columns instead of re-sampling every string column.
- Parquet reads stream the first row batch when `max_rows` is set (memory
  stays O(max_rows) instead of O(file size)).
- Table skips the column rebuild when the visible column set is unchanged.
- Histogram, box plot, heatmap, and sparkline cap the rows fed to plotext
  (heatmap no longer recomputes a full-frame correlation per refresh tick).

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
