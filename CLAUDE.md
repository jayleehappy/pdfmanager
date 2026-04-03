# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

```bash
# Development (run directly)
python main.py

# Package (onedir mode — do NOT use onefile)
pyinstaller pdfmc.spec --clean -y

# Output: dist/pdfmc/pdfmc.exe (+ _internal/ directory)
```

## Architecture

```
src/
├── core/
│   ├── directory_scanner.py   # Scans dirs → TreeNode list, handles sort_order.ini
│   ├── tree_manager.py       # TreeItem data model + TreeManager (CRUD, drag-drop)
│   ├── pdf_merger.py         # Merge PDFs by tree, generate nested bookmarks
│   ├── pdf_splitter.py       # Split PDF by bookmarks → directory structure + outline.xml
│   └── xml_handler.py        # Import/export/validate XML bookmarks
└── ui/
    ├── main_window.py        # QSplitter layout: toolbar + tree + preview
    ├── tree_widget.py        # QTreeWidget, right-click menu, drag-drop
    └── preview_widget.py     # PDF preview via pypdfium2, zoom, page edit
```

## Key Design: Path Resolution for Virtual Nodes

Two node types exist:
- **Real nodes** — scanned from disk: `TreeItem.path` is the absolute file path
- **Virtual nodes** — created manually (bookmarks/folders): `TreeItem.path` is `""`

`TreeItem.resolve_path(work_dir)` reconstructs the full path for virtual nodes by walking the parent chain. This is the single most important method — it avoids duplicating path-building logic across merger, merger, validator, and preview code. Any change to how virtual paths are constructed must update `resolve_path()`.

## Key Design: Dual Tree Representation

Two parallel trees are kept in sync:
1. **QTreeWidget (UI)** — `FileTreeItem` wraps `TreeItem`, parent-child via Qt's model
2. **TreeManager.root_items (data)** — `TreeItem` objects with explicit `parent`/`children` references

`structure_changed` signal triggers sync. `get_current_structure()` rebuilds the data tree from UI. `_rebuild_tree_item()` does the reverse.

## Key Design: pypdf Outline Format

pypdf generates a flat+hybrid outline: `[DEST, LIST, DEST, LIST, ...]`. A `DEST` with `Count>0` is a directory; `Count==0` is a leaf. Page references are `IndirectObject` — compare via `.indirect_reference`, never by equality. Page ranges use left-closed right-open `[start, end)`.

## PyInstaller (onedir only)

**Onefile mode is broken** — `QFileDialog.getExistingDirectory` (SHBrowseForFolder/COM) silently fails in temp extraction directory. Always use onedir.

Critical bundling requirements:
- `rthook.py` must set `sys.path[0] = _internal` before any imports
- Both `pypdfium2/` and `pypdfium2_raw/` must be bundled as separate packages
- `vcruntime140_1.dll` is NOT in System32 — explicitly copy from Python install dir
- `PIL` must NOT be in `excludes` — pypdfium2 rendering depends on it
- `OleInitialize(None)` via `ole32.dll` is required for Windows COM dialogs

## Configuration

- `sort_order.ini` — module-level cached by `directory_scanner.py` at first load. Supports `[SortOrder]` (explicit priority) and `[DisplayNames]` (display alias).
- `config.py` — `DEFAULT_WORK_DIR`, `DEFAULT_OUTPUT_DIR`, window dimensions.
