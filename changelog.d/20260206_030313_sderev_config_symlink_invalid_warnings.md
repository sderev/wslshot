Fixed
-----
* Allowed `~/.config/wslshot/config.json` to be a symlink and kept writes on its target file.
* Changed screenshot discovery to validate newest candidates first, so stale invalid files no longer spam warnings on routine runs.
