#!/bin/bash

# Ensure the file exists
if [ ! -f "$ZIP_FILE" ]; then
  echo "Error: File $ZIP_FILE not found."
  exit 1
fi

# Get the current date in the format YYYY-MM-DD
CURRENT_DATE=$(date +%Y-%m-%d)

# JSON payload
JSON_PAYLOAD=$(cat <<EOF
{
  "description": "GitHub Actions Import: All Architectures",
  "mode": "DEFAULT",
  "name": "${REPORT_PORTAL_PROJECT_NAME} for android"
}
EOF
)

# Execute the curl command and capture the output and exit status
response=$(curl -v -L "https://$REPORT_PORTAL_API_ENDPOINT/api/v1/$REPORT_PORTAL_PROJECT_NAME/launch/import" \
  -H "Authorization: Bearer $REPORT_PORTAL_API_TOKEN" \
  -F "file=@$ZIP_FILE;type=application/zip" \
  --form-string "launchImportRq=$JSON_PAYLOAD;type=application/json" 2>&1)

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
