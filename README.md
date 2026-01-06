# Claim Photo Editor

A desktop application for captioning photos and generating PDF contact sheets.

## Features

- Browse and navigate photo folders
- View photos in grid or full-screen mode
- Add captions to photos (stored in EXIF metadata)
- Filter photos by captioned/uncaptioned status
- Generate customizable PDF contact sheets
- Automatic updates from GitHub releases

## Installation

### From Release

Download the latest release for your platform from the [Releases](https://github.com/jamescurtin/claim-photo-editor/releases) page.

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/jamescurtin/claim-photo-editor.git
   cd claim-photo-editor
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. Run the application:
   ```bash
   claim-photo-editor
   ```

## Development

### Running Tests

```bash
pytest
```

### Running Lints

```bash
ruff check src tests
ruff format --check src tests
mypy src
```

### Building the Application

```bash
pip install pyinstaller
pyinstaller claim-photo-editor.spec
```

## Usage

1. Use the sidebar to navigate between folders.

2. Click on photos to view them in full-screen mode.

3. Add captions by clicking on a photo and entering text in the caption field.

4. Use the filter dropdown to show all, captioned, or uncaptioned photos.

5. Click "Generate PDF" to create a contact sheet of captioned photos.

6. After saving the PDF, optionally move the folder to "Completed Photos".

## Settings

Access settings via the Settings menu to customize:

- PDF layout (rows, columns)
- Page orientation (portrait/landscape)
- Margins
- Font
- Image resolution and DPI
