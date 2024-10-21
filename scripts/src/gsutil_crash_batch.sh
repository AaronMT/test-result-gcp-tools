#!/bin/bash

# Ensure GCS_BUCKET_NAME is set
if [ -z "$GCS_BUCKET_NAME" ]; then
    echo "Error: GCS_BUCKET_NAME is not set."
    exit 1
fi

# Set the date prefix to today's date
# Test: date_prefix="2024-09-25"
date_prefix=$(date -u -d 'yesterday' +%Y-%m-%d)

# Destination directory where files will be copied
DEST_DIR="crash_reports"

# Base GCS path
GCS_BASE="gs://${GCS_BUCKET_NAME}"

echo "Starting processing for date prefix: $date_prefix"
echo "Destination directory: $DEST_DIR"
echo "Base GCS path: $GCS_BASE"
echo
echo "Listing directories with prefix ${GCS_BASE}/${date_prefix}_*/"
directories=$(gsutil ls -d "${GCS_BASE}/${date_prefix}_*/" 2>/dev/null)

# Check if any directories were found
if [ -z "$directories" ]; then
    echo "No directories found with the date prefix $date_prefix."
    exit 0
fi

for dir in $directories; do
    echo "--------------------------------------------"
    echo "Processing directory: $dir"

    # Check if matrix_ids.json exists in this directory
    matrix_ids_json="${dir}matrix_ids.json"
    echo "Checking for matrix_ids.json at $matrix_ids_json"
    if gsutil -q stat "$matrix_ids_json"; then
        echo "Found matrix_ids.json in $dir"
    else
        echo "matrix_ids.json not found in $dir, skipping."
        continue  # Go to the next directory
    fi

    # Now check if minidump files exist under this directory
    minidumps_pattern="${dir}matrix_*/*/artifacts/sdcard/Android/data/org.mozilla.fenix.debug/minidumps/*.dmp"
    echo "Checking for minidump files at pattern: $minidumps_pattern"
    minidump_files=$(gsutil ls "$minidumps_pattern" 2>/dev/null)

    if [ -n "$minidump_files" ]; then
        echo "Found minidump files in $dir"
    else
        echo "No minidump files found in $dir, skipping."
        continue  # Go to the next directory
    fi

    # Both matrix_ids.json and minidump files exist; proceed to copy
    # Create a unique local directory for this date-prefix directory
    dir_name=$(basename "$dir" | tr -d '/')
    local_dir="${DEST_DIR}/${dir_name}"
    echo "Creating local directory: $local_dir"
    mkdir -p "$local_dir"

    # Copy matrix_ids.json to the local directory
    echo "Copying matrix_ids.json to $local_dir/"
    gsutil cp "$matrix_ids_json" "$local_dir/"

    # Copy minidump files to the local directory
    echo "Copying minidump files to $local_dir/"
    gsutil -m cp "$minidumps_pattern" "$local_dir/"
    echo "Minidump files copied successfully."

    echo
done

echo "Processing completed."
