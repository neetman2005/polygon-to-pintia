# Polygon → Pintia Test Data Converter

Converts test data from [Polygon](https://polygon.codeforces.com) Full packages into [Pintia (PTA)](https://pintia.cn) compatible format.

> ⚠️ **Currently Windows only.**

---

## 📖 Full Workflow

### Prerequisites: Exporting Problems from Polygon

1. Complete all problem editing on [Polygon](https://polygon.codeforces.com)
2. For each problem: **Create Package** → select **Full** → click **Continue**
3. On the download page, click **Windows** or **Linux** to download the package

> Downloaded packages are named `{problem}-{version}$windows.zip` or `{problem}-{version}$linux.zip`, where `version` is any positive integer and `problem` is the problem name.

### Steps: Converting with This Tool

1. Launch `PolygonToPintia.exe` (or **drag & drop** a zip file onto the window)
2. **Select** or **drag** a Polygon Full package into the window
3. The tool processes automatically and displays two types of results:
   - **📦 Test data archive** (`-tests-pintia.zip`)
   - **📝 Statement Markdown files** (`-english-problem.md` / `-chinese-problem.md`, etc.)
4. Each file has its own **📥 Download** and **🗑 Delete** button

### Follow-up: Uploading to Pintia

1. Log in to [Pintia](https://pintia.cn)
2. Upload the converted `-tests-pintia.zip` as test data
3. Paste the converted `.md` statement content into Pintia's problem description

---

## 🚀 Quick Start

### Option 1: Download exe (Recommended — no Python required)

1. Go to the [Releases](../../releases) page and download the latest `PolygonToPintia.exe`
2. Copy the exe to any folder and double-click to run
3. Drag a Polygon Full package into the window, or click the file selection button
4. Click **📥 Download** to save the converted result

### Option 2: Run from Source

```bash
git clone https://github.com/neetman2005/polygon-to-pintia.git
cd polygonToPintia
pip install -r requirements.txt
python main.py
```

## 📋 Features

| Feature | Description |
|---------|-------------|
| **Import** | Drag `.zip` files into the window, or use the file selection button |
| **Test Data Conversion** | Automatically finds the `tests/` folder and generates `-tests-pintia.zip` |
| **Statement Conversion** | Automatically finds `statements/*/problem.tex` and converts to Markdown `.md` |
| **Download** | Each file has its own download button (**copies**, temp file preserved) |
| **Delete** | Each file has its own delete button |

### Test Data Conversion Rules

- Input files `{id}` → `{id}.in` (Unix line endings, UTF-8)
- Output files `{id}.a` → `{id}.out` (Unix line endings, UTF-8)
- Output filename: `{original-name}-tests-pintia.zip`

### Statement Conversion Rules (LaTeX → Markdown)

| LaTeX | Markdown |
|-------|----------|
| `\textbf{...}` | `**...**` |
| `\textit{...}` / `\emph{...}` | `*...*` |
| `\texttt{...}` | `` `...` `` |
| `\text{...}` (outside math mode) | `**...**` |
| `\begin{itemize}...\end{itemize}` | `* ` unordered list |
| `\begin{enumerate}...\end{enumerate}` | `1. ` ordered list |
| `\section{...}` | `## ...` |
| `\subsection{...}` | `### ...` |
| `$...$` / `$$...$$` | preserved as-is |
| `\InputFile` | `### Input:` |
| `\OutputFile` | `### Output:` |
| `\Note` | `### Notes` |
| `\Examples` + `\exmpfile` | expanded as code blocks |

> LaTeX commands inside math mode (`$...$`) are preserved as-is.

- Statement filename: `{original-name}-{language}-problem.md`
- Temp files are stored in the `temp/` folder next to the exe

### Validation & Warnings

The tool automatically detects and reports:

| Check | Behavior |
|-------|----------|
| No `tests/` folder | ❌ Error, processing stopped |
| Filename doesn't match `{id}` or `{id}.a` pattern | ⚠️ Warning, file ignored |
| ID has only input or only output (orphaned) | ⚠️ Warning, existing side exported |
| IDs are non-contiguous, don't start at 1, or non-positive | ⚠️ Warning, processing continues |

### File Lifecycle

| Action | Files in `temp/` |
|--------|-----------------|
| Import new package | Previous **undownloaded** files auto-deleted; **downloaded** files kept |
| Download a file | **Copied** to chosen location, temp copy preserved |
| Delete a file | Temp file removed immediately |
| Close the app | Confirmation prompt, then **all** temp files are deleted |

## 📁 Project Structure

```
polygonToPintia/
├── main.py              # Entry point
├── app.py               # GUI (tkinter)
├── processor.py         # Core logic (test data + statements)
├── tex_converter.py     # LaTeX → Markdown conversion engine
├── requirements.txt     # Python dependencies
├── build.bat            # Build script (generates .exe)
├── LICENSE              # MIT License
└── temp/                # Runtime temp directory (gitignored, auto-created)
```

## 🔧 Building from Source

After modifying the code, rebuild the exe with:

```bash
pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --windowed --hidden-import tkinterdnd2 --name "PolygonToPintia" main.py
```

The output is at `dist/PolygonToPintia.exe`. Alternatively, double-click `build.bat`.

## ❓ FAQ

**Q: Drag & drop doesn't work?**  
A: Use the file selection button to load the package, or ensure `tkinterdnd2` is properly installed.

**Q: What encodings are supported?**  
A: Auto-detects UTF-8 (with/without BOM), GBK/GB2312/GB18030, Latin-1, etc. All output is UTF-8 with LF line endings.

**Q: The package isn't being recognized?**  
A: Make sure the package is a Polygon **Full Package** (Create package → Full → Download), not a Standard package.

**Q: The converted statement looks wrong?**  
A: This tool handles common LaTeX markup (bold, italic, lists, sections, etc.). Math formulas (`$...$`) are preserved — Pintia supports LaTeX math rendering. Report any unhandled LaTeX commands so they can be added.

**Q: The statement preview looks garbled?**  
A: The preview is reference-only; Markdown syntax is stripped for readability. Download the `.md` file and open it in any Markdown viewer (VS Code, Typora, etc.) for the full result.

**Q: Where are the temp files?**  
A: In the `temp/` folder next to the exe. They are automatically cleaned up when the app exits.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
