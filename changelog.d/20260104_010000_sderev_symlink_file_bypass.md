Security
--------

* Fix symlink bypass inside source directory. When `--allow-symlinks` is false, symlinked files inside the source directory are now rejected, preventing unauthorized access to files outside the source.
