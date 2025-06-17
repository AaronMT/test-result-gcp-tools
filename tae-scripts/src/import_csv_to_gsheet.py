import csv
import gspread
import json
import os


def authenticate_google_sheets():
    """
    Authenticates with Google Sheets using service account credentials from an environment variable.

    Returns:
        gspread.Client: An authorized gspread client.
    """
    # Retrieve the Service Account JSON from the environment variable
    creds_json = os.environ.get('GOOGLE_SHEETS_KEY')
    if not creds_json:
        raise Exception("Google Sheets credentials not found in environment variables.")

    # Parse the JSON credentials
    creds_dict = json.loads(creds_json)

    # Authenticate using gspread with the credentials dictionary
    client = gspread.service_account_from_dict(creds_dict)

    return client


def upload_csv_to_worksheet(csv_filename, sheet_title, spreadsheet_title):
    """
    Uploads a CSV file to the specified worksheet in a Google Spreadsheet.

    Args:
        csv_filename (str): Path to the CSV file.
        sheet_title (str): Title of the worksheet.
        spreadsheet_title (str): Title of the Google Spreadsheet.
    """
    client = authenticate_google_sheets()

    try:
        sheet = client.open(spreadsheet_title).worksheet(sheet_title)
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open(spreadsheet_title).add_worksheet(title=sheet_title, rows="1000", cols="25")

    
    # Read and upload CSV content
    with open(csv_filename, 'r', newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Update the worksheet with new data
    sheet.update('A1', rows)


if __name__ == "__main__":
    CSV_FILE = "test_summary.csv"
    SHEET_TITLE = "TAE Stats (Android)"
    SPREADSHEET_TITLE = "Fenix and Focus - Automated Flaky & Failure Tracking"

    upload_csv_to_worksheet(CSV_FILE, SHEET_TITLE, SPREADSHEET_TITLE)
