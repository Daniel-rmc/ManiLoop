"""Fetch public archives listed in the pinned official registry; no credentials."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile

def main():
    PROJECT = Path(__file__).resolve().parents[1]
    ROOT = PROJECT / '.external/robocasa/robocasa/models/assets'
    LINKS = json.loads((ROOT / 'box_links/box_links_assets.json').read_text())
    TARGETS = [('textures', 'textures'), ('generative_textures', 'generative_textures'), ('fixtures_lightwheel', 'fixtures'),
               ('objects_lightwheel', 'objects/lightwheel'), ('objaverse', 'objects/objaverse')]
    OUT = PROJECT / '.runtime/robocasa-assets'
    OUT.mkdir(parents=True, exist_ok=True)
    for key, target in TARGETS:
        record = OUT / (key + '.json')
        if record.exists() and (ROOT / target).is_dir():
            print('ALREADY_VERIFIED', key, flush=True)
            continue
        link = LINKS[key]
        base, ident = link.rsplit('/s/', 1)
        url = base + '/shared/static/' + ident + '.zip'
        archive = OUT / (key + '.zip')
        digest = hashlib.sha256()
        print('DOWNLOAD', key, url, flush=True)
        started = last = time.monotonic()
        count = 0
        with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as stream:
            expected = int(response.headers.get('Content-Length') or 0)
            print('COMPRESSED_BYTES', key, expected, flush=True)
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
                digest.update(chunk)
                count += len(chunk)
                if time.monotonic() - last > 20:
                    print('DOWNLOADED_MIB', key, round(count / 2**20), flush=True)
                    last = time.monotonic()
                if shutil.disk_usage(OUT).free < 5 * 2**30:
                    raise RuntimeError('Stopping before exhausting disk; partial archive preserved')
            if expected and count != expected:
                raise RuntimeError('Incomplete archive; preserving partial download')
        destination = (ROOT / target).parent
        with zipfile.ZipFile(archive) as z:
            total = sum(member.file_size for member in z.infolist())
            if total + 5 * 2**30 > shutil.disk_usage(OUT).free:
                raise RuntimeError('Insufficient free disk for extraction; archive preserved')
            for member in z.infolist():
                path = (destination / member.filename).resolve()
                if not path.is_relative_to(destination):
                    raise ValueError('Unsafe archive member')
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Symlink in archive')
            print('EXTRACT', key, 'bytes', total, flush=True)
            z.extractall(destination)
        record.write_text(json.dumps({'key': key, 'source_url': url,
            'compressed_bytes': count, 'expanded_bytes': total,
            'archive_sha256': digest.hexdigest(), 'seconds': time.monotonic() - started,
            'destination': target}, indent=2))
        archive.unlink()  # Only the archive created by this script; extracted files remain.
        print('VERIFIED', key, count, 'bytes', flush=True)
    print('ASSETS_COMPLETE', flush=True)


if __name__ == "__main__":
    main()
