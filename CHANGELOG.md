# Changelog

All notable changes to this project will be documented in this file.

## 0.3.3 - 2026-04-11

- Fixed the packaged README for PyPI by switching the screenshot and license badge links to absolute GitHub-hosted URLs instead of repo-relative paths.
- Reduced the CI test matrix to Python `3.12` only.

## 0.3.2 - 2026-04-11

- Improved editing flow by handling `Escape` correctly in URL edit mode and preventing it from collapsing the Home sidebar.
- Fixed env placeholder handling for hyphenated names, preserved placeholders in header previews, and expanded placeholder highlighting across request views.
- Persisted root-level requests across restarts and added coverage for the related storage behavior.
- Updated the packaged welcome screenshot from PNG to SVG for sharper README rendering.

## 0.3.1 - 2026-04-11

- Updated the packaged README screenshot URL to a cache-busting, commit-pinned asset URL for package indexes.

## 0.3.0 - 2026-04-11

- Refactored the application architecture into dedicated domain, state, storage, screen, interaction, and UI modules, and removed the legacy rendering facade.
- Reworked the Home, Env, and History screens with dedicated controllers/screens, sidebar tree navigation, improved layout/state flow, and more stable focus, overlay, jump-mode, and search behavior.
- Expanded request editing with `HEAD` and `OPTIONS` methods, a new `Options` tab, SSL certificate verification, Description and Follow Redirects fields, a new request hotkey, body-editor copy support, and improved request/body/header/param editing flows.
- Added broader autocomplete and navigation support, including env-var autocomplete in the URL bar, tab/path completion improvements, `H`/`L` field cycling, add-row UI for request tables, and multiple bindings and selection-handling fixes.
- Introduced and adopted refactored custom `Select` and `Tree` widgets, plus theme/styling updates for method coloring, focus states, selected elements, and sidebar/request panel highlighting.
- Split collections and envs into directory-based workspace files, expanded storage/path handling and migration behavior, and improved request/auth/body/env serialization coverage.
- Updated packaging and release automation with packaged `.tcss` assets, richer project metadata URLs, CI distribution builds plus installed-wheel smoke tests, a TestPyPI publishing workflow, README installation guidance for `uv`/`pipx`, and an updated screenshot asset.
- Expanded automated coverage across app UI, rendering, commands, state/workspace logic, storage, auth, and request body handling.

## 0.2.0 - 2026-03-29

- Added `Cookie Auth`, `Custom Header`, and `OAuth 2.0` client credentials support.
- Added OAuth client auth selection for `Basic Auth header` or `Send creds in body`.
- Added configurable header prefixes for bearer and OAuth auth flows.
- Added `GraphQL`, `Binary`, raw `HTML`, and raw `JavaScript` request body support.
- Added validation and syntax highlighting improvements for GraphQL, HTML, JavaScript, and XML previews.
- Improved Binary body editing with path-oriented inline editing and filesystem path completion.
- Improved command-mode and path completion behavior, including `:import` paste support and cycling path matches with `Tab`.
- Simplified the request header area by moving the resolved URL inline and making it clickable-to-copy.
- Updated in-app `:help` so page commands and key hints reflect the current page and mode.
- Expanded automated coverage across auth, body handling, command mode, storage, rendering, and network error paths.

## 0.1.0 - 2026-03-27

- Initial public release.
- Added a terminal-first API client for organized request workflows.
- Included collections, folders, env sets, request history, replay, and a keyboard-driven TUI.
- Added local packaging metadata, CLI entrypoint support, and release-ready documentation.
