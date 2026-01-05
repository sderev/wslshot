### Security

* Fix symlink file bypass inside source directory (CWE-59). When `--allow-symlinks` is false, symlinked files inside the source directory are now rejected. Previously, `stat()` followed symlinks allowing external file access.
