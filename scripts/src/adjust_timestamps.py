#!/usr/bin/env python3

import os
import glob
import datetime
import xml.etree.ElementTree as ET
import argparse


# Adjust timestamps in XML files to the current UTC time
def adjust_timestamps_in_xml_files(directory):
    # Get the current UTC time as the base time
    base_time_dt = datetime.datetime.utcnow()

    # Iterate over all XML files in the given directory
    for filepath in glob.glob(os.path.join(directory, '*.xml')):
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError:
            print(f"Warning: Could not parse XML file {filepath}. Skipping.")
            continue

        # Collect all elements with 'timestamp' attributes
        timestamped_elements = []

        # Include the root element if it has a 'timestamp' attribute
        if 'timestamp' in root.attrib:
            timestamped_elements.append(root)

        # Iterate over all elements to find those with 'timestamp' attributes
        for elem in root.iter():
            if 'timestamp' in elem.attrib:
                timestamped_elements.append(elem)

        # Adjust timestamps
        for elem in timestamped_elements:
            # Add 'Z' if missing and ensure the timestamp is in UTC format
            timestamp_str = elem.get('timestamp')
            if timestamp_str:
                # Add 'Z' if missing
                if not timestamp_str.endswith('Z'):
                    timestamp_str += 'Z'
                try:
                    # Parse the timestamp
                    timestamp_dt = datetime.datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%SZ')
                except ValueError:
                    # Handle timestamps with fractional seconds
                    try:
                        timestamp_dt = datetime.datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                    except ValueError:
                        print(f"Warning: Could not parse timestamp '{timestamp_str}' in file '{filepath}'. Skipping this timestamp.")
                        continue

                # If timestamp is earlier than the base time, adjust it
                if timestamp_dt < base_time_dt:
                    timestamp_dt = base_time_dt

                # Update the timestamp with 'Z' at the end
                elem.set('timestamp', timestamp_dt.strftime('%Y-%m-%dT%H:%M:%SZ'))
            else:
                # If no timestamp, set it to the base time
                elem.set('timestamp', base_time_dt.strftime('%Y-%m-%dT%H:%M:%SZ'))

        # Write the modified XML back to the file
        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        print(f"Adjusted timestamps in file: {filepath}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Adjust timestamps in XML files to the current UTC time.')
    parser.add_argument('directory', help='Directory containing XML files to adjust')

    args = parser.parse_args()

    directory = args.directory
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' does not exist.")
        exit(1)
    adjust_timestamps_in_xml_files(directory)
