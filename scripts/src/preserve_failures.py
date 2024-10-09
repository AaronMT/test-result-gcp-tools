#!/usr/bin/env python3

import os
import sys
import xml.etree.ElementTree as ET


def has_failures(xml_file):
    """
    Check if the given JUnit XML file contains any failures or errors.
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Handle both 'testsuites' and 'testsuite' as root elements
        if root.tag == 'testsuites':
            testsuites = root.findall('testsuite')
        elif root.tag == 'testsuite':
            testsuites = [root]
        else:
            return False  # Not a valid JUnit XML file

        for testsuite in testsuites:
            # Check 'failures' and 'errors' attributes in 'testsuite'
            failures = int(testsuite.attrib.get('failures', '0'))
            errors = int(testsuite.attrib.get('errors', '0'))
            if failures > 0 or errors > 0:
                return True

            # Check each 'testcase' for 'failure' or 'error' elements
            for testcase in testsuite.findall('testcase'):
                if testcase.find('failure') is not None or testcase.find('error') is not None:
                    return True
        return False
    except ET.ParseError:
        print(f"Warning: Could not parse {xml_file}")
        return False
    except Exception as e:
        print(f"Error processing {xml_file}: {e}")
        return False


def main(directory):
    # Traverse the directory for XML files
    for root_dir, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.xml'):
                full_path = os.path.join(root_dir, file)
                if has_failures(full_path):
                    print(f"Preserving file with failures: {full_path}")
                else:
                    try:
                        os.remove(full_path)
                        print(f"Deleted file without failures: {full_path}")
                    except Exception as e:
                        print(f"Error deleting file {full_path}: {e}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 preserve_failed_junit_results.py <directory_with_xml_files>")
        sys.exit(1)
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' does not exist.")
        sys.exit(1)
    main(directory)
