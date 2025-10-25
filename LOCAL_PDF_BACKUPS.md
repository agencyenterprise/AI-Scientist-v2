# Local PDF Backup System

## Overview

To prevent data loss from MinIO upload failures, all generated PDFs are now automatically saved to a local backup directory before/during upload to MinIO.

## Features

- ✅ **Automatic Backups**: Every PDF is saved locally in `local_pdf_backups/` before upload attempts
- ✅ **Safety Net**: If MinIO upload fails, you'll still have the PDF locally
- ✅ **Named by Run ID**: Files are saved as `{run_id}_{original_filename}.pdf` for easy identification
- ✅ **Archive Upload Protection**: Experiments won't be deleted if archive upload to MinIO fails

## Directory Structure

```
AI-Scientist-v2/
├── local_pdf_backups/           # Local PDF backup directory
│   ├── {run_id}_paper.pdf       # PDFs named by run ID
│   └── ...
├── cleanup_local_pdfs.sh        # Script to clean up backups
└── ...
```

## Cleanup Script

When storage starts filling up, use the cleanup script:

### Interactive Cleanup (with confirmation)
```bash
./cleanup_local_pdfs.sh
```

### Force Cleanup (no confirmation)
```bash
./cleanup_local_pdfs.sh --force
```

### Delete Old PDFs Only
```bash
# Delete PDFs older than 7 days
./cleanup_local_pdfs.sh --old 7

# Delete PDFs older than 30 days without confirmation
./cleanup_local_pdfs.sh --old 30 --force
```

### Get Help
```bash
./cleanup_local_pdfs.sh --help
```

## How It Works

### During Experiment Run

1. **PDF Generation**: LaTeX compiles `template.pdf`
2. **Local Backup**: PDF is copied to `local_pdf_backups/{run_id}_paper.pdf` ✅
3. **MinIO Upload**: Attempt to upload to MinIO
   - If successful: PDF is available in UI ✅
   - If failed: Local backup preserved, error message shown ⚠️

### During Archive Upload

1. **Archive Creation**: Experiment directory is compressed to `.tar.gz`
2. **MinIO Upload**: Attempt to upload archive
   - If successful: Local experiment directory is deleted ✅
   - If failed: Local experiment directory is kept ⚠️
3. **Safety**: No cleanup happens if upload fails

## Benefits

- **No More Lost PDFs**: Even if MinIO upload fails, PDFs are preserved locally
- **Easy Recovery**: Can manually upload PDFs from backup directory later
- **Storage Management**: Cleanup script makes it easy to free space when needed
- **Debugging**: Local copies help diagnose upload issues

## Storage Monitoring

To check backup directory size:

```bash
du -sh local_pdf_backups/
```

To count PDFs:

```bash
ls local_pdf_backups/*.pdf | wc -l
```

To list recent backups:

```bash
ls -lht local_pdf_backups/ | head -10
```

## Recovery

If you need to manually upload a PDF from the backup directory:

1. Find the PDF: `ls local_pdf_backups/ | grep {run_id}`
2. The PDF is already there and can be accessed directly
3. You can also trigger a writeup retry which will attempt to upload again

## Git Ignore

The `local_pdf_backups/` directory is added to `.gitignore` so local backups are never committed to the repository.

