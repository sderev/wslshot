# Windows Screenshot for Linux

`wslshot` is a CLI tool designed to fetch the latest screenshot(s) from a directory shared with a Windows host, copy them to a designated directory in a Linux VM, and output their new Markdown-formatted paths.

Take a screenshot using the Windows Snipping tool (`win + shift + S`), then run `wslshot` in your terminal to transfer the image.

![demo](assets/images/demo.gif)

<!-- TOC -->
## Table of Contents

1. [Features](#features)
1. [Installation](#installation)
    1. [Install with `pip`](#install-with-pip)
    1. [Install with `uv`](#install-with-uv)
1. [Quick Start](#quick-start)
1. [Windows Configuration](#windows-configuration)
    1. [For Windows 11 Users](#for-windows-11-users)
    1. [For Windows 10 Users](#for-windows-10-users)
1. [Shared Directory Configuration](#shared-directory-configuration)
    1. [For WSL Users](#for-wsl-users)
    1. [For Virtual Machine Users](#for-virtual-machine-users)
1. [Configuration](#configuration)
1. [Fetching Screenshots](#fetching-screenshots)
1. [Using a Specific Image Path](#using-a-specific-image-path)
    1. [Output](#output)
    1. [File Copy Behavior](#file-copy-behavior)
1. [Vim Integration](#vim-integration)
<!-- /TOC -->

## Features

* Set a default source directory for screenshots.
* Designate a custom source or destination directory per operation, or let wslshot detect typical image directories automatically.
* Fetch the most recent screenshot or specify a number of recent screenshots to fetch.
* Print source paths without copying files using `--no-transfer`.
* Control automatic staging of screenshots when copied to a git repository.
* Convert screenshots to `png`, `jpg`/`jpeg`, `webp`, or `gif` during copy (flag or default).
* Optimize copied screenshots in place without changing filenames or extensions.
* Set a default output style (Markdown, HTML, text) and specify a custom style per operation.
* Migrate legacy config values with `migrate-config --dry-run`.

## Installation

Ensure you have Python 3.10 or later installed on your system.

### Install with `pip`

```bash
python3 -m pip install wslshot
```

### Install with `uv`

```bash
uv tool install wslshot
```

## Quick Start

This assumes your Windows screenshots are already saved in a directory your Linux environment can access.

```bash
wslshot configure --source /path --destination /path
wslshot
```

## Windows Configuration

Before using `wslshot`, you need to ensure that your screenshots are automatically saved to a directory accessible by your Linux environment.

### For Windows 11 Users

The Windows Snipping Tool in Windows 11 supports automatic saving of screenshots (it should be enabled by default):

1. Open the Snipping Tool.
1. Click on "Settings...".
1. Toggle the box that says "Automatically save screenshots".

### For Windows 10 Users

The Snipping Tool in Windows 10 doesn't support automatic saving. However, you can use the following methods to automatically save screenshots:

1. **Use `Win + PrtScn`**: It captures the entire screen and saves to `C:\Users\[Your Username]\Pictures\Screenshots`.
1. **Use `Win + Alt + PrtScn`**: It captures the active window and saves to `C:\Users\[Your Username]\Videos\Captures`.
    * To unify the save directory, right-click on the `Captures` directory, select **Properties**, and set your desired directory in the **Location** tab.
1. **Use a third-party tool**.

You can still use the Snipping Tool, but you'll need to manually save each screenshot after capturing it.

## Shared Directory Configuration

For `wslshot` to fetch screenshots from your Windows host, you need to set up a shared directory between your Windows host and your Linux VM.

### For WSL Users

If you are using the Windows Subsystem for Linux (WSL), you can directly access your Windows file system from your WSL distro. The Windows `C:` drive, for example, can be found at `/mnt/c/` within your WSL environment. Therefore, you can directly use a directory on your Windows file system as the source directory for `wslshot`.

### For Virtual Machine Users

If you are using a traditional virtual machine managed by a hypervisor (e.g., VirtualBox, VMware, Hyper-V), you'll need to set up a shared directory with your Windows host and the Linux VM. The process varies depending on your hypervisor, but here are general steps:

1. Choose a directory on your Windows host to use as your screenshot directory. This should be the same directory where you configured your Snipping Tool to automatically save screenshots.
1. Go into your VM settings and locate the shared directories option. Add the chosen screenshot directory as a shared directory.
1. Depending on your VM settings, this directory will now be available at a certain path in your Linux environment. Use this path as your source directory for `wslshot`.

Remember to consult the documentation of your hypervisor for specific instructions on how to set up shared directories.

## Configuration

Configure `wslshot` to suit your needs using the `configure` command:

```bash
wslshot configure [--source /path] [--destination /path] [--auto-stage-enabled True] [--output-style HTML] [--convert-to png]
```

This command allows you to set various options:

* **`--source` or `-s`**: This option lets you specify the default source directory where `wslshot` will look for screenshots.

* **`--destination` or `-d`**: This option lets you specify the default destination directory where `wslshot` will copy screenshots.

* **`--auto-stage-enabled`**: This option lets you control whether screenshots are automatically staged when copied to a git repository. By default, this option is set to `False`. If this option is set to `True`, any screenshot copied to a git repository will automatically be staged for commit.

* **`--output-style`**: This option lets you set the default output style for the links to the screenshots that `wslshot` creates. The available styles are Markdown, HTML, and text. If you do not set this option, `wslshot` will output links in Markdown format by default.

* **`--convert-to` or `-c`**: Set the default image conversion format. Supported formats: png, jpg, jpeg, webp, gif. Conversion runs after copying; the converted file replaces the copied original. `jpeg` is treated as `jpg`. A CLI `--convert-to` flag overrides this default.

These are default settings. Override them on a per-operation basis by providing the corresponding options when running the `wslshot` command.

Migrate older configuration keys to the current names with `migrate-config`:

```bash
wslshot migrate-config --dry-run
wslshot migrate-config
```

Use `--dry-run` to preview changes without writing the config file.

## Fetching Screenshots

**Fetch screenshots with the `wslshot` command**:

```bash
wslshot
```

This fetches the most recent screenshot from the source directory. If run inside a git repository, wslshot looks for an existing image directory (checked in priority order) and copies the screenshot there. If none exists, it creates `/assets/images/`.

**Directories checked in priority order**:

1. `/img/`
2. `/images/`
3. `/assets/img/`
4. `/assets/images/`

**You can also choose a specific number of screenshots**:

```bash
wslshot -n 3
```

This fetches the three most recent screenshots.

**Print source paths without copying files**:

```bash
wslshot --no-transfer
```

This prints the source paths for the selected screenshots without copying files or interacting with git. Output defaults to text; override with `--output-style`.

**Convert screenshots to a different format**:

```bash
wslshot --convert-to png
```

This converts the screenshot(s) to the specified format. Supported formats: png, jpg, jpeg, webp, gif. If a default conversion is set in configuration, it runs when no flag is provided. Conversion happens after copying, and the converted file replaces the copied original. If auto-staging is enabled in a git repository, only the converted file is staged. Conversion is skipped only when the copied file already has the target extension; `.jpeg` files are rewritten to `.jpg`. Conversion applies both to the latest-screenshot workflow and when you pass a specific image path.

**Optimize copied screenshots in place**:

```bash
wslshot --optimize
```

This optimizes copied screenshots after transfer and rewrites destination files in place. Source files are never modified. Optimization preserves each copied file's extension. If a default conversion format is configured, `--optimize` takes precedence for that run and skips conversion.

`--optimize` conflicts with `--no-transfer` and `--convert-to`.

**Allow symlinks (security risk)**:

```bash
wslshot --allow-symlinks
```

WARNING: Only use with trusted paths. By default, `wslshot` rejects symlinks for security.

**These are all the possible options**:

```bash
wslshot [--source /custom/source] [--destination /custom/destination] [--count 3] [--output-style HTML] [--no-transfer] [--convert-to png] [--optimize] [--allow-symlinks]
```

## Using a Specific Image Path

Provide the path to a specific image as an argument:

```bash
wslshot /mnt/c/user/my_name/Images/magic.gif
```

Note that you can _drag and drop_ a file into the Windows Terminal to automatically populate its path.

### Output

Upon success, the command outputs the new path in Markdown format:

```
![<uuid>.gif](/assets/images/<uuid>.gif)
```

### File Copy Behavior

The specified image is copied to your designated directory on the Linux VM.

## Vim Integration

If `wslshot` is in your PATH, call it with a filter command:

```vim
:.!wslshot
```

![vim demo](assets/images/demo-vim.gif)

---

<https://github.com/sderev/wslshot>
