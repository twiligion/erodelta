# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

import os
import json
import hashlib
import urllib.request
import subprocess
import shutil
from portage.sync.syncbase import SyncBase

USER_AGENT = "erodelta-portage-sync/1.0"


def get_file_sha256(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out_file:
        shutil.copyfileobj(resp, out_file)


class ErodeltaSync(SyncBase):
    def __init__(self):
        super().__init__("erodelta", "app-portage/portage-sync-erodelta")

    def exists(self, **kwargs):
        if kwargs:
            self._kwargs(kwargs)
        loc = getattr(self.repo, "location", None)
        return bool(loc and os.path.ismount(loc))

    def new(self, **kwargs):
        return self.sync(**kwargs)

    def sync(self, **kwargs):
        if kwargs:
            self._kwargs(kwargs)

        if not getattr(self, "repo", None) and "repo" in kwargs:
            self.repo = kwargs["repo"]

        if not self.repo:
            print("[erodelta] Fatal error: Repository context is missing")
            return (1, False)

        name = self.repo.name
        base_url = self.repo.sync_uri.rstrip("/")
        img_dir = "/var/cache/portage/erofs"
        
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(self.repo.location, exist_ok=True)

        current_img = f"{img_dir}/{name}.erofs"
        new_img = f"{img_dir}/{name}.erofs.new"
        delta_file = f"{img_dir}/{name}.vcdiff"

        try:
            manifest_url = f"{base_url}/manifest.json"
            req = urllib.request.Request(manifest_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req) as resp:
                manifest_data = json.loads(resp.read().decode())

            if name not in manifest_data:
                print(f"[{name}] Error: Repository not listed in manifest.json")
                return (1, False)

            manifest = manifest_data[name]
            target_sha = manifest["to_sha256"]
            current_sha = get_file_sha256(current_img)
            is_mounted = os.path.ismount(self.repo.location)

            if current_sha == target_sha and is_mounted:
                print(f"[{name}] Repo image is already up-to-date and mounted")
                return (0, True)

            if current_sha == target_sha and not is_mounted:
                print(f"[{name}] Repo image is up-to-date, mounting...")
                return self._mount_repo(name, current_img)

            applied_delta = False
            if manifest.get("has_delta") and current_sha == manifest.get("from_sha256"):
                print(f"[{name}] Delta match, downloading patch {name}.vcdiff...")
                download(f"{base_url}/{name}.vcdiff", delta_file)
                
                ret = subprocess.run(["xdelta3", "-d", "-s", current_img, delta_file, new_img])
                if os.path.exists(delta_file):
                    os.remove(delta_file)
                    
                if ret.returncode == 0:
                    applied_delta = True
                else:
                    print(f"[{name}] Warning: xdelta3 failed, falling back to full image")

            if not applied_delta:
                print(f"[{name}] Delta unavailable or outdated, downloading full {name}.erofs...")
                download(f"{base_url}/{name}.erofs", new_img)

            if get_file_sha256(new_img) != target_sha:
                print(f"[{name}] Checksum mismatch, corrupted download")
                if os.path.exists(new_img):
                    os.remove(new_img)
                return (1, False)

            os.replace(new_img, current_img)

            return self._mount_repo(name, current_img)

        except Exception as e:
            print(f"[{name}] Sync error: {e}")
            if os.path.exists(new_img):
                os.remove(new_img)
            if os.path.exists(delta_file):
                os.remove(delta_file)
            return (1, False)

    def _mount_repo(self, name, img_path):
        res = subprocess.run(
            ["systemctl", "restart", f"gentoo-repo@{name}.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if res.returncode == 0:
            print(f"[{name}] Successfully synced and mounted via gentoo-repo@{name}.service")
            return (0, True)

        subprocess.run(["umount", "-q", self.repo.location], stderr=subprocess.DEVNULL)
        mount_res = subprocess.run([
            "mount", "-t", "erofs", "-o", "ro,loop,nodev,noexec",
            img_path, self.repo.location
        ])
        if mount_res.returncode == 0:
            print(f"[{name}] Successfully synced and mounted via direct loop mount")
            return (0, True)

        print(f"[{name}] Failed to mount image to {self.repo.location}!")
        return (mount_res.returncode, False)
