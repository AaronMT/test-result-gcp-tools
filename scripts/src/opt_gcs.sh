#!/bin/bash

# Simplified and fast GCS copy using gcloud storage
# Replaces the "Copy JUnit reports from the last 24 hours from GCS" step

BUCKET_NAME="${{ secrets[matrix.project.bucket_name] }}"
DATE_PREFIX=$(date -u -d 'yesterday' +%Y-%m-%d)

mkdir -p junit_reports

echo "Starting fast gcloud storage copy for date prefix: $DATE_PREFIX"

# Use gcloud storage ls to get all directories for yesterday in one call
echo "Finding directories for $DATE_PREFIX..."
gcloud storage ls "gs://$BUCKET_NAME/${DATE_PREFIX}*/" > directories.txt 2>/dev/null

if [ ! -s directories.txt ]; then
    echo "No directories found for date $DATE_PREFIX"
    exit 0
fi

echo "Found $(wc -l < directories.txt) directories to check"

# Process each directory to find ones with both required files
valid_dirs=()
while IFS= read -r dir; do
    if [ -z "$dir" ]; then continue; fi
    
    echo "Checking: $dir"
    
    # Check if both files exist in parallel
    {
        gcloud storage ls "${dir}FullJUnitReport.xml" >/dev/null 2>&1 && echo "junit_ok"
        gcloud storage ls "${dir}matrix_ids.json" >/dev/null 2>&1 && echo "matrix_ok"
    } | {
        junit_found=false
        matrix_found=false
        while read -r result; do
            case $result in
                "junit_ok") junit_found=true ;;
                "matrix_ok") matrix_found=true ;;
            esac
        done
        
        if $junit_found && $matrix_found; then
            valid_dirs+=("$dir")
            echo "✓ Valid: $dir"
        else
            echo "✗ Missing files: $dir"
        fi
    }
done < directories.txt

# Clean up temp file
rm directories.txt

if [ ${#valid_dirs[@]} -eq 0 ]; then
    echo "No valid directories found with both FullJUnitReport.xml and matrix_ids.json"
    exit 0
fi

echo "Processing ${#valid_dirs[@]} valid directories..."

# Download all files in parallel using gcloud storage cp with parallel processing
for dir in "${valid_dirs[@]}"; do
    DIR_NAME=$(basename "$dir" | tr -d '/')
    
    echo "Processing: $DIR_NAME"
    
    # Download matrix_ids.json first to check matrixLabel
    LOCAL_MATRIX_FILE="./junit_reports/matrix_ids-${DIR_NAME}.json"
    
    if gcloud storage cp "${dir}matrix_ids.json" "$LOCAL_MATRIX_FILE" 2>/dev/null; then
        # Check matrixLabel and skip if 'try'
        if command -v jq >/dev/null 2>&1; then
            MATRIX_LABEL=$(jq -r 'to_entries | map(select(.value.clientDetails.matrixLabel == "try")) | first | .value.clientDetails.matrixLabel // empty' "$LOCAL_MATRIX_FILE" 2>/dev/null)
            if [ "$MATRIX_LABEL" = "try" ]; then
                echo "Skipping $DIR_NAME (matrixLabel = try)"
                rm -f "$LOCAL_MATRIX_FILE"
                continue
            fi
        fi
        
        # Download JUnit report
        DEST_FILE="./junit_reports/FullJUnitReport-${DIR_NAME}.xml"
        gcloud storage cp "${dir}FullJUnitReport.xml" "$DEST_FILE"
        echo "Downloaded: $DEST_FILE"
    else
        echo "Failed to download matrix_ids.json for $DIR_NAME"
    fi
done

echo "Fast gcloud storage copy completed"