import os
import glob
import csv
from junitparser import JUnitXml, Failure
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import gspread
import json
import random
import time

from gspread.exceptions import APIError


def with_retries(func, *args, retries=10, backoff=3, max_sleep=120, **kwargs):
    """
    Run a gspread operation with retries on quota (429) errors.
    Exponential backoff with jitter to spread out retries.
    
    Args:
        func: Function to execute
        retries: Maximum number of retry attempts (default: 10)
        backoff: Base backoff multiplier (default: 3)
        max_sleep: Maximum sleep time in seconds (default: 120)
    """
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            if "429" in str(e):
                if attempt == retries:
                    raise RuntimeError(f"Operation failed after {retries} retries due to quota errors")
                # Cap sleep time to avoid extremely long waits
                sleep_time = min(backoff ** attempt + random.uniform(0, 2), max_sleep)
                print(f"[Retry {attempt}/{retries}] Quota exceeded. Sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
            else:
                raise
    raise RuntimeError(f"Operation failed after {retries} retries due to quota errors")


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


def append_daily_per_test_issues_only(
    client,
    aggregated_results,
    project_name,
    run_date=None,
    sheet_title=None,
):
    """
    Appends one row per (class,test) with issues (flaky>0 or failed>0)
    into a per-project worksheet.

    Behavior:
    - Removes existing rows for the given date+project (avoid duplicates)
    - Keeps only the last 7 days of data (rolling window)
    """
    run_date = run_date or (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    sheet_title = sheet_title or f"Trending Results - {project_name}"
    keep_days = 7  # rolling window length

    ss = client.open("Fenix and Focus - Automated Flaky & Failure Tracking")

    try:
        ws = ss.worksheet(sheet_title)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=sheet_title, rows="1000", cols="7")
        ws.update("A1:G1", [[
            "date", "project_name", "class_name", "test_name",
            "total_runs", "flaky_runs", "failed_runs"
        ]])
        time.sleep(2)

    # Load all current rows
    values = with_retries(ws.get_all_values)  # includes header
    time.sleep(2)  # Increased pause after read

    # 1) Remove duplicates for today's date+project
    if len(values) > 1:
        to_delete_today = [
            idx for idx, row in enumerate(values[1:], start=2)
            if len(row) >= 2 and row[0] == run_date and row[1] == project_name
        ]
        # Delete in smaller chunks to reduce API load
        if to_delete_today:
            chunk_size = 5  # Reduced from 10
            for i in range(0, len(to_delete_today), chunk_size):
                chunk = to_delete_today[i:i + chunk_size]
                for r in reversed(chunk):
                    with_retries(lambda: ws.delete_rows(r))
                time.sleep(3)  # Increased pause after each chunk

    # Longer pause before next read operation
    time.sleep(3)

    # 2) Prune rows older than the 7-day window
    if len(values) > 1:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        values_after_dupe_check = with_retries(ws.get_all_values)  # after dupe deletion
        time.sleep(2)  # Brief pause after read
        values_after_dupe_check = values_after_dupe_check[1:]  # skip header

        to_delete_old = [
            idx for idx, row in enumerate(values_after_dupe_check, start=2)
            if len(row) >= 1 and row[0] < cutoff
        ]
        # Delete in smaller chunks
        if to_delete_old:
            chunk_size = 5  # Reduced from 10
            for i in range(0, len(to_delete_old), chunk_size):
                chunk = to_delete_old[i:i + chunk_size]
                for r in reversed(chunk):
                    with_retries(lambda: ws.delete_rows(r))
                time.sleep(3)  # Increased pause after each chunk

    # Longer pause before append operation
    time.sleep(3)

    # 3) Append today's issue rows
    out_rows = []
    for r in aggregated_results:
        flaky = int(r.get("Flaky Runs", 0))
        failed = int(r.get("Failed Runs", 0))
        if flaky > 0 or failed > 0:
            out_rows.append([
                run_date,
                project_name,
                r.get("Class Name", ""),
                r.get("Test Name", ""),
                int(r.get("Total Runs", 0)),
                flaky,
                failed,
            ])

    if out_rows:
        # Append in smaller chunks
        chunk_size = 50  # Reduced from larger batches
        for i in range(0, len(out_rows), chunk_size):
            chunk = out_rows[i:i + chunk_size]
            print(f"Appending chunk {i // chunk_size + 1} of {(len(out_rows) + chunk_size - 1) // chunk_size} ({len(chunk)} rows)")
            with_retries(lambda: ws.append_rows(chunk, value_input_option="USER_ENTERED"))
            time.sleep(3)  # Increased pause after write


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
        "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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
        time.sleep(2)

    # Check if the first row (headers) exists; if not, add them
    first_row = with_retries(lambda: sheet.row_values(1))
    if not first_row:  # If the first row is empty, add headers
        headers = ["Class Name", "Test Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"]
        with_retries(lambda: sheet.append_row(headers))
        time.sleep(2)

    # Read existing data from the sheet
    existing_records = with_retries(lambda: sheet.get_all_records())
    time.sleep(2)
    
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

    # Execute batch updates for existing rows in smaller chunks
    if batch_updates:
        chunk_size = 25  # Reduced from 50 to minimize quota pressure
        for i in range(0, len(batch_updates), chunk_size):
            chunk = batch_updates[i:i + chunk_size]
            print(f"Updating chunk {i // chunk_size + 1} of {(len(batch_updates) + chunk_size - 1) // chunk_size} ({len(chunk)} rows)")
            with_retries(lambda: sheet.batch_update(chunk))
            time.sleep(4)  # Increased from 2 seconds to 4 seconds

    # Append new rows if there are any, in smaller chunks
    if new_rows:
        chunk_size = 50  # Reduced from 100
        for i in range(0, len(new_rows), chunk_size):
            chunk = new_rows[i:i + chunk_size]
            print(f"Appending chunk {i // chunk_size + 1} of {(len(new_rows) + chunk_size - 1) // chunk_size} ({len(chunk)} rows)")
            with_retries(lambda: sheet.append_rows(chunk, value_input_option='USER_ENTERED'))
            time.sleep(4)  # Increased from 2 seconds to 4 seconds


def update_daily_totals_sheet(client, daily_totals, sheet_name, project_name):
    # Open the worksheet for daily totals
    sheet = client.open("Fenix and Focus - Automated Flaky & Failure Tracking").worksheet(sheet_name)
    time.sleep(2)  # Increased pause after opening the sheet

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

    first_row = with_retries(lambda: sheet.row_values(1))
    if not first_row:
        with_retries(lambda: sheet.append_row(headers))
        time.sleep(2)  # Increased pause after writing headers

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
    with_retries(lambda: sheet.append_row(row_data))
    time.sleep(2)


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

    # Append daily issues to the per-project worksheet
    run_date = os.environ.get("RUN_DATE") or (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        print(f"Updating trending sheet for {project_name}...")
        append_daily_per_test_issues_only(
            client=client,
            aggregated_results=aggregated_results,
            project_name=project_name,
            run_date=run_date,
            sheet_title=f"Trending Results - {project_name}",
        )
        print(f"Successfully updated trending sheet for {project_name}")
    except Exception as e:
        print(f"[Warning] Failed to update trending sheet for {project_name}: {e}")

    # Add longer delay between major operations
    time.sleep(5)

    # Update Google Sheets with cumulative data
    print(f"Updating cumulative data sheet for {project_name}...")
    update_google_sheet_with_cumulative_data(client, output_csv, project_name)
    print(f"Successfully updated cumulative data sheet for {project_name}")

    # Add longer delay between major operations
    time.sleep(5)

    print(f"Updating daily totals sheet for {project_name}...")
    update_daily_totals_sheet(client, daily_totals, "Daily Totals", project_name)
    print(f"Successfully updated daily totals sheet for {project_name}")

    print(
        f"Aggregated test results have been written to {output_csv}, daily totals written to {daily_totals_csv}, and Google Sheets updated with cumulative data."
    )