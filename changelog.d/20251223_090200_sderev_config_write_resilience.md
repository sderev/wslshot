Fixed
-----
* Make config write edge cases best-effort instead of failing. Directory `fsync` and `chmod` errors now log warnings rather than raising exceptions.
