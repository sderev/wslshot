### Security

* **PERSO-194**: Fix path disclosure in error messages (CWE-209, CVSS 5.3). Error messages now sanitize filesystem paths to prevent attackers from probing usernames, directory structures, and system configuration. Paths displayed as `<...>/filename` to preserve user context while hiding sensitive information.
