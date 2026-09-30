"""List Groq model IDs without displaying credentials or response headers."""
import os
import sys
import httpx


def main():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key or not key.isascii() or any(c.isspace() for c in key):
        print("Set and export a valid GROQ_API_KEY in this terminal first.")
        return 1
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.get("https://api.groq.com/openai/v1/models",
                                  headers={"Authorization": f"Bearer {key}"})
        if response.status_code != 200:
            print(f"Model listing failed: HTTP {response.status_code}.")
            return 1
        models = sorted(m["id"] for m in response.json()["data"] if isinstance(m.get("id"), str))
        print("Model IDs returned by Groq (not all support text/JSON or your account permissions):")
        for model in models:
            print(model)
        return 0
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        print("Could not retrieve the model list. Check Ubuntu connectivity and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
