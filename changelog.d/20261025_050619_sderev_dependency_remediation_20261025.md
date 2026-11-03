Security
--------
* Updated Pillow to 13.0.0, urllib3 to 2.8.0, and certifi to 2026.10.19 in `uv.lock`, and raised the Pillow and urllib3 minimum versions to these patched releases. This addresses 58 Dependabot alerts.

Removed
-------
* Dropped support for Python 3.10, which reached end of life in October 2026. Pillow 13.0.0, the first release to fix 41 of these alerts, requires Python 3.11 or later.
