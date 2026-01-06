# Claim Photo Editor - Development Guide

## Project Overview

Claim Photo Editor is a cross-platform desktop application for captioning photos and generating PDF contact sheets. It's built with Python and PySide6 (Qt for Python).

## Quick Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the application
claim-photo-editor

# Run tests
pytest

# Run tests with coverage
pytest --cov

# Run lints
ruff check src tests
ruff format --check src tests
mypy src

# Format code
ruff format src tests
ruff check --fix src tests

# Build macOS app
pyinstaller claim-photo-editor.spec
```

## Project Structure

```
claim-photo-editor/
├── src/
│   └── claim_photo_editor/
│       ├── __init__.py          # Package init with version
│       ├── main.py              # Application entry point
│       ├── app.py               # Main application window
│       ├── config.py            # Settings and configuration
│       ├── models/
│       │   ├── __init__.py
│       │   └── photo.py         # Photo model with EXIF handling
│       ├── views/
│       │   ├── __init__.py
│       │   ├── sidebar.py       # Folder navigation sidebar
│       │   ├── grid_view.py     # Photo grid view
│       │   ├── photo_view.py    # Full-screen photo view
│       │   └── settings_dialog.py # Settings dialog
│       ├── services/
│       │   ├── __init__.py
│       │   ├── pdf_generator.py # PDF contact sheet generation
│       │   └── updater.py       # Auto-update functionality
│       └── utils/
│           ├── __init__.py
│           └── exif.py          # EXIF metadata utilities
├── tests/
│   ├── conftest.py              # Pytest fixtures
│   ├── test_photo.py            # Photo model tests
│   ├── test_config.py           # Config tests
│   ├── test_pdf_generator.py    # PDF generation tests
│   ├── test_exif.py             # EXIF utility tests
│   └── test_updater.py          # Update checker tests
├── .github/
│   └── workflows/
│       ├── ci.yml               # CI pipeline for tests/lints
│       └── build.yml            # Build pipeline for releases
├── pyproject.toml               # Project configuration
├── claim-photo-editor.spec      # PyInstaller spec file
└── scripts/
    └── release.py               # Release automation script
```

## Architecture

### Core Components

1. **MainWindow (app.py)**: The main application window containing the sidebar and content area.

2. **Config (config.py)**: Handles persistent settings using QSettings, including:
   - Photos directory path
   - PDF settings (rows, columns, orientation, margins, font, DPI)

3. **Photo Model (models/photo.py)**: Represents a photo with:
   - File path and metadata
   - Caption (stored in EXIF UserComment field)
   - Timestamp extraction

4. **Views**:
   - **Sidebar**: Tree view of folders under "Estimate Photos"
   - **GridView**: Thumbnail grid with captions
   - **PhotoView**: Full-screen view with metadata and caption editing

5. **Services**:
   - **PDFGenerator**: Creates contact sheets using ReportLab
   - **Updater**: Checks GitHub releases for updates

### Data Flow

1. User selects photos directory → saved to QSettings
2. App scans "Estimate Photos" folder for subfolders
3. User selects folder → photos loaded into grid
4. User adds caption → saved to EXIF UserComment
5. User generates PDF → only captioned photos included
6. User saves PDF → prompted to move folder to "Completed"

### EXIF Caption Storage

Captions are stored in the EXIF UserComment field using piexif library. This allows:
- Captions to persist with the image file
- Compatibility with other photo management software
- No external database needed

## Key Dependencies

- **PySide6**: Qt bindings for Python (cross-platform UI)
- **Pillow**: Image processing
- **piexif**: EXIF metadata handling
- **reportlab**: PDF generation
- **requests**: HTTP client for update checks
- **packaging**: Version comparison for updates

## Testing

Tests use pytest with pytest-qt for Qt widget testing. Key test areas:

1. **Unit tests**: Photo model, config, EXIF utilities
2. **Integration tests**: PDF generation, update checking
3. **Widget tests**: UI components (where practical)

Run tests in CI without display using `QT_QPA_PLATFORM=offscreen`.

## Release Process

Use the release script to create new versions:

```bash
python scripts/release.py [major|minor|patch]
```

This will:
1. Bump version in `__init__.py`
2. Create git commit and tag
3. Push to trigger GitHub Actions build

## Settings Storage

Settings are stored using Qt's QSettings:
- macOS: `~/Library/Preferences/com.jamescurtin.claim-photo-editor.plist`
- Windows: Registry under `HKEY_CURRENT_USER\Software\jamescurtin\claim-photo-editor`
- Linux: `~/.config/jamescurtin/claim-photo-editor.conf`

## PDF Generation Details

Contact sheets are generated with:
- Configurable grid layout (default 2x2)
- Smart image rotation to maximize size
- Dynamic font sizing for long captions
- Optimized image compression for email
- Default 75 DPI for small file sizes
