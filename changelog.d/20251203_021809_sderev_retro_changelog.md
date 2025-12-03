Security
--------
- **Breaking change:** Enforce non-bypassable image size ceilings (50MB per file, 200MB aggregate) and treat decompression bombs as errors so oversized or malicious images are rejected even when limits are "disabled."
- **Breaking change:** Reject symlinks in sources, destinations, and direct image paths to close CWE-59 exfiltration; opt into `--allow-symlinks` only when you explicitly trust the paths.
- Validate PNG/JPEG/GIF inputs via magic bytes and trailer checks across CLI flows to block corrupted or spoofed images before processing.

Added
-----
- `--convert-to/-c` flag (and config default) to convert screenshots to PNG/JPG/WebP/GIF during fetch, with smart JPEG transparency handling and removal of originals after conversion.
- `migrate-config` command with `--dry-run` to normalize legacy output format values safely.

Changed
-------
- **Breaking change:** `--output-style` is now the only output selector; deprecated `--output-format/-f` and `plain_text` output were removed, so use `text`, `markdown`, or `html` instead.
- Clarified `--convert-to` documentation so it's clear when conversions run, which formats are supported, and that converted files replace the originals.

Fixed
-----
- `stage_screenshots` now falls back to staging files individually when batch `git add` fails, so valid captures still reach the index.
- Screenshot discovery is case-insensitive, so files like `IMAGE.PNG` and `SHOT.JPG` are included.
- Config writes fsync both file and directory entries to avoid losing settings if the system crashes mid-save.
