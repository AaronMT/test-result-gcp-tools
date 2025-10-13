import os
import requests
import re
import json

OWNER = 'mozilla-firefox'
REPO = 'firefox'
BRANCH = 'autoland'
API_URL = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/mobile/android/fenix/app/src/androidTest/java/org/mozilla/fenix/ui?ref={BRANCH}'
HEADERS = {
    'Accept': 'application/vnd.github.v3+json',
}

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'token {GITHUB_TOKEN}'

def get_kotlin_test_files(path_url=API_URL):
    kotlin_files = []
    response = requests.get(path_url, headers=HEADERS)
    response.raise_for_status()
    items = response.json()

    for item in items:
        if item['type'] == 'file' and item['name'].endswith('.kt'):
            kotlin_files.append(item)
        elif item['type'] == 'dir':
            kotlin_files.extend(get_kotlin_test_files(item['url']))

    return kotlin_files


def extract_tests_from_file(file_info):
    file_response = requests.get(file_info['download_url'], headers=HEADERS)
    file_response.raise_for_status()
    content = file_response.text

    # Extract package name
    package_match = re.search(r'^\s*package\s+([\w\.]+)', content, re.MULTILINE)
    package_name = package_match.group(1) if package_match else 'unknown.package'

    # Extract class name
    class_match = re.search(r'^\s*(?:class|object)\s+(\w+)', content, re.MULTILINE)
    class_name = class_match.group(1) if class_match else 'UnknownClass'

    # Extract test methods annotated with @Test
    test_methods = []
    for match in re.finditer(r'@Test\s*(?:\n\s*@[^\n]+\s*)*\n\s*fun\s+(\w+)', content, re.MULTILINE):
        method_name = match.group(1)
        test_methods.append(method_name)

    return package_name, class_name, test_methods


def main():
    kotlin_files = get_kotlin_test_files(API_URL)
    tests = []

    for file_info in kotlin_files:
        package_name, class_name, test_methods = extract_tests_from_file(file_info)
        for method in test_methods:
            test_entry = f"MediumPhone.arm-34-en_US-portrait:{package_name}.{class_name}#{method}"
            tests.append(test_entry)

    output = {"tests": tests}

    with open("test_list.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"✅  Wrote {len(tests)} tests to test_list.json")


if __name__ == "__main__":
    main()