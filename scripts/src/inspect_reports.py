import junitparser
import os
import sys


# Inspect a JUnit report file and remove it if it is empty
def inspect_report(file_path):
    xml = junitparser.JUnitXml.fromfile(file_path)
    if not xml.testsuites or len(xml.testsuites) == 0:
        print(f"Removing empty report: {file_path}")
        os.remove(file_path)

# Main function to inspect all JUnit reports in a directory
if __name__ == "__main__":
    # Get the directory to inspect from command line arguments
    reports_dir = sys.argv[1]
    for root, dirs, files in os.walk(reports_dir):
        for file in files:
            if file.endswith(".xml"):
                inspect_report(os.path.join(root, file))
