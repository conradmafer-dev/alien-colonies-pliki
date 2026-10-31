"""Build a small author-side AAB delta by reusing unchanged ZIP local records.

The output is applied by the release's ApplyUpdateNN.java helper. It is not an
Android in-app executable updater. Both inputs must be original unsigned AABs.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile


def records(path):
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = sorted(archive.infolist(), key=lambda item: item.header_offset)
        end = archive.start_dir
    result = {}
    for index, entry in enumerate(entries):
        next_offset = entries[index + 1].header_offset if index + 1 < len(entries) else end
        result[entry.filename] = (entry.header_offset, next_offset, raw[entry.header_offset:next_offset])
    return raw, entries, end, result


def build(old_path, new_path, code):
    old, _, _, previous = records(old_path)
    new, entries, central, updated = records(new_path)
    out = io.BytesIO()
    if 10 <= code <= 99:
        magic = "ACZIPD" + str(code)
    elif 100 <= code <= 999:
        magic = "ACZIP" + str(code)
    else:
        raise ValueError("Delta release code must be between 10 and 999")
    out.write(magic.encode("ascii"))
    out.write(struct.pack(">Q", len(old)) + hashlib.sha256(old).digest())
    out.write(struct.pack(">Q", len(new)) + hashlib.sha256(new).digest())
    operations = []

    def literal(data):
        if data:
            out.write(b"\x01" + struct.pack(">I", len(data)) + data)
            operations.append({"literal": len(data)})

    literal(new[:entries[0].header_offset])
    for entry in entries:
        start, end, data = updated[entry.filename]
        before = previous.get(entry.filename)
        if before and before[2] == data:
            out.write(b"\x00" + struct.pack(">QQ", before[0], end - start))
            operations.append({"copy": end - start})
        else:
            literal(data)
    literal(new[central:])
    out.write(b"\xff")
    return gzip.compress(out.getvalue(), compresslevel=9, mtime=0), operations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--code", type=int, required=True)
    args = parser.parse_args()
    data, operations = build(args.old, args.new, args.code)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({"delta_sha256": hashlib.sha256(data).hexdigest(), "delta_size": len(data),
                      "copied_bytes": sum(item.get("copy", 0) for item in operations),
                      "literal_bytes": sum(item.get("literal", 0) for item in operations)}, indent=2))


if __name__ == "__main__":
    main()
