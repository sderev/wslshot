"""
Security tests for symlink following vulnerability (CWE-59, CVSS 9.1).

These tests verify that wslshot rejects symlinks in all vulnerable locations
to prevent attackers from exfiltrating sensitive files (SSH keys, credentials).
"""

import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import create_test_image

from wslshot.cli import configure, fetch, resolve_path_safely


class TestResolvePathSafely:
    """Unit tests for `resolve_path_safely()` function."""

    def test_accepts_normal_path(self, tmp_path):
        """Normal paths should be accepted and resolved."""
        test_dir = tmp_path / "screenshots"
        test_dir.mkdir()

        result = resolve_path_safely(str(test_dir))

        assert result == test_dir.resolve()
        assert result.is_absolute()

    def test_rejects_direct_symlink(self, tmp_path):
        """Direct symlinks should be rejected with clear error."""
        real_dir = tmp_path / "real_screenshots"
        real_dir.mkdir()

        symlink_dir = tmp_path / "symlink_screenshots"
        symlink_dir.symlink_to(real_dir)

        with pytest.raises(ValueError, match="Symlinks are not allowed"):
            resolve_path_safely(str(symlink_dir))

    def test_rejects_symlink_in_parent_chain(self, tmp_path):
        """Symlinks in parent directories should be rejected."""
        # Create real directory structure
        real_base = tmp_path / "real_base"
        real_base.mkdir()
        real_subdir = real_base / "subdir"
        real_subdir.mkdir()

        # Create symlink to base directory
        symlink_base = tmp_path / "symlink_base"
        symlink_base.symlink_to(real_base)

        # Try to access subdir through symlinked parent
        target_path = symlink_base / "subdir"

        with pytest.raises(ValueError, match="Path contains symlink"):
            resolve_path_safely(str(target_path))

    def test_allows_symlink_when_check_disabled(self, tmp_path):
        """Symlinks should be allowed when `check_symlink=False`."""
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()

        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.symlink_to(real_dir)

        # Should NOT raise when check is disabled
        result = resolve_path_safely(str(symlink_dir), check_symlink=False)

        assert result.exists()

    def test_expands_tilde_in_path(self, tmp_path, monkeypatch):
        """Tilde (~) should be expanded to home directory."""
        # Create a test directory in tmp_path to simulate home
        test_home = tmp_path / "test_home"
        test_home.mkdir()
        test_subdir = test_home / "screenshots"
        test_subdir.mkdir()

        # Mock Path.home() to return our test directory
        monkeypatch.setattr(Path, "home", lambda: test_home)

        # Use expanduser directly to handle the tilde
        result = resolve_path_safely(str(test_subdir))

        assert result == test_subdir.resolve()

    def test_raises_on_nonexistent_path(self, tmp_path):
        """`FileNotFoundError` should be raised for nonexistent paths."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError):
            resolve_path_safely(str(nonexistent))

    def test_handles_relative_paths(self, tmp_path):
        """Relative paths should be resolved to absolute paths."""
        test_dir = tmp_path / "screenshots"
        test_dir.mkdir()

        # Change to tmp_path and use relative path
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = resolve_path_safely("screenshots")

            assert result.is_absolute()
            assert result == test_dir.resolve()
        finally:
            os.chdir(original_cwd)


class TestFetchCommandSymlinkSecurity:
    """Integration tests for `fetch` command symlink security."""

    def test_rejects_symlink_source_directory(self, tmp_path, fake_home):
        """`fetch` command should reject symlink source directories."""
        runner = CliRunner()

        # Create real source and destination
        real_source = tmp_path / "real_source"
        real_source.mkdir()
        destination = tmp_path / "destination"
        destination.mkdir()

        # Create symlink to source
        symlink_source = tmp_path / "symlink_source"
        symlink_source.symlink_to(real_source)

        # Run fetch with symlink source
        result = runner.invoke(
            fetch,
            ["--source", str(symlink_source), "--destination", str(destination)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Symlinks are not allowed" in result.output

    def test_rejects_symlink_destination_directory(self, tmp_path, fake_home):
        """`fetch` command should reject symlink destination directories."""
        runner = CliRunner()

        # Create real directories
        source = tmp_path / "source"
        source.mkdir()
        real_destination = tmp_path / "real_destination"
        real_destination.mkdir()

        # Create symlink to destination
        symlink_destination = tmp_path / "symlink_destination"
        symlink_destination.symlink_to(real_destination)

        # Run fetch with symlink destination
        result = runner.invoke(
            fetch,
            ["--source", str(source), "--destination", str(symlink_destination)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Symlinks are not allowed" in result.output

    def test_rejects_symlink_as_direct_file_path(self, tmp_path, fake_home):
        """`fetch` should reject symlinks when using direct file path argument (CRITICAL GAP)."""
        runner = CliRunner()

        # Create real file and destination
        real_file = tmp_path / "real_screenshot.png"
        create_test_image(real_file)
        destination = tmp_path / "destination"
        destination.mkdir()

        # Create symlink to file
        symlink_file = tmp_path / "symlink_screenshot.png"
        symlink_file.symlink_to(real_file)

        # Run fetch with symlink as direct file path
        result = runner.invoke(
            fetch,
            ["--destination", str(destination), str(symlink_file)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Symlinks are not allowed" in result.output

    def test_rejects_symlinked_file_inside_source(self, tmp_path, fake_home):
        """`fetch` should reject symlinked files inside a real source directory."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        destination = tmp_path / "destination"
        destination.mkdir()

        real_file = source / "real.png"
        create_test_image(real_file)

        external_dir = tmp_path / "external"
        external_dir.mkdir()
        external_file = external_dir / "external.jpg"
        create_test_image(external_file)

        symlink_file = source / "newest.png"
        symlink_file.symlink_to(external_file)

        os.utime(real_file, (1, 1))
        os.utime(external_file, None)

        result = runner.invoke(
            fetch,
            ["--source", str(source), "--destination", str(destination), "--count", "1"],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

        copied_files = list(destination.iterdir())
        assert len(copied_files) == 1
        copied_bytes = copied_files[0].read_bytes()
        assert copied_bytes == real_file.read_bytes()
        assert copied_bytes != external_file.read_bytes()

    def test_rejects_symlink_in_image_path_parent(self, tmp_path, fake_home):
        """`fetch` should reject symlinks in parent directories of image_path (CRITICAL GAP)."""
        runner = CliRunner()

        # Create real directory structure with file
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        real_file = real_dir / "screenshot.png"
        create_test_image(real_file)
        destination = tmp_path / "destination"
        destination.mkdir()

        # Create symlink to parent directory
        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.symlink_to(real_dir)

        # Try to access file through symlinked parent
        target_file = symlink_dir / "screenshot.png"

        # Run fetch with file accessed through symlinked parent
        result = runner.invoke(
            fetch,
            ["--destination", str(destination), str(target_file)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Path contains symlink" in result.output

    def test_rejects_symlink_in_source_parent_chain(self, tmp_path, fake_home):
        """`fetch` should reject symlinks in source parent directory chain."""
        runner = CliRunner()

        # Create real directory structure
        real_base = tmp_path / "real_base"
        real_base.mkdir()
        real_source = real_base / "source"
        real_source.mkdir()
        destination = tmp_path / "destination"
        destination.mkdir()

        # Create symlink to base directory
        symlink_base = tmp_path / "symlink_base"
        symlink_base.symlink_to(real_base)

        # Try to access source through symlinked parent
        target_source = symlink_base / "source"

        # Run fetch
        result = runner.invoke(
            fetch,
            ["--source", str(target_source), "--destination", str(destination)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Path contains symlink" in result.output

    def test_rejects_symlink_in_destination_parent_chain(self, tmp_path, fake_home):
        """`fetch` should reject symlinks in destination parent directory chain."""
        runner = CliRunner()

        # Create real directory structure
        source = tmp_path / "source"
        source.mkdir()
        real_base = tmp_path / "real_base"
        real_base.mkdir()
        real_destination = real_base / "destination"
        real_destination.mkdir()

        # Create symlink to base directory
        symlink_base = tmp_path / "symlink_base"
        symlink_base.symlink_to(real_base)

        # Try to access destination through symlinked parent
        target_destination = symlink_base / "destination"

        # Run fetch
        result = runner.invoke(
            fetch,
            ["--source", str(source), "--destination", str(target_destination)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Path contains symlink" in result.output


class TestConfigureCommandSymlinkSecurity:
    """Integration tests for `configure` command symlink security."""

    def test_rejects_symlink_source(self, tmp_path):
        """`configure --source` should reject symlink source directories."""
        runner = CliRunner()

        # Create real source
        real_source = tmp_path / "real_source"
        real_source.mkdir()

        # Create symlink to source
        symlink_source = tmp_path / "symlink_source"
        symlink_source.symlink_to(real_source)

        # Run configure with symlink source
        result = runner.invoke(
            configure,
            ["--source", str(symlink_source)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Symlinks are not allowed" in result.output

    def test_rejects_symlink_destination(self, tmp_path):
        """`configure --destination` should reject symlink destination directories."""
        runner = CliRunner()

        # Create real destination
        real_destination = tmp_path / "real_destination"
        real_destination.mkdir()

        # Create symlink to destination
        symlink_destination = tmp_path / "symlink_destination"
        symlink_destination.symlink_to(real_destination)

        # Run configure with symlink destination
        result = runner.invoke(
            configure,
            ["--destination", str(symlink_destination)],
        )

        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Symlinks are not allowed" in result.output


class TestAttackScenarios:
    """Real-world attack scenario tests."""

    def test_cannot_exfiltrate_ssh_key_via_image_path(self, tmp_path, fake_home, monkeypatch):
        """Verify SSH key cannot be exfiltrated using `image_path` argument (CRITICAL)."""
        runner = CliRunner()

        # Create fake SSH key
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()
        fake_key = fake_ssh_dir / "id_rsa"
        fake_key.write_text("-----BEGIN PRIVATE KEY-----\nFAKE KEY DATA\n-----END PRIVATE KEY-----")

        # Create destination (simulating git repo)
        git_repo = tmp_path / "git_repo"
        git_repo.mkdir()

        # Attacker creates symlink disguised as PNG
        malicious_symlink = tmp_path / "fake_screenshot.png"
        malicious_symlink.symlink_to(fake_key)

        # Attempt attack
        result = runner.invoke(
            fetch,
            ["--destination", str(git_repo), str(malicious_symlink)],
        )

        # Verify attack is blocked
        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Symlinks are not allowed" in result.output

        # Verify SSH key was NOT copied to git repo
        copied_files = list(git_repo.iterdir())
        assert len(copied_files) == 0, "SSH key should not be copied"

    def test_cannot_exfiltrate_ssh_key_via_source_directory(self, tmp_path, fake_home):
        """Verify SSH key cannot be exfiltrated using source directory."""
        runner = CliRunner()

        # Create fake SSH directory
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()
        fake_key = fake_ssh_dir / "id_rsa"
        fake_key.write_text("-----BEGIN PRIVATE KEY-----\nFAKE KEY DATA\n-----END PRIVATE KEY-----")

        # Create destination (simulating git repo)
        git_repo = tmp_path / "git_repo"
        git_repo.mkdir()

        # Attacker creates symlink to .ssh directory
        malicious_symlink = tmp_path / "screenshots"
        malicious_symlink.symlink_to(fake_ssh_dir)

        # Attempt attack
        result = runner.invoke(
            fetch,
            ["--source", str(malicious_symlink), "--destination", str(git_repo)],
        )

        # Verify attack is blocked
        assert result.exit_code == 1
        assert "Security error" in result.output
        assert "Symlinks are not allowed" in result.output

    def test_cannot_exfiltrate_etc_passwd(self, tmp_path, fake_home):
        """Verify `/etc/passwd` cannot be exfiltrated using symlinks."""
        runner = CliRunner()

        # Create fake /etc/passwd
        fake_etc = tmp_path / "etc"
        fake_etc.mkdir()
        fake_passwd = fake_etc / "passwd"
        fake_passwd.write_text("root:x:0:0:root:/root:/bin/bash\n")

        # Create destination
        destination = tmp_path / "destination"
        destination.mkdir()

        # Attacker creates symlink disguised as image
        malicious_symlink = tmp_path / "screenshot.jpg"
        malicious_symlink.symlink_to(fake_passwd)

        # Attempt attack
        result = runner.invoke(
            fetch,
            ["--destination", str(destination), str(malicious_symlink)],
        )

        # Verify attack is blocked
        assert result.exit_code == 1
        assert "Security error" in result.output

        # Verify /etc/passwd was NOT copied
        copied_files = list(destination.iterdir())
        assert len(copied_files) == 0, "/etc/passwd should not be copied"


class TestAllowSymlinksFlag:
    """Tests for `--allow-symlinks` CLI flag."""

    def test_flag_allows_symlink_source(self, tmp_path, fake_home):
        """`--allow-symlinks` flag should allow symlink source directories."""
        runner = CliRunner()

        # Create real source with a file
        real_source = tmp_path / "real_source"
        real_source.mkdir()
        test_file = real_source / "test.png"
        create_test_image(test_file)

        # Create destination
        destination = tmp_path / "destination"
        destination.mkdir()

        # Create symlink to source
        symlink_source = tmp_path / "symlink_source"
        symlink_source.symlink_to(real_source)

        # Run fetch with --allow-symlinks
        result = runner.invoke(
            fetch,
            [
                "--source",
                str(symlink_source),
                "--destination",
                str(destination),
                "--allow-symlinks",
            ],
        )

        # Should succeed (exit code 0)
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Security error" not in result.output

    def test_flag_allows_symlink_destination(self, tmp_path, fake_home):
        """`--allow-symlinks` flag should allow symlink destination directories."""
        runner = CliRunner()

        # Create source with a file
        source = tmp_path / "source"
        source.mkdir()
        test_file = source / "test.png"
        create_test_image(test_file)

        # Create real destination
        real_destination = tmp_path / "real_destination"
        real_destination.mkdir()

        # Create symlink to destination
        symlink_destination = tmp_path / "symlink_destination"
        symlink_destination.symlink_to(real_destination)

        # Run fetch with --allow-symlinks
        result = runner.invoke(
            fetch,
            [
                "--source",
                str(source),
                "--destination",
                str(symlink_destination),
                "--allow-symlinks",
            ],
        )

        # Should succeed
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Security error" not in result.output

    def test_flag_allows_symlink_image_path(self, tmp_path, fake_home):
        """`--allow-symlinks` flag should allow symlink as direct file path."""
        runner = CliRunner()

        # Create real file
        real_file = tmp_path / "real_screenshot.png"
        create_test_image(real_file)

        # Create destination
        destination = tmp_path / "destination"
        destination.mkdir()

        # Create symlink to file
        symlink_file = tmp_path / "symlink_screenshot.png"
        symlink_file.symlink_to(real_file)

        # Run fetch with --allow-symlinks
        result = runner.invoke(
            fetch,
            ["--destination", str(destination), "--allow-symlinks", str(symlink_file)],
        )

        # Should succeed
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Security error" not in result.output

    def test_flag_allows_symlinked_file_inside_source(self, tmp_path, fake_home):
        """`--allow-symlinks` flag should allow symlinked files inside source directory."""
        runner = CliRunner()

        # Create source directory
        source = tmp_path / "source"
        source.mkdir()

        # Create external file
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        external_file = external_dir / "external.png"
        create_test_image(external_file)

        # Create symlink inside source pointing to external file
        symlink_file = source / "link.png"
        symlink_file.symlink_to(external_file)

        # Create destination
        destination = tmp_path / "destination"
        destination.mkdir()

        # Run fetch with --allow-symlinks
        result = runner.invoke(
            fetch,
            [
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--allow-symlinks",
            ],
        )

        # Should succeed and copy the symlinked file
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Security error" not in result.output
        assert "Skipping symlinked file" not in result.output
