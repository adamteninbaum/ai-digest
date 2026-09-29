"""Upload a file to Dropbox and print a shared link to it.

Optional. Usage: python3 dropbox_upload.py LOCAL_FILE [DROPBOX_FOLDER]   (default /daily_digest)

Reads DROPBOX_APP_KEY, DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN from the environment
(set on the cloud environment). A fresh short-lived access token is minted each run, so
nothing expires. Needs app scopes files.content.write, sharing.write, sharing.read.
"""
import json
import os
import sys

import requests


def access_token():
    try:
        key = os.environ["DROPBOX_APP_KEY"]
        secret = os.environ["DROPBOX_APP_SECRET"]
        refresh = os.environ["DROPBOX_REFRESH_TOKEN"]
    except KeyError as missing:
        sys.exit(f"Missing environment variable {missing}")
    resp = requests.post("https://api.dropboxapi.com/oauth2/token", timeout=30,
                         data={"grant_type": "refresh_token", "refresh_token": refresh},
                         auth=(key, secret))
    if not resp.ok:
        sys.exit(f"Token refresh failed: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


def upload(token, local, remote):
    with open(local, "rb") as fh:
        resp = requests.post("https://content.dropboxapi.com/2/files/upload", timeout=120, data=fh,
                             headers={"Authorization": f"Bearer {token}",
                                      "Content-Type": "application/octet-stream",
                                      "Dropbox-API-Arg": json.dumps({"path": remote, "mode": "overwrite", "mute": True})})
    if not resp.ok:
        sys.exit(f"Upload failed: {resp.status_code} {resp.text}")
    return resp.json()["path_display"]


def shared_link(token, path):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post("https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings",
                         headers=headers, json={"path": path}, timeout=30)
    if resp.ok:
        return resp.json()["url"]
    if "shared_link_already_exists" in resp.text:
        resp = requests.post("https://api.dropboxapi.com/2/sharing/list_shared_links",
                             headers=headers, json={"path": path, "direct_only": True}, timeout=30)
        if resp.ok and resp.json().get("links"):
            return resp.json()["links"][0]["url"]
    sys.exit(f"Shared link failed: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    local = sys.argv[1]
    folder = (sys.argv[2] if len(sys.argv) > 2 else "/daily_digest").rstrip("/")
    token = access_token()
    path = upload(token, local, f"{folder}/{os.path.basename(local)}")
    print(shared_link(token, path))
