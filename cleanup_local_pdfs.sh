#!/bin/bash

# Script to clean up local PDF backups if storage becomes an issue
# Usage: 
#   ./cleanup_local_pdfs.sh            # Interactive mode - confirms before deletion
#   ./cleanup_local_pdfs.sh --force    # Force mode - deletes without confirmation
#   ./cleanup_local_pdfs.sh --old 7    # Delete PDFs older than 7 days

set -e

BACKUP_DIR="local_pdf_backups"
FORCE=false
DELETE_OLD=false
DAYS_OLD=0

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --force|-f)
      FORCE=true
      shift
      ;;
    --old|-o)
      DELETE_OLD=true
      DAYS_OLD="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Clean up local PDF backups to free up storage space."
      echo ""
      echo "Options:"
      echo "  --force, -f           Delete without confirmation"
      echo "  --old DAYS, -o DAYS   Delete only PDFs older than DAYS days"
      echo "  --help, -h            Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0                    # Interactive - confirms before deletion"
      echo "  $0 --force            # Delete all PDFs without confirmation"
      echo "  $0 --old 7            # Delete PDFs older than 7 days"
      echo "  $0 --old 30 --force   # Delete PDFs older than 30 days, no confirmation"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Check if backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
  echo "Backup directory '$BACKUP_DIR' does not exist."
  echo "No PDFs to clean up."
  exit 0
fi

# Count PDFs
if [ "$DELETE_OLD" = true ]; then
  PDF_COUNT=$(find "$BACKUP_DIR" -name "*.pdf" -type f -mtime +$DAYS_OLD 2>/dev/null | wc -l | tr -d ' ')
  PDF_SIZE=$(find "$BACKUP_DIR" -name "*.pdf" -type f -mtime +$DAYS_OLD -exec du -ch {} + 2>/dev/null | grep total | cut -f1 || echo "0")
else
  PDF_COUNT=$(find "$BACKUP_DIR" -name "*.pdf" -type f 2>/dev/null | wc -l | tr -d ' ')
  PDF_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "0")
fi

if [ "$PDF_COUNT" -eq 0 ]; then
  echo "No PDF files found to delete."
  exit 0
fi

# Show what will be deleted
echo "=========================================="
echo "Local PDF Backup Cleanup"
echo "=========================================="
echo ""
if [ "$DELETE_OLD" = true ]; then
  echo "PDFs to delete: $PDF_COUNT (older than $DAYS_OLD days)"
  echo "Disk space to free: ~$PDF_SIZE"
  echo ""
  echo "Files to be deleted:"
  find "$BACKUP_DIR" -name "*.pdf" -type f -mtime +$DAYS_OLD -exec ls -lh {} \; | awk '{print "  " $9 " (" $5 ")"}'
else
  echo "PDFs to delete: $PDF_COUNT"
  echo "Disk space to free: $PDF_SIZE"
  echo ""
  echo "Most recent PDFs:"
  find "$BACKUP_DIR" -name "*.pdf" -type f -exec ls -lt {} \; | head -5 | awk '{print "  " $9 " (" $5 ")"}'
  if [ "$PDF_COUNT" -gt 5 ]; then
    echo "  ... and $((PDF_COUNT - 5)) more"
  fi
fi
echo ""

# Confirm deletion unless force mode
if [ "$FORCE" = false ]; then
  read -p "Are you sure you want to delete these PDFs? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled. No files were deleted."
    exit 0
  fi
fi

# Delete PDFs
echo ""
echo "Deleting PDFs..."
if [ "$DELETE_OLD" = true ]; then
  find "$BACKUP_DIR" -name "*.pdf" -type f -mtime +$DAYS_OLD -delete
  echo "✓ Deleted $PDF_COUNT PDF(s) older than $DAYS_OLD days"
else
  rm -rf "$BACKUP_DIR"/*.pdf 2>/dev/null || true
  echo "✓ Deleted $PDF_COUNT PDF(s)"
fi

echo "✓ Freed up ~$PDF_SIZE of disk space"
echo ""
echo "Done!"

