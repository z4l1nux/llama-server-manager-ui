# Llama Server Manager

Llama Server Manager is a complete Python-based graphical user interface (GUI) designed to easily manage and configure `llama.cpp` servers. It provides a user-friendly interface to configure parameters, download models, monitor server logs, and start/stop the server.

---

## Tech Stack & Prerequisites

*   **Language**: Python 3.x
*   **GUI Framework**: Tkinter (built-in for Python on Windows; usually needs a package install on Linux)
*   **Dependencies**: Uses only standard library modules (no `pip install` required!).

> [!TIP]
> **Automatic llama.cpp Downloader**: You do not need to manually clone and compile `llama.cpp` anymore. The application has a built-in button next to the binary path config field to automatically fetch, download, and extract the latest compatible pre-compiled official binary for your operating system and CPU architecture.

### Prerequisites

#### Windows
- **Python 3.x**: Ensure Python is installed from [python.org](https://www.python.org/downloads/). During installation, make sure to check the box **"Add Python to PATH"** and include **tcl/tk** (Tkinter) support (which is enabled by default).

#### Linux (Debian/Ubuntu)
- **Python 3.x**: Usually pre-installed.
- **Tkinter**: Install using your package manager if not present:
  ```bash
  sudo apt-get install python3-tk
  ```

#### macOS
- **Python 3.x**: Usually pre-installed or can be installed via Homebrew (`brew install python`) or the official package from python.org. Tkinter is included by default.

---

## Installation Guide

### Windows Installation

1. **Download / Copy Files**:
   Copy the following files into the **same folder** (e.g. a temporary folder in your Downloads or Desktop):
   - `llama_manager.py` (the application code)
   - `install.py` (the installation script)
   - `llama-manager.png` (optional icon file)

2. **Run Installer**:
   - Open Command Prompt (`cmd`) or PowerShell.
   - Navigate (`cd`) to the directory where you copied the files:
     ```cmd
     cd Downloads
     ```
   - Run the installer script:
     ```cmd
     python install.py
     ```

3. **What happens next**:
   - The installer creates a folder in `%APPDATA%/llama-manager` and copies the application files there.
   - It will automatically create a desktop shortcut named **Llama Server Manager** and a menu entry in your **Start Menu**.
   - You can delete the temporary folder with the installer files.

4. **Launch**:
   - Double-click the **Llama Server Manager** shortcut on your Desktop or search for it in your Start Menu.

---

### Linux Installation

1. **Locate Files**:
   Ensure `llama_manager.py`, `install.py`, and `llama-manager.png` are in the same folder.

2. **Run Installer**:
   - Open your terminal.
   - Navigate to the directory containing the files.
   - Run the installer script:
     ```bash
     python3 install.py
     ```

3. **What happens next**:
   - The script copies `llama_manager.py` to `~/.local/share/llama-manager/`.
   - It copies the icon to `~/.local/share/icons/llama-manager.png` if it exists.
   - It creates a desktop entry at `~/.local/share/applications/llama-manager.desktop` to integrate the application into your application launcher.

4. **Launch**:
   - Search for **Llama Server Manager** in your system's application launcher/menu or run:
     ```bash
     python3 ~/.local/share/llama-manager/llama_manager.py
     ```

---

### macOS Installation

1. **Locate Files**:
   Ensure `llama_manager.py`, `install.py`, and `llama-manager.png` are in the same folder.

2. **Run Installer**:
   - Open your terminal.
   - Navigate to the directory containing the files.
   - Run the installer script:
     ```bash
     python3 install.py
     ```

3. **What happens next**:
   - The script copies `llama_manager.py` to `~/Library/Application Support/llama-manager/`.
   - It creates an application bundle at `~/Applications/Llama Server Manager.app`.

4. **Launch**:
   - Double-click **Llama Server Manager.app** in your `~/Applications` folder.

---

## Key Features

- **Server Control**: Start and stop the `llama-server` background process.
- **Auto-Kill Ports**: Automatically terminates processes running on the specified port before starting the server.
- **Model Library**: View, load, copy path, and delete GGUF models directly inside your models folder.
- **Advanced Parameters**: Toggle GPU layers, context size, parallel slots, batch size, thread configuration, CPU/RAM locking, Continuous Batching, Flash Attention, speculative execution, and TurboQuant RoPE parameters.
- **Direct HuggingFace Downloads**: Input a Repository ID and file name (plus HuggingFace token for private models) to download GGUF models directly within the application.
- **Server Logs**: Real-time console log viewer with text color highlighting for commands, info logs, and errors.
