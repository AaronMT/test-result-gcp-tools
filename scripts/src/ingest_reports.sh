#!/bin/bash

# Ensure the file exists
if [ ! -f "$ZIP_FILE" ]; then
  echo "Error: File $ZIP_FILE not found."
  exit 1
fi

# Execute the curl command and capture the output and exit status
response=$(curl -v -L -X POST "http://$REPORT_PORTAL_API_ENDPOINT/api/v1/$REPORT_PORTAL_PROJECT_NAME/launch/import" \
-H "Content-Type: multipart/form-data" \
-H "Authorization: Bearer $REPORT_PORTAL_API_TOKEN" \
-F "file=@$ZIP_FILE;type=application/x-zip-compressed" \
-F 'launchImportRq={
  "description": "Github Actions import: ARM64-v8a",
  "mode": "DEFAULT",
  "name": "Fenix ARM64-v8a"
};type=application/json' 2>&1)

status=$?

# Check if the curl command was successful
if [ $status -ne 0 ]; then
  echo "Error: Failed to upload reports to ReportPortal."
  echo "Curl response:"
  echo "$response"  # Log the full response for debugging
  exit 1
else
  echo "Reports successfully uploaded to ReportPortal."
fi
