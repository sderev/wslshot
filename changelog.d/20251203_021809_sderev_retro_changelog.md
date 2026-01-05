Security
--------
- **Breaking change:** Enforce non-bypassable image size ceilings (50MB per file, 200MB aggregate) and treat decompression bombs as errors so oversized or malicious images are rejected even when limits are "disabled."
- **Breaking change:** Reject symlinks in sources, destinations, and direct image paths to prevent unauthorized file access; opt into `--allow-symlinks` only when you explicitly trust the paths.
- Validate PNG/JPEG/GIF image integrity to block corrupted or spoofed images before processing.

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
- Staging now falls back to individual file staging when batch `git add` fails, so valid captures still reach the index.
- Screenshot discovery is case-insensitive, so files like `IMAGE.PNG` and `SHOT.JPG` are included.
- Config saves are crash-safe to avoid losing settings if the system crashes mid-save.
