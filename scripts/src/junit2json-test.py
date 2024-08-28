import os
import subprocess


def convert_junit_to_json(input_files, output_file):
    # Run the junit2json command and capture the output
    command = ["junit2json", "-p"] + input_files
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error converting JUnit to JSON: {result.stderr}")
    else:
        # Write the output to the specified file
        with open(output_file, 'w') as f:
            f.write(result.stdout)
        print(f"Successfully converted JUnit to JSON: {output_file}")


if __name__ == "__main__":
    # Define the input JUnit files and the output JSON file
    input_files = ["FullJUnitReport.xml"]
    output_file = os.path.join(os.getcwd(), "output.json")

    # Convert the JUnit files to JSON
    convert_junit_to_json(input_files, output_file)
