#!/bin/bash

if [ -z "$BUCKET_NAME" ]; then
    echo "Error: BUCKET_NAME environment variable is not set"
    exit 1
fi

DATE_PREFIX=$(date -u -d 'yesterday' +%Y-%m-%d)

mkdir -p junit_reports

echo "Starting fast gcloud storage copy for date prefix: $DATE_PREFIX"
echo "Using bucket: $BUCKET_NAME"

echo "Finding directories for $DATE_PREFIX..."
gcloud storage ls "gs://$BUCKET_NAME/${DATE_PREFIX}*/" > directories.txt 2>/dev/null

if [ ! -s directories.txt ]; then
    echo "No directories found for date $DATE_PREFIX"
    echo "Tried pattern: gs://$BUCKET_NAME/${DATE_PREFIX}*/"
    exit 0
fi

echo "Found $(wc -l < directories.txt) directories to check"

valid_dirs=()
while IFS= read -r dir; do
    if [ -z "$dir" ]; then continue; fi
    
    echo "Checking: $dir"
    
    # Check if both files exist
    junit_exists=false
    matrix_exists=false
    
    if gcloud storage ls "${dir}FullJUnitReport.xml" >/dev/null 2>&1; then
        junit_exists=true
    fi
    
    if gcloud storage ls "${dir}matrix_ids.json" >/dev/null 2>&1; then
        matrix_exists=true
    fi
    
    if $junit_exists && $matrix_exists; then
        valid_dirs+=("$dir")
        echo "✓ Valid: $dir"
    else
        echo "✗ Missing files: $dir (junit: $junit_exists, matrix: $matrix_exists)"
    fi
done < directories.txt

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