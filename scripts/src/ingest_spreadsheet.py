import os
import glob
import csv
from junitparser import JUnitXml, Failure
from collections import defaultdict
from datetime import datetime
import gspread
import json


def aggregate_test_results(xml_directory):
    test_data = defaultdict(
        lambda: {"Total Runs": 0, "Flaky Runs": 0, "Failed Runs": 0}
    )

    xml_files = glob.glob(os.path.join(xml_directory, "*.xml"))

    for xml_file in xml_files:
        xml = JUnitXml.fromfile(xml_file)
        for suite in xml:
            for case in suite:
                test_name = case.name
                class_name = case.classname
                # Use a unique identifier for each test
                test_id = f"{class_name}.{test_name}"

                test_data[test_id]["Total Runs"] += 1

                flaky_attr = case._elem.get("flaky")
                failures = (
                    [r for r in case.result if isinstance(r, Failure)]
                    if case.result
                    else []
                )

                if flaky_attr == "true" and len(failures) == 1:
                    # This is a flaky test
                    test_data[test_id]["Flaky Runs"] += 1
                elif len(failures) > 1 and flaky_attr is None:
                    # This is a failed test
                    test_data[test_id]["Failed Runs"] += 1
                # Else, it's a passed test; no action needed

    return test_data


def calculate_rates(test_data):
    aggregated_results = []

    for test_id, data in test_data.items():
        class_name, test_name = test_id.rsplit(".", 1)
        total_runs = data["Total Runs"]
        flaky_runs = data["Flaky Runs"]
        failed_runs = data["Failed Runs"]

        flaky_rate = flaky_runs / total_runs if total_runs else 0
        failure_rate = failed_runs / total_runs if total_runs else 0

        aggregated_results.append(
            {
                "Class Name": class_name,
                "Test Name": test_name,
                "Total Runs": total_runs,
                "Flaky Runs": flaky_runs,
                "Failed Runs": failed_runs,
                "Flaky Rate": f"{flaky_rate:.2%}",
                "Failure Rate": f"{failure_rate:.2%}",
            }
        )

    return aggregated_results


def write_aggregated_results_to_csv(aggregated_results, filename):
    headers = [
        "Class Name",
        "Test Name",
        "Total Runs",
        "Flaky Runs",
        "Failed Runs",
        "Flaky Rate",
        "Failure Rate",
    ]

    with open(filename, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for result in aggregated_results:
            writer.writerow(result)


def calculate_overall_totals(aggregated_results):
    total_runs = sum(int(result["Total Runs"]) for result in aggregated_results)
    total_flaky_runs = sum(int(result["Flaky Runs"]) for result in aggregated_results)
    total_failed_runs = sum(int(result["Failed Runs"]) for result in aggregated_results)

    overall_flaky_rate = total_flaky_runs / total_runs if total_runs else 0
    overall_failure_rate = total_failed_runs / total_runs if total_runs else 0

    return {
        "Date": datetime.utcnow().strftime("%Y-%m-%d"),
        "Total Runs": total_runs,
        "Flaky Runs": total_flaky_runs,
        "Failed Runs": total_failed_runs,
        "Flaky Rate": f"{overall_flaky_rate:.2%}",
        "Failure Rate": f"{overall_failure_rate:.2%}",
    }


def write_daily_totals_to_csv(daily_totals, filename):
    headers = [
        "Date",
        "Total Runs",
        "Flaky Runs",
        "Failed Runs",
        "Flaky Rate",
        "Failure Rate",
    ]

    # Check if the CSV file exists
    file_exists = os.path.isfile(filename)

    with open(filename, mode="a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)

        # Write headers only if the file doesn't exist
        if not file_exists:
            writer.writeheader()

        # Write the daily totals
        writer.writerow(daily_totals)


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


def update_google_sheet_with_cumulative_data(client, csv_filename, project_name):
    """
    Updates the specified Google Sheet worksheet with cumulative data from the CSV file.
    Merges new test results with existing data without clearing the sheet.

    Args:
        client (gspread.Client): The authenticated gspread client.
        csv_filename (str): Path to the CSV file containing aggregated results.
        project_name (str): Name of the project (used to identify the correct worksheet).
    """
    # Define the sheet name for the project
    sheet_title = f"Aggregated Results - {project_name}"

    # Try to open the worksheet; if it doesn't exist, create it
    try:
        sheet = client.open("Fenix and Focus - Automated Flaky & Failure Tracking").worksheet(sheet_title)
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open("Fenix and Focus - Automated Flaky & Failure Tracking").add_worksheet(title=sheet_title, rows="1000", cols="7")

    # Check if the first row (headers) exists; if not, add them
    if not sheet.row_values(1):  # If the first row is empty, add headers
        headers = ["Class Name", "Test Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"]
        sheet.append_row(headers)

    # Read existing data from the sheet
    existing_records = sheet.get_all_records()
    existing_data = {}
    for idx, record in enumerate(existing_records, start=2):  # Start at row 2 because row 1 contains headers
        test_id = f"{record['Class Name']}.{record['Test Name']}"
        existing_data[test_id] = idx  # Store the row number for updating

    # Read data from CSV
    with open(csv_filename, mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        csv_data = list(reader)

    # Prepare batch updates and new rows for appending
    batch_updates = []
    new_rows = []

    for row in csv_data:
        test_id = f"{row['Class Name']}.{row['Test Name']}"
        new_total_runs = int(row["Total Runs"])
        new_flaky_runs = int(row["Flaky Runs"])
        new_failed_runs = int(row["Failed Runs"])

        if test_id in existing_data:
            # If the test already exists, update the existing row
            row_num = existing_data[test_id]
            # Retrieve current values from the sheet
            current_total_runs = int(existing_records[row_num - 2]["Total Runs"])
            current_flaky_runs = int(existing_records[row_num - 2]["Flaky Runs"])
            current_failed_runs = int(existing_records[row_num - 2]["Failed Runs"])

            # Calculate new cumulative values
            cumulative_total_runs = current_total_runs + new_total_runs
            cumulative_flaky_runs = current_flaky_runs + new_flaky_runs
            cumulative_failed_runs = current_failed_runs + new_failed_runs

            # Calculate rates
            flaky_rate = f"{cumulative_flaky_runs / cumulative_total_runs:.2%}" if cumulative_total_runs else "0.00%"
            failure_rate = f"{cumulative_failed_runs / cumulative_total_runs:.2%}" if cumulative_total_runs else "0.00%"

            # Prepare the updated row data
            updated_row = [
                row["Class Name"],
                row["Test Name"],
                cumulative_total_runs,
                cumulative_flaky_runs,
                cumulative_failed_runs,
                flaky_rate,
                failure_rate,
            ]

            # Queue the update for this row
            batch_updates.append({
                'range': f'A{row_num}:G{row_num}',  # Update the corresponding row
                'values': [updated_row]
            })
        else:
            # If the test doesn't exist, prepare a new row to be appended
            flaky_rate = f"{new_flaky_runs / new_total_runs:.2%}" if new_total_runs else "0.00%"
            failure_rate = f"{new_failed_runs / new_total_runs:.2%}" if new_total_runs else "0.00%"

            new_row = [
                row["Class Name"],
                row["Test Name"],
                new_total_runs,
                new_flaky_runs,
                new_failed_runs,
                flaky_rate,
                failure_rate,
            ]
            new_rows.append(new_row)

    # Execute batch updates for existing rows
    if batch_updates:
        sheet.batch_update(batch_updates)

    # Append new rows if there are any
    if new_rows:
        sheet.append_rows(new_rows, value_input_option='USER_ENTERED')


def update_daily_totals_sheet(client, daily_totals, sheet_name, project_name):
    # Open the worksheet for daily totals
    sheet = client.open("Fenix and Focus - Automated Flaky & Failure Tracking").worksheet(sheet_name)

    # Check if headers exist; if not, add them
    headers = [
        "Date",
        "Project Name",
        "Total Runs",
        "Flaky Runs",
        "Failed Runs",
        "Flaky Rate",
        "Failure Rate",
    ]
    if not sheet.row_values(1):
        sheet.append_row(headers)

    # Append the daily totals
    row_data = [
        daily_totals["Date"],
        project_name,
        daily_totals["Total Runs"],
        daily_totals["Flaky Runs"],
        daily_totals["Failed Runs"],
        daily_totals["Flaky Rate"],
        daily_totals["Failure Rate"],
    ]
    sheet.append_row(row_data)


if __name__ == "__main__":

    project_name = os.environ.get('PROJECT_NAME')
    if not project_name:
        raise Exception("PROJECT_NAME not found in environment variables.")

    xml_directory = "junit_reports"  # Directory containing the XML files
    test_data = aggregate_test_results(xml_directory)
    aggregated_results = calculate_rates(test_data)

    # Write per-test aggregated results to CSV
    output_csv = "aggregated_test_results.csv"
    write_aggregated_results_to_csv(aggregated_results, output_csv)

    # Calculate daily totals and write to CSV
    daily_totals = calculate_overall_totals(aggregated_results)
    daily_totals_csv = "daily_totals.csv"
    write_daily_totals_to_csv(daily_totals, daily_totals_csv)

    # Authenticate once and pass client to update functions
    client = authenticate_google_sheets()

    # Update Google Sheets with cumulative data
    update_google_sheet_with_cumulative_data(client, output_csv, project_name)
    update_daily_totals_sheet(client, daily_totals, "Daily Totals", project_name)

    print(
        f"Aggregated test results have been written to {output_csv}, daily totals written to {daily_totals_csv}, and Google Sheets updated with cumulative data."
    )
