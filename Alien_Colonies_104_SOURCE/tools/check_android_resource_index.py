"""Validate the Godot 4.5 sparse resource index in an exported Android AAB.

Android reads asset lengths from assets.sparsepck, not from the ZIP directory.
Run after every bundle mutation, before signing or publishing.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import zipfile


def records(data):
    if len(data) < 108 or data[:4] != b"GDPC":
        raise ValueError("Missing Godot pack header")
    version, = struct.unpack_from("<I", data, 4)
    flags, = struct.unpack_from("<I", data, 20)
    if version != 3 or not flags & 4:
        raise ValueError("Expected a Godot v3 sparse pack")
    directory, = struct.unpack_from("<Q", data, 32)
    count, = struct.unpack_from("<I", data, directory)
    cursor = directory + 4
    seen = set()
    result = []
    for _ in range(count):
        length, = struct.unpack_from("<I", data, cursor)
        cursor += 4
        if not 0 < length <= 4096 or cursor + length + 36 > len(data):
            raise ValueError("Invalid resource record")
        name = data[cursor:cursor + length].rstrip(b"\0").decode("utf-8")
        cursor += length
        offset, size = struct.unpack_from("<QQ", data, cursor)
        digest = data[cursor + 16:cursor + 32]
        if offset != 0 or name in seen:
            raise ValueError("Duplicate or non-sparse resource: " + name)
        seen.add(name)
        result.append((name, size, digest, cursor))
        cursor += 36
    if cursor != len(data):
        raise ValueError("Trailing or incomplete resource records")
    return result


def index_location(bundle):
    names = [n for n in bundle.namelist() if n.endswith("/assets/assets.sparsepck")]
    if len(names) != 1:
        raise ValueError("Expected exactly one Android resource index")
    return names[0], names[0].removesuffix("assets.sparsepck")


def rebuilt_index(bundle, replacements=None):
    replacements = replacements or {}
    name, prefix = index_location(bundle)
    original = bundle.read(name)
    directory, = struct.unpack_from('<Q', original, 32)
    entries = records(original)
    known = {entry[0] for entry in entries}
    added = sorted(path.removeprefix(prefix) for path in replacements
                   if path.startswith(prefix) and path != name and path.removeprefix(prefix) not in known)
    for relative in added:
        if relative.startswith('/') or any(part in ('', '.', '..') for part in relative.split('/')):
            raise ValueError('Invalid added resource path: ' + relative)
    data = bytearray(original[:directory])
    data.extend(struct.pack('<I',len(entries)+len(added)))
    for relative in [entry[0] for entry in entries] + added:
        path = prefix + relative
        content = replacements[path] if path in replacements else bundle.read(path)
        encoded = relative.encode('utf-8')
        encoded += b'\0' * ((-len(encoded)) % 4)
        data.extend(struct.pack('<I',len(encoded)) + encoded + struct.pack('<QQ',0,len(content)))
        data.extend(hashlib.md5(content).digest())
        old = next((entry for entry in entries if entry[0] == relative),None)
        data.extend(original[old[3]+32:old[3]+36] if old else struct.pack('<I',0))
    return name, bytes(data)


def check_bundle(path):
    with zipfile.ZipFile(path) as bundle:
        name, prefix = index_location(bundle)
        entries = records(bundle.read(name))
        errors = []
        for relative, size, digest, _ in entries:
            try:
                content = bundle.read(prefix + relative)
            except KeyError:
                errors.append(relative + ": missing")
                continue
            if len(content) != size or hashlib.md5(content).digest() != digest:
                errors.append(f"{relative}: stale index (size {size}, actual {len(content)})")
        return len(entries), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    count, errors = check_bundle(args.bundle)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: all {count} Android resource lengths and MD5 digests match")


if __name__ == "__main__":
    main()
