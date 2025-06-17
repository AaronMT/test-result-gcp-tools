import json
import requests
from datetime import datetime
from datetime import UTC
from statistics import mean


def load_test_names(json_path):
    with open(json_path, "r") as f:
        config = json.load(f)
    return config.get("tests", [])


def fetch_history(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def ts_to_date(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%d")


def process_test(test_key, test_data):
    durations = []
    timestamps = []

    for item in test_data.get("items", []):
        time = item.get("time", {})
        duration = time.get("duration")
        start = time.get("start")
        if duration is not None and start is not None:
            durations.append(duration)
            timestamps.append(start)

    if not durations:
        return None

    avg_sec = round(mean(durations) / 1000, 2)
    min_date = ts_to_date(min(timestamps))
    max_date = ts_to_date(max(timestamps))
    return {
        "test": test_key,
        "average_duration_sec": avg_sec,
        "count": len(durations),
        "start_date": min_date,
        "end_date": max_date,
    }


def generate_summary(json_path, history_url, output_csv_path):
    test_names = load_test_names(json_path)
    history = fetch_history(history_url)

    results = []
    for name in test_names:
        for key in history:
            if key == name or name in key:
                summary = process_test(key, history[key])
                if summary:
                    results.append(summary)

    with open(output_csv_path, "w") as f:
        f.write("Test Name,Average Duration (s),N,Start Date,End Date\n")
        for r in results:
            f.write(
                f"{r['test']},{r['average_duration_sec']},{r['count']},{r['start_date']},{r['end_date']}\n"
            )

    print(f"✅ Wrote {len(results)} test summaries to {output_csv_path}")


if __name__ == "__main__":
    generate_summary(
        json_path="test_list.json",
        history_url="https://storage.googleapis.com/mobile-allure-test-reports/Fenix/allure-report/history/history.json",
        output_csv_path="test_summary.csv",
    )
