# Changelog

All notable changes to `korean-stat-mcp` are documented here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-source release preparation: bilingual KO/EN README and CLAUDE manuals, GitHub Actions CI/release workflows, Issue & PR templates, Claude Code plugin manifest, public OpenAPI coverage matrix.
- `verify_statistics` MCP tool — cross-checks LLM numeric claims against KOSIS source data (planned in US-005).
- `discover_tools` and `execute_tool` meta tools for power-user introspection.
- Claude Code plugin marketplace manifest (`.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`) for `/plugin marketplace add` installation flow.
- Fly.io deploy config (`fly.toml`) and bilingual `deploy/README.md` covering Fly.io, Render, Railway, DigitalOcean App Platform, and self-hosted Docker options.

### Changed
- Renamed package from `kosis-mcp` to `korean-stat-mcp`.
- Tool surface curated via allow-list: ~24 internal tools, ~12–16 exposed to LLM clients (US-003).

### Removed
- All references to private hosting infrastructure (server hostname, owner-specific domain, temporary Cloudflare Tunnel URL) replaced with neutral placeholders or the `${KOSIS_MCP_URL}` environment variable.

### Deprecated
_(none)_

### Fixed
_(none)_

### Security
_(none)_

---

## [0.1.0] — TBD

Initial public release. See `[Unreleased]` above for the in-progress changeset.

---

[Unreleased]: https://github.com/<github-user>/korean-stat-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<github-user>/korean-stat-mcp/releases/tag/v0.1.0
