### Fixed

* Handle missing git binary gracefully. When git is not installed, `is_git_repo()` returns `False` and staging is skipped instead of crashing with `FileNotFoundError`.
