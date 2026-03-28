# Changelog

All notable changes to this project will be documented in this file.

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
