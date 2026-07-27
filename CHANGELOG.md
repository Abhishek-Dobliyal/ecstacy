# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
