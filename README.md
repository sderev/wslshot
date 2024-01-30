# Windows Screenshot for Linux

`wslshot` is a CLI tool designed to fetch the latest screenshot(s) from a shared directory with a Windows host, copy them to a designated directory in a Linux VM, and output their new Markdown-formatted paths.

Simply take a screenshot using the Windows Snipping tool (`win + shift + S`), and then run `wslshot` in your terminal to effortlessly transfer the image.

![demo_0](https://github.com/sderev/wslshot/assets/24412384/656b0595-0c27-41fa-966a-d6ca39ec410a)

<!-- TOC -->
## Table of Contents

1. [Features](#features)
1. [Installation](#installation)
    1. [Install with `pip`](#install-with-pip)
    1. [Install with `pipx` (Recommended)](#install-with-pipx-recommended)
1. [Windows Configuration](#windows-configuration)
1. [Shared Folder Configuration](#shared-folder-configuration)
    1. [For WSL Users](#for-wsl-users)
    1. [For Virtual Machine Users](#for-virtual-machine-users)
1. [Configuration of `wslshot`](#configuration-of-wslshot)
1. [Fetching Screenshots](#fetching-screenshots)
1. [Specifying an Image Path Instead of a Directory](#specifying-an-image-path-instead-of-a-directory)
    1. [Output](#output)
    1. [File Copy Behavior](#file-copy-behavior)
1. [Integration in Vim](#integration-in-vim)
<!-- /TOC -->

## Features

* Set a default source directory for screenshots.
* Designate a custom source or destination directory per operation.
  * Or automatically detect `/assets/images/` or other typical folders for this use case.
* Fetch the most recent screenshot or specify a number of recent screenshots to fetch.
* Control automatic staging of screenshots when copied to a git repository.
* Set a default output format (Markdown, HTML, plain text of the path) and specify a custom format per operation.

## Installation

Ensure you have Python 3.8 or later installed on your system.

### Install with `pip`

```bash
python3 -m pip install wslshot
```

### Install with `pipx` (Recommended)

```bash
pipx install wslshot
```

## Windows Configuration

Before using `wslshot`, it's essential to configure the Windows Snipping Tool to save screenshots automatically. It should be the default behavior; if it's not, here's how to enable automatic saving of screenshots in the Windows Snipping Tool:

1. Open the Snipping Tool.
1. Click on "Settings...".
1. Toggle the box that says "Automatically save screenshots".

## Shared Folder Configuration

For `wslshot` to fetch screenshots from your Windows host, you need to set up a shared directory between your Windows host and your Linux VM.

### For WSL Users

If you are using the Windows Subsystem for Linux (WSL), you can directly access your Windows file system from your WSL distro. The Windows `C:` drive, for example, can be found at `/mnt/c/` within your WSL environment. Therefore, you can directly use a folder on your Windows file system as the source directory for `wslshot`.

### For Virtual Machine Users

If you are using a traditional virtual machine managed by a hypervisor (e.g., VirtualBox, VMware, Hyper-V), you'll need to set up a shared folder with your Windows host and the Linux VM. The process varies depending on your VM provider, but here are general steps:

1. Choose a folder on your Windows host to use as your screenshot folder. This should be the same folder where you configured your Snipping Tool to automatically save screenshots.
1. Go into your VM settings and locate the shared folders option. Add the chosen screenshot folder as a shared folder.
1. Depending on your VM settings, this folder will now be available at a certain path in your Linux environment. Use this path as your source directory for `wslshot`.

Remember to consult your VM provider's documentation for specific instructions on how to set up shared folders.

## Configuration of `wslshot`

Before using `wslshot`, you may want to configure it to suit your needs. You can do this using the `configure` command:

```bash
wslshot configure --source /path/to/source --auto-stage-enabled True --output-format HTML
```

This command allows you to set various options:

* **`--source` or `-s`**: This option lets you specify the default source directory where `wslshot` will look for screenshots.

* **`--auto-stage-enabled`**: This option lets you control whether screenshots are automatically staged when copied to a git repository. By default, this option is set to `False`. If this option is set to `True`, any screenshot copied to a git repository will automatically be staged for commit.

* **`--output-format` or `-f`**: This option lets you set the default output format for the links to the screenshots that `wslshot` creates. The available formats are Markdown, HTML, and the plain text of the path (`plain_text`). If you do not set this option, `wslshot` will output links in Markdown format by default.

Remember, these are just the default settings. You can override these settings on a per-operation basis by providing the corresponding options when running the `wslshot` command.

## Fetching Screenshots

**Fetch screenshots with the `wslshot` command**:

```bash
wslshot
```

This will fetch the most recent screenshots from the source directory. If this command is run inside a git repository, it will create the folder `/assets/images` (if it doesn't exist) and copy the screenshot to it.

**These are the folders automatically detected for the copy**:

- `/assets/img/`
- `/assets/images/`
- `/img/`
- `/images/`

**You can also choose a specific number of screenshots**:

```bash
wslshot -n 3
```

This will fetch the three most recent screenshots.

**These are all the possible options**:

```bash
wslshot [--source /custom/source] [--destination /custom/destination] [--count 3] [--output-format HTML]
```

## Specifying an Image Path Instead of a Directory

To utilize this feature, provide the path to the image you'd like to copy as an argument when running the `wslshot` command:

```bash
wslshot /mnt/c/user/my_name/Images/magic.gif
```

Note that you can _drag and drop_ a file into the Windows Terminal to automatically populate its path.

### Output

Upon success, the command will output the new path of the image in Markdown format:

```bash
![magic.gif](/assets/images/animated_magic.gif)
```

### File Copy Behavior

As with the standard usage of `wslshot`, the specified image will be copied to your designated folder on the Linux VM.

## Integration in Vim

If `wslshot` is in your PATH (this is by default if you installed it with `pipx`), you can easily call it with a shebang command.

```vim
:.!wslshot
```

---

<https://github.com/sderev/wslshot>
