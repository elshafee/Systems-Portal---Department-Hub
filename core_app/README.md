# ESSIC Office Document Numbering System — v1.0

A lightweight web application for generating sequential office document numbers
and inserting them into Word (.docx) templates.

## Quick Start (Windows)

### 1. Prerequisites
- Python 3.10+ installed → https://www.python.org/downloads/
- Run as normal user (no admin needed)

### 2. Install dependencies
Open a Command Prompt inside the project folder and run:

```
pip install -r requirements.txt
```

### 3. Run the application
```
python app.py
```

### 4. Open in browser
```
http://localhost:5000
```

---

## Document Number Format

```
Code No 0031 ESSIC 05-2026
```

- `0031` — zero-padded sequential number (resets every month)
- `ESSIC` — fixed office identifier
- `05-2026` — current month and year

---

## Template Placeholder

Add this text exactly in your Word document where the code should appear:

```
{{CODE_NUMBER}}
```

The system will replace it with the full formatted code while preserving
all fonts, logos, Arabic text, headers, footers, and layout.

---

## Folder Structure

```
project/
│
├── app.py              ← Flask application entry point
├── models.py           ← SQLAlchemy database models
├── requirements.txt    ← Python dependencies
├── documents.db        ← SQLite database (auto-created on first run)
│
├── uploads/            ← Stores original uploaded templates
├── generated/          ← Stores numbered output documents
│
├── templates/
│   ├── base.html       ← Shared layout (sidebar, nav, alerts)
│   ├── index.html      ← Upload page
│   ├── documents.html  ← Document history table
│   └── edit.html       ← Edit serial number page
│
├── static/             ← Static assets (CSS/JS if needed)
│
└── services/
    ├── numbering.py    ← Auto-increment logic, code formatter
    └── word_editor.py  ← Safe placeholder replacement in .docx files
```

---

## Features (v1)

- Upload `.docx` template files
- Auto-generate sequential document numbers per month/year
- Insert number into Word document (paragraphs, tables, headers, footers)
- View full document history with stats
- Download generated numbered documents
- Edit serial number and regenerate document
- Delete records and files
- Fully preserves Arabic text, logos, fonts, and document formatting

---

## Notes

- The database resets numbering automatically each month/year combination.
- Uploaded originals are kept in `uploads/` so editing remains possible.
- The app runs locally on port 5000; no internet connection required.
