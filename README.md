# Windows Screenshot for Linux

`wslshot` is a CLI tool that fetches the most recent screenshot(s) from a shared directory with a Windows host, then copies it to a specified directory in a Linux VM.

<!-- TOC -->
## Table of Contents

1. [Features](#features)
1. [Installation](#installation)
    1. [Install with pip](#install-with-pip)
    1. [Install with pipx (recommended)](#install-with-pipx-recommended)
1. [Windows Configuration](#windows-configuration)
1. [Shared Folder Configuration](#shared-folder-configuration)
    1. [For WSL users](#for-wsl-users)
    1. [For Virtual Machine users](#for-virtual-machine-users)
1. [Configuration of `wslshot`](#configuration-of-wslshot)
1. [Fetching Screenshots](#fetching-screenshots)
1. [Integration in Vim](#integration-in-vim)
<!-- /TOC -->

## Features

* Set a default source directory for screenshots.
* Specify a custom source or destination directory per operation.
    * Or automatically detect `/assets/images/` or other typical folders for this use case.
* Fetch the most recent screenshot or specify a number of recent screenshots to fetch.
* Control automatic staging of screenshots when copied to a git repository.
* Set a default output format (Markdown, HTML, plain text of the Path) and specify a custom format per operation.

## Installation

Ensure you have Python 3.8 or later installed on your system.

### Install with pip

```bash
python3 -m pip install wslshot
```

### Install with pipx (recommended)

[`pipx`](https://pypi.org/project/pipx/) is an alternative package manager for Python applications. It allows you to install and run Python applications in isolated environments without having to configure anything yourself.

**First, install `pipx` if you haven't already**:

* On macOS and Linux:

  ```
  python3 -m pip install --user pipx
  ```

Alternatively, you can use your package manager (`brew`, `apt`, etc.).

* On Windows:

  ```
  py -m pip install --user pipx
  py -m pipx ensurepath
  ```

**Once `pipx` is installed, you can install `wslshot` using the following command**:

```
pipx install wslshot
```

## Windows Configuration

Before using `wslshot`, it's essential to configure the Windows Snipping Tool to save screenshots automatically. It should be the default behavior, but if that's not the case, here is how to enable the automatic save of screenshots in the Windows Snipping Tool:

1. Open the Snipping Tool.
1. Click on "Settings...".
1. Toggle the box that says "Automatically save screenshots".

## Shared Folder Configuration

For `wslshot` to fetch screenshots from your Windows host, you need to set up a shared directory between your Windows host and your Linux VM. 

### For WSL users

If you are using the Windows Subsystem for Linux (WSL), you can directly access your Windows file system from your WSL distro. The Windows `C:` drive, for example, can be found at `/mnt/c/` within your WSL environment. Therefore, you can directly use a folder on your Windows file system as the source directory for `wslshot`. 

### For Virtual Machine users

If you are using a different kind of virtual machine (like VirtualBox or VMware), you need to set up a shared folder. The process varies depending on your VM provider, but here are general steps:

1. Choose a folder on your Windows host to use as your screenshot folder. This should be the same folder where you configured your Snipping Tool to automatically save screenshots.
1. Go into your VM settings and locate the shared folders option. Add the chosen screenshot folder as a shared folder.
1. Depending on your VM settings, this folder will now be available at a certain path in your Linux environment. This is the path you should use as your source directory for `wslshot`.

Remember to consult your VM provider's documentation for specific instructions on how to set up shared folders.

## Configuration of `wslshot`

Before using `wslshot`, you may want to configure it to suit your needs. You can do this using the `config` command:

```bash
wslshot config --source /path/to/source --auto-stage-enabled True --output-format HTML
```

This command allows you to set various options:

* **`--source` or `-s`**: This option lets you specify the default source directory where `wslshot` will look for screenshots.

* **`--auto-stage-enabled`**: This option lets you control whether screenshots are automatically staged when copied to a git repository. By default, this option is set to `False`. If this option is set to `True`, any screenshot copied to a git repo will automatically be staged for commit.

* **`--output-format` or `-o`**: This option lets you set the default output format for the links to the screenshots that `wslshot` creates. The available formats are Markdown, HTML, and the plain text of the path (`plain_text`). If you do not set this option, `wslshot` will output links in Markdown format by default.

Remember, these are just the default settings. You can override these settings on a per-operation basis by providing the corresponding options when running the `wslshot` command.

## Fetching Screenshots

**Fetch screenshots with the `wslshot` command**:

```bash
wslshot
```

This will fetch the most recent screenshots from the source directory. If this command is ran inside a git repository, it will create the folder `/assets/images` (if it doesn't exist) and copy the screenshot to it.

**These are the folders automatically detected for the copy**:

* `/assets/img/`
* `/assets/images/`
* `/img/`
* `/images/`

**You can also choose a specific number of screenshots**:

```bash
wslshot [--source /custom/source] [--destination /custom/destination] [--count 3] [--output HTML]
```

This will fetch the three most recent screenshots from the source directory and copy them to the destination directory. You can specify a custom source or destination directory for this operation. You can also specify the number of recent screenshots to fetch (defaults to 1) and choose the output format for the operation, which overrides the default set in `config`.

## Integration in Vim

If `wslshot` is in your PATH (this is by default if you installed it with `pipx`), you can easily call it with a shebang command.

```vim
:.!wslshot
```

___

<https://github.com/sderev/wslshot>
