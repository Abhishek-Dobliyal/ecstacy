<p align="center">
  <img src="https://raw.githubusercontent.com/Abhishek-Dobliyal/ecstacy/main/assets/logo.png" alt="Ecstacy" width="200">
</p>

<h1 align="center">Ecstacy</h1>

<p align="center">
  <em>Beautiful data, right in your terminal.</em>
</p>

<p align="center">
  <a href="https://github.com/Abhishek-Dobliyal/ecstacy/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Abhishek-Dobliyal/ecstacy/ci.yml?label=CI" alt="CI">
  </a>
  <a href="https://pypi.org/project/ecstacy-tui/">
    <img src="https://img.shields.io/pypi/v/ecstacy-tui" alt="PyPI version">
  </a>
  <a href="https://pepy.tech/projects/ecstacy-tui">
    <img src="https://static.pepy.tech/badge/ecstacy-tui" alt="Downloads">
  </a>
  <a href="https://pypi.org/project/ecstacy-tui/">
    <img src="https://img.shields.io/pypi/pyversions/ecstacy-tui" alt="Python versions">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/Abhishek-Dobliyal/ecstacy" alt="License">
  </a>
  <a href="https://github.com/Abhishek-Dobliyal/ecstacy/stargazers">
    <img src="https://img.shields.io/github/stars/Abhishek-Dobliyal/ecstacy?style=social" alt="Stars">
  </a>
  <a href="https://github.com/Abhishek-Dobliyal/ecstacy/forks">
    <img src="https://img.shields.io/github/forks/Abhishek-Dobliyal/ecstacy?style=social" alt="Forks">
  </a>
  <img src="https://img.shields.io/badge/code%20style-ruff-000000" alt="Code style: ruff">
  <a href="https://textual.textualize.io/">
    <img src="https://img.shields.io/badge/made%20with-Textual-8A2BE2" alt="Made with Textual">
  </a>
</p>

Ecstacy is a Textual TUI for visualizing data from local files, REST endpoints,
SQL, and WebSockets -- with charts, tables, sparklines, gauges, heatmaps and a
JSON explorer. Any source feeds any visualization through a typed `DataSet`
contract, and dashboards compose multiple panels from a single YAML file.

<table>
<tr>
  <td align="center" width="50%"><b>Splash screen</b><br><br><img src="https://raw.githubusercontent.com/Abhishek-Dobliyal/ecstacy/main/assets/splash.png" alt="Splash screen"></td>
  <td align="center" width="50%"><b>Home screen</b><br><br><img src="https://raw.githubusercontent.com/Abhishek-Dobliyal/ecstacy/main/assets/home.png" alt="Home screen"></td>
</tr>
<tr>
  <td align="center" width="50%"><b>Sparkline chart</b><br><br><img src="https://raw.githubusercontent.com/Abhishek-Dobliyal/ecstacy/main/assets/sparkline.png" alt="Sparkline chart"></td>
  <td align="center" width="50%"><b>JSON explorer</b><br><br><img src="https://raw.githubusercontent.com/Abhishek-Dobliyal/ecstacy/main/assets/json.png" alt="JSON explorer"></td>
</tr>
</table>

## Install

```
pip install ecstacy
```

Then launch it:

```
ecstacy
```

You can also run it directly with [uv](https://docs.astral.sh/uv/) from a clone
of this repo:

```
uv sync
uv run ecstacy
```

## Quick start

Open a file directly:

```
ecstacy file sample.csv --chart line
ecstacy file data.csv --chart bar --x region --y value
ecstacy file metrics.parquet --chart table --max-rows 1000
ecstacy file sheet.xlsx --sheet data --chart table
```

Auto-refresh a live source:

```
ecstacy file metrics.csv --refresh 5s --chart line
ecstacy rest https://api.example.com/metrics --refresh 10s --chart table
```

Press `r` to manually refresh the current chart.

Pipe data in from stdin:

```
cat data.csv | ecstacy file -
curl -s https://api.example.com/items.json | ecstacy file - --format json
```

Go headless -- print rows or export without launching the TUI:

```
ecstacy file data.csv --head 20
ecstacy file data.csv --tail 5 --export csv > out.csv
ecstacy rest https://api.example.com/items --export json > out.json
ecstacy file data.csv --export markdown > out.md
ecstacy socket ws://localhost:8765 --head 20 --timeout 3
```

Query a REST endpoint:

```
ecstacy rest https://api.example.com/items --json-path data.items --chart table
```

Run a DuckDB SQL query:

```
ecstacy sql "select 1 as a, 2 as b" --chart table
ecstacy sql "select * from 'data.csv'" --db :memory: --chart line
```

Run a SQLite query:

```
ecstacy sqlite "select * from metrics" --db app.db --chart table
```

Stream from a WebSocket:

```
ecstacy socket ws://localhost:8765 --chart table
```

Open a multi-panel dashboard:

```
ecstacy dashboard ops.yaml
```

Inspect available themes, charts, or your config path:

```
ecstacy themes
ecstacy charts
ecstacy config path
```

## Sources

| Source   | Formats / protocol                                        |
|----------|-----------------------------------------------------------|
| file     | CSV, TSV, JSON, NDJSON, Parquet, log/text, Excel (xlsx)   |
| stdin    | `ecstacy file -` -- CSV, TSV, JSON, NDJSON, log from pipe |
| rest     | HTTP/HTTPS JSON endpoints with dotted json-path           |
| sql      | DuckDB queries (in-memory or file-backed)                 |
| sqlite   | SQLite queries (in-memory or file-backed)                 |
| socket   | WebSocket streaming JSON records                          |

## Visualizations

table (sortable, searchable, column picker, export), line, bar, histogram,
scatter, sparkline, gauge, heatmap (correlation matrix), box plot, proportion
chart (horizontal bars, formerly `pie`), summary card
(count/mean/median/std/min/max), json tree.

## Keys

Home: `o` open, `d` dashboard, `t` pick theme, `?` help, `q` quit.
Chart: `n`/`right` next chart, `p`/`left` previous chart, `ctrl+f` query/transform, `r` refresh, `t` pick theme, `esc` back.
Table: `s` sort by column, `/` focus search, `c` column picker, `e` export view, type to filter, `esc` clear.
Dashboard: `m` toggle grid/single layout, `n`/`p` cycle panels, `r` refresh now, `esc` back.

## Themes

Five built-in themes: `ecstacy-dark` (default), `ecstacy-light`, `onedark`,
`darcula`, `synthwave`. Press `t` to open the theme picker, or set one in
`config.yaml`:

```yaml
theme: synthwave
```

## Configuration

Ecstacy layers configuration in this order (later wins):

1. Built-in defaults.
2. User config: `$XDG_CONFIG_HOME/ecstacy/config.yaml` (or `~/.config/ecstacy/config.yaml`).
3. Project config: `./ecstacy.yaml` in the current directory.
4. Environment variables prefixed `ECSTACY_` (e.g. `ECSTACY_THEME=ecstacy-light`).
5. CLI flags.

On first run Ecstacy auto-creates the user config directory and a default
`config.yaml` (it never overwrites an existing one).

Example `config.yaml`:

```yaml
theme: ecstacy-dark
refresh: 0s
splash: true
max_rows: 1000
```

## Dashboards

A dashboard YAML describes sources and panels. Each panel binds a source to a
visualization with an optional column mapping. Source paths are resolved
relative to the dashboard file, so dashboards are portable.

```yaml
theme: ecstacy-dark
refresh: 5s
sources:
  - id: metrics
    kind: file
    path: ./sample.csv
panels:
  - source: metrics
    viz: line
    x: timestamp
    y: [revenue, margin]
  - source: metrics
    viz: bar
    category: region
    value: revenue
```

When `refresh` is set, dashboard panels re-fetch on that interval. Press `m` to
switch between grid and single-panel layouts.

## Architecture

- `core` -- `DataSet` contract, plugin registry, transforms, store, scheduler.
- `sources` -- file, rest, sql, sqlite, socket -- all registered plugins.
- `widgets` -- visualization widgets, registered plugins.
- `screens` -- splash, home, chart, dashboard, modal, help.
- `config` -- defaults, Pydantic schema, layered config loader.
- `theming` -- Textual themes and the global stylesheet.

Sources resolve to a typed `DataSet` (DataFrame + schema + meta). Widgets bind
to a `DataSet` and a column mapping, so any source can feed any visualization.

## Extending

Add a source by subclassing `Source` and decorating it with
`@registry.sources.register("name")`. Add a visualization by creating a widget
with a `set_data(dataset, mapping)` method and decorating it with
`@registry.viz.register("name")`.

## Known limitations

- Headless export is stdout-only (CSV/JSON/Markdown); in-TUI export writes to file. No PNG/SVG yet.
- No clipboard, Prometheus, InfluxDB, or Google Sheets source yet.

## License

MIT. See [LICENSE](LICENSE).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
