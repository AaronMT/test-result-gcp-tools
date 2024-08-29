curl -v -L -X POST 'http://$REPORT_PORTAL_API_ENDPOINT/api/v1/$REPORT_PORTAL_PROJECT_NAME/launch/import' \
-H 'Content-Type: multipart/form-data' \
-H 'Authorization: Bearer $REPORT_PORTAL_API_TOKEN' \
-F 'file=@$ZIP_FILE;type=application/x-zip-compressed' \
-F 'launchImportRq="{
  \"description\": \"ARM64-v8a\",
  \"mode\": \"DEFAULT\",
  \"name\": \"Fenix ARM64-v8a\",
  \"startTime\": \"2023-11-08T10:23:34.259Z\"
}";type=application/json'