from google.cloud import storage
from datetime import datetime
import os


def list_blobs_with_prefix(bucket_name, prefix, delimiter=None):
    """Lists all the blobs in the bucket that begin with the prefix."""
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter=delimiter)

    return blobs


def download_files(bucket_name, source_blob_names, destination_folder):
    # Initialize the GCS client
    client = storage.Client()

    # Get the bucket
    bucket = client.bucket(bucket_name)

    for source_blob_name in source_blob_names:
        # Get the blob
        blob = bucket.blob(source_blob_name)

        # Create the destination file path
        destination_file_path = os.path.join(destination_folder, os.path.basename(source_blob_name))

        # Download the blob to the destination file
        blob.download_to_filename(destination_file_path)
        print(f"Downloaded {source_blob_name} to {destination_file_path}")


def main():
    bucket_name = "aaronmt-moz-tools-test"
    report_filename = "FullJUnitReport.xml"
    destination_folder = os.getcwd()
    num_directories = 5

    # Create the destination folder with current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    destination_folder = os.path.join(os.getcwd(), "reports", current_date)
    os.makedirs(destination_folder, exist_ok=True)

    # List all objects with detailed metadata
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)

    # Filter blobs to get directories and their creation times
    directories = {}
    files = []
    for blob in blobs:
        if blob.name.endswith('/'):
            directories[blob.name] = blob.time_created
        elif blob.name.endswith(report_filename):
            files.append(blob)

    if directories:
        # Sort directories by creation time (newest first) and take the latest num_directories
        sorted_directories = sorted(directories.items(), key=lambda x: x[1], reverse=True)[:num_directories]

        # Iterate over the newest directories and check for the report file
        for directory, _ in sorted_directories:
            # List files in the directory
            blobs_in_directory = list_blobs_with_prefix(bucket_name, directory)

            for blob in blobs_in_directory:
                if blob.name.endswith(report_filename):
                    # Download the report file
                    download_files(bucket_name, [blob.name], destination_folder)
    else:
        # If no directories found, look for the newest FullJUnitReport.xml in the root
        if files:
            # Sort files by creation time (newest first)
            newest_file = sorted(files, key=lambda x: x.time_created, reverse=True)[0]
            # Download the newest report file
            download_files(bucket_name, [newest_file.name], destination_folder)
        else:
            print("No directories found and no FullJUnitReport.xml in the root directory.")


if __name__ == "__main__":
    main()
