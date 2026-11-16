#!/usr/bin/env python3
"""Download the Fun-CosyVoice3 weights used by VoiceSculptor Studio.

The launcher calls this script on first start when the model directory is
incomplete.  Files are downloaded to a .part file, checked against the
published size and SHA-256, then renamed into place.  Existing .part files are
resumed when the server supports HTTP Range requests.

Sources (tried in this order by default):
  modelscope   - ModelScope, usually the fastest choice in mainland China
  hf-mirror    - Hugging Face mirror, useful when huggingface.co is blocked
  huggingface  - Hugging Face for international users

Set VS_MODEL_SOURCE=modelscope|hf-mirror|huggingface to force a source.
"""

import argparse
import hashlib
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MODEL_ID = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"

FILES = (
    {
        "path": "llm.pt",
        "size": 2024669519,
        "sha256": "69f43bd545131c30e98947fb360ea8b4dc9916d8e83dded7757c7ea4f5a24970",
    },
    {
        "path": "flow.pt",
        "size": 1329116148,
        "sha256": "a6fab32a7825e5b0bc855ddd948f8db9370b0a786fbc249caa4595e95b608e4b",
    },
    {
        "path": "hift.pt",
        "size": 83202622,
        "sha256": "b279d7641eb97ae55b3b540cfba4f953c26492a2df758328a89a4d007ab87a65",
    },
    {
        "path": "campplus.onnx",
        "size": 28303423,
        "sha256": "a6ac6a63997761ae2997373e2ee1c47040854b4b759ea41ec48e4e42df0f4d73",
    },
    {
        "path": "speech_tokenizer_v3.onnx",
        "size": 969451503,
        "sha256": "23236a74175dbdda47afc66dbadd5bcb41303c467a57c261cb8539ad9db9208d",
    },
    {
        "path": "CosyVoice-BlankEN/model.safetensors",
        "size": 988097824,
        "sha256": "130282af0dfa9fe5840737cc49a0d339d06075f83c5a315c3372c9a0740d0b96",
    },
)

SOURCE_URLS = {
    "modelscope": "https://modelscope.cn/models/{model}/resolve/master/{path}",
    "hf-mirror": "https://hf-mirror.com/{model}/resolve/main/{path}",
    "huggingface": "https://huggingface.co/{model}/resolve/main/{path}",
}
SOURCE_ORDER = ("modelscope", "hf-mirror", "huggingface")
CHUNK = 1024 * 1024


def human_size(n):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024.0 or unit == "GiB":
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f GiB" % n


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def url_for(source, rel_path):
    safe_path = urllib.parse.quote(rel_path.replace("\\", "/"), safe="/")
    return SOURCE_URLS[source].format(model=MODEL_ID, path=safe_path)


def target_path(dest, rel_path):
    return os.path.join(dest, *rel_path.replace("\\", "/").split("/"))


def check_files(dest, selected, verify_hash=False):
    missing = []
    for item in selected:
        path = target_path(dest, item["path"])
        if not os.path.isfile(path):
            missing.append((item, "missing"))
        elif os.path.getsize(path) != item["size"]:
            missing.append((item, "size %d != %d" % (os.path.getsize(path), item["size"])))
        elif verify_hash and sha256_file(path) != item["sha256"]:
            missing.append((item, "SHA-256 mismatch"))
    return missing


def disk_has_room(dest, selected):
    need = 0
    for item in selected:
        path = target_path(dest, item["path"])
        part = path + ".part"
        if not os.path.isfile(path):
            need += item["size"]
            if os.path.isfile(part):
                need -= min(os.path.getsize(part), item["size"])
    if need <= 0:
        return True
    probe = dest
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    free = shutil.disk_usage(probe or ".").free
    if free < need + 512 * 1024 * 1024:
        print("[ERROR] Not enough disk space: need about %s, free %s"
              % (human_size(need + 512 * 1024 * 1024), human_size(free)))
        return False
    return True


def open_url(url, start=0):
    headers = {"User-Agent": "VoiceSculptor-model-downloader/1.0"}
    if start:
        headers["Range"] = "bytes=%d-" % start
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=60)


def download_one(dest, item, source):
    url = url_for(source, item["path"])
    path = target_path(dest, item["path"])
    part = path + ".part"
    expected = item["size"]
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.isfile(path) and os.path.getsize(path) == expected:
        print("[CHECK] %s (existing file)" % item["path"], flush=True)
        if sha256_file(path) == item["sha256"]:
            print("[SKIP] %s (already present)" % item["path"], flush=True)
            return
        print("[WARN] %s hash mismatch; re-downloading" % item["path"], flush=True)
        os.remove(path)

    start = os.path.getsize(part) if os.path.isfile(part) else 0
    if start > expected:
        os.remove(part)
        start = 0

    print("[GET ] %s (%s) from %s" % (item["path"], human_size(expected), source), flush=True)
    resp = None
    try:
        resp = open_url(url, start)
    except urllib.error.HTTPError as exc:
        if exc.code != 416 or start != expected:
            raise
    if resp is not None:
        try:
            status = getattr(resp, "status", 200)
            if start and status == 206:
                mode = "ab"
                total = start + int(resp.headers.get("Content-Length") or 0)
            else:
                if start:
                    print("  server ignored Range; restarting from byte 0", flush=True)
                start = 0
                mode = "wb"
                total = int(resp.headers.get("Content-Length") or expected)
            if total <= 0:
                total = expected
            done = start
            last = time.monotonic()
            with open(part, mode) as f:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    now = time.monotonic()
                    if now - last >= 0.5:
                        pct = min(100.0, done * 100.0 / total) if total else 0.0
                        print("\r  %5.1f%%  %s / %s" % (pct, human_size(done), human_size(total)),
                              end="", flush=True)
                        last = now
            print("\r  %5.1f%%  %s / %s" % (done * 100.0 / total if total else 0.0,
                                            human_size(done), human_size(total)), flush=True)
        finally:
            try:
                resp.close()
            except Exception:
                pass

    if not os.path.isfile(part) or os.path.getsize(part) != expected:
        actual = os.path.getsize(part) if os.path.isfile(part) else -1
        raise RuntimeError("size mismatch for %s: got %d, expected %d"
                           % (item["path"], actual, expected))
    print("  verifying SHA-256 ...", flush=True)
    actual_hash = sha256_file(part)
    if actual_hash != item["sha256"]:
        os.remove(part)
        raise RuntimeError("SHA-256 mismatch for %s: got %s, expected %s"
                           % (item["path"], actual_hash, item["sha256"]))
    os.replace(part, path)
    print("[OK  ] %s" % item["path"], flush=True)


def parse_args(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    default_dest = os.path.join(here, "engine", "CosyVoice", "pretrained_models",
                                "Fun-CosyVoice3-0.5B")
    parser = argparse.ArgumentParser(description="Download Fun-CosyVoice3 weights")
    parser.add_argument("--dest", default=default_dest,
                        help="model directory (default: %(default)s)")
    parser.add_argument("--source", default=os.environ.get("VS_MODEL_SOURCE", "auto"),
                        choices=("auto", "modelscope", "hf-mirror", "huggingface"),
                        help="download source (default: auto)")
    parser.add_argument("--only", action="append", default=[],
                        help="download only this relative path (repeatable)")
    parser.add_argument("--check", action="store_true",
                        help="only check that files exist with the expected size")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    selected = [f for f in FILES if not args.only or f["path"] in args.only]
    if not selected:
        print("[ERROR] --only did not match any known file", file=sys.stderr)
        return 1

    if args.check:
        missing = check_files(args.dest, selected, verify_hash=True)
        if missing:
            for item, reason in missing:
                print("[MISS] %s (%s)" % (item["path"], reason))
            return 1
        print("[OK] all selected model files are present with the expected size and SHA-256")
        return 0

    missing = check_files(args.dest, selected)
    for item, reason in missing:
        print("[MISS] %s (%s)" % (item["path"], reason))

    if not disk_has_room(args.dest, selected):
        return 2

    sources = SOURCE_ORDER if args.source == "auto" else (args.source,)
    os.makedirs(args.dest, exist_ok=True)
    failed = []
    for item in selected:
        last_error = None
        for source in sources:
            for attempt in (1, 2):
                try:
                    download_one(args.dest, item, source)
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - report and try next source
                    last_error = exc
                    print("\n[WARN] %s from %s failed (attempt %d): %s"
                          % (item["path"], source, attempt, exc), file=sys.stderr, flush=True)
                    time.sleep(1)
            if last_error is None:
                break
        if last_error is not None:
            failed.append((item["path"], last_error))

    if failed:
        print("\n[ERROR] model download incomplete:", file=sys.stderr)
        for path, exc in failed:
            print("  - %s: %s" % (path, exc), file=sys.stderr)
        print("Set VS_MODEL_SOURCE=modelscope|hf-mirror|huggingface to try one source, "
              "or set COSYVOICE_MODEL_DIR to an existing model directory.", file=sys.stderr)
        return 3
    print("\n[OK] model weights are ready in %s" % args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
