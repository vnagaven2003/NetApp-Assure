"""Verify the running container over HTTP using only Python's standard library."""

import json
import urllib.error
import urllib.request


def main():
    cases = [
        ("/health", 200, {"status": "ok"}),
        ("/devices", 200, [
            {"id": 1, "name": "r1", "platform": "FRR"},
            {"id": 2, "name": "r2", "platform": "FRR"},
        ]),
        ("/devices/1", 200, {"id": 1, "name": "r1", "platform": "FRR"}),
        ("/devices/999", 404, {"detail": "Device not found"}),
        ("/devices/abc", 422, None),
    ]
    for path, expected_status, expected_body in cases:
        try:
            response = urllib.request.urlopen(f"http://127.0.0.1:8000{path}", timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.status
            body = json.load(response)
        if status != expected_status:
            raise RuntimeError(f"{path}: expected {expected_status}, got {status}")
        if expected_body is not None and body != expected_body:
            raise RuntimeError(f"{path}: unexpected response body {body!r}")
        if expected_status == 422 and not body.get("detail"):
            raise RuntimeError(f"{path}: missing validation error details")
        print(f"PASS {path}: HTTP {status}")
    print("All 5 live API checks passed.")


if __name__ == "__main__":
    main()
