# Changelog

All notable changes to this project will be documented in this file.

For versions ≤0.0.12, see [GitHub Releases](https://github.com/sderev/wslshot/releases).

## [Unreleased]

<!-- scriv-insert-here -->

<a id='changelog-0.1.0'></a>
## 0.1.0 - 2026-02-03

Added
-----
* `--convert-to/-c` flag (and config default) to convert screenshots to PNG/JPG/WebP/GIF during fetch, with smart JPEG transparency handling and removal of originals after conversion.
* `migrate-config` command with `--dry-run` to normalize legacy output format values safely.
* Config schema validation: validates types and values, fills missing keys with defaults, and warns about unknown keys.
* `--no-transfer` flag to print source screenshot paths without copying files or using git.

Changed
-------
* **Breaking change:** `--output-style` is now the only output selector; deprecated `--output-format/-f` and `plain_text` output were removed—use `text`, `markdown`, or `html` instead.
* Clarified `--convert-to` documentation so it's clear when conversions run, which formats are supported, and that converted files replace the originals.
* Config is validated on load; invalid configurations are automatically fixed by resetting to defaults.

Fixed
-----
* Staging falls back to individual file staging when batch `git add` fails, so valid captures still reach the index.
* Screenshot discovery is case-insensitive, so files like `IMAGE.PNG` and `SHOT.JPG` are included.
* Config saves are crash-safe and resilient to non-critical file system errors.
* Non-interactive runs no longer block when `config.json` is corrupted; it is backed up and defaults are restored.
* Non-dict JSON config files are treated as corrupted (warning, backup, reset) instead of crashing.
* Missing git is handled gracefully: staging is skipped instead of crashing.
* Read-only parsing avoids config writes or backups when `--no-transfer` reads a corrupted config.
* Default source validation is skipped when `wslshot fetch` uses an explicit image path.

Security
--------
* **Breaking change:** Enforce non-bypassable image size ceilings (50MB per file, 200MB aggregate) and treat decompression bombs as errors so oversized or malicious images are rejected even when limits are "disabled."
* **Breaking change:** Reject symlinks in sources, destinations, direct image paths, and configuration paths to prevent unauthorized file access; symlinked files inside the source directory are also rejected unless `--allow-symlinks` is set.
* Fix race condition vulnerabilities in directory creation to prevent symlink attacks.
* Validate PNG/JPEG/GIF image integrity to block corrupted or spoofed images before processing.
* Removed semantic prefixes from generated screenshot filenames to improve anonymization.
* Configuration files are written with `0600` permissions.
* Sanitize filesystem paths in error messages to prevent disclosure; paths display as `<...>/filename` to preserve user context while hiding sensitive information.
