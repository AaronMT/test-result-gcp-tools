#!/bin/bash

# Ensure the ZIP file exists
if [ ! -f "$ZIP_FILE" ]; then
  echo "Error: File $ZIP_FILE not found."
  exit 1
fi

# Get the current date in the format YYYY-MM-DD
CURRENT_DATE=$(date +%Y-%m-%d)

# Execute the curl command and capture the output and exit status
response=$(curl -v -L -X POST "https://$REPORT_PORTAL_API_ENDPOINT/api/v1/$REPORT_PORTAL_PROJECT_NAME/launch/import" \
  -H 'Content-Type: multipart/form-data' \
  -H "Authorization: Bearer $REPORT_PORTAL_API_TOKEN" \
  -F 'file=@'"$ZIP_FILE"';type=application/x-zip-compressed' \
  -F 'launchImportRq="{
    \"description\": \"GitHub Actions Import: All Architectures\",
    \"mode\": \"DEFAULT\",
    \"name\": \"'"${REPORT_PORTAL_PROJECT_NAME}"' for android\"
  }";type=application/json' 2>&1)

status=$?

# Check if the curl command was successful
if [ $status -ne 0 ]; then
  echo "Error: Failed to upload reports to Report Portal."
  echo "Curl response:"
  echo "$response"  # Log the full response for debugging
  exit 1
else
  echo "Reports successfully uploaded to Report Portal."
fi
