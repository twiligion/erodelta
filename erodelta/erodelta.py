import os
import json
import hashlib
import urllib.request
import subprocess
from portage.sync.syncbase import SyncBase

def get_file_sha256(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def download(url, dest):
    urllib.request.urlretrieve(url, dest)

class ErodeltaSync(SyncBase):
    def __init__(self):
        super().__init__('erodelta', 'app-portage/portage-sync-erodelta')

    def sync(self, **kwargs):
        name = self.repo.name
        base_url = self.repo.sync_uri.rstrip('/')
        img_dir = "/var/lib/portage-images"
        os.makedirs(img_dir, exist_ok=True)

        current_img = f"{img_dir}/{name}.erofs"
        new_img = f"{img_dir}/{name}.erofs.new"
        delta_file = f"{img_dir}/{name}.vcdiff"

        try:
            manifest_url = f"{base_url}/manifest.json"
            req = urllib.request.urlopen(manifest_url)
            manifest = json.loads(req.read().decode())[name]

            target_sha = manifest['to_sha256']
            current_sha = get_file_sha256(current_img)

            if current_sha == target_sha:
                print(f"[{name}] Repo image is already up-to-date.")
                return (0, True)

            applied_delta = False
            if manifest.get('has_delta') and current_sha == manifest.get('from_sha256'):
                print(f"[{name}] Delta match, downloading patch {name}.vcdiff...")
                download(f"{base_url}/{name}.vcdiff", delta_file)
                ret = subprocess.run(["xdelta3", "-d", "-s", current_img, delta_file, new_img])
                if ret.returncode == 0:
                    applied_delta = True
                if os.path.exists(delta_file):
                    os.remove(delta_file)

            if not applied_delta:
                print(f"[{name}] Delta unavailable or outdated, downloading full {name}.erofs...")
                download(f"{base_url}/{name}.erofs", new_img)

            if get_file_sha256(new_img) != target_sha:
                print(f"[{name}] Checksum mismatch, corrupted download.")
                if os.path.exists(new_img):
                    os.remove(new_img)
                return (1, False)

            os.replace(new_img, current_img)

            os.makedirs(self.repo.location, exist_ok=True)
            res = subprocess.run(["mount", "-o", "remount", self.repo.location], stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                subprocess.run(["mount", "-o", "loop,ro", current_img, self.repo.location])

            print(f"[{name}] Successfully synced and mounted")
            return (0, True)

        except Exception as e:
            print(f"[{name}] Sync error: {e}")
            return (1, False)
