"""Unpack a plugin zip and check it answers Flow Launcher's python_v2 handshake.

Usage: python scripts/smoke.py <plugin.zip>
"""
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main(zip_path: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        plugin_dir = Path(tmp) / "plugin"
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(plugin_dir)
        settings_dir = Path(tmp) / "settings"
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": [{"currentPluginMetadata": {"pluginSettingsDirectoryPath": str(settings_dir)}}]},
            {"jsonrpc": "2.0", "id": 2, "method": "query",
             "params": [{"search": "", "actionKeyword": "ma", "rawQuery": "ma "}, {"server_url": "", "token": ""}]},
            {"jsonrpc": "2.0", "id": 3, "method": "close", "params": []},
        ]
        stdin = "".join(json.dumps(request) + "\n" for request in requests)
        completed = subprocess.run([sys.executable, "run.py"], cwd=plugin_dir, input=stdin,
                                   capture_output=True, text=True, timeout=60)
    responses = {}
    for line in completed.stdout.splitlines():
        message = json.loads(line)
        responses[message.get("id")] = message
    query = responses.get(2, {}).get("result") or {}
    titles = [result.get("Title") for result in query.get("result") or []]
    if titles != ["Set up Music Assistant"]:
        print(completed.stdout, completed.stderr, sep="\n", file=sys.stderr)
        print(f"unexpected query result: {titles}", file=sys.stderr)
        return 1
    print("python_v2 handshake OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
