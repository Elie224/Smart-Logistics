import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    train_url = os.getenv("TRAIN_URL", "").strip()
    token = os.getenv("ML_TRAIN_TOKEN", "").strip()

    if not train_url:
        print("TRAIN_URL is not set", file=sys.stderr)
        return 2
    if not token:
        print("ML_TRAIN_TOKEN is not set", file=sys.stderr)
        return 2

    req = urllib.request.Request(
        train_url,
        method="POST",
        headers={"X-Train-Token": token},
    )

    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(body)
        return 0
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTPError {exc.code}: {detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
