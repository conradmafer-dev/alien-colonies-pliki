"""Replace compiled Godot scripts/textures and rebuild the Android sparse index.

Use after a Godot 4.5.1 code export. Preserve unchanged ZIP payloads for small
author update packages. Always run the Android sparse startup check afterward.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

from check_android_resource_index import check_bundle, index_location, rebuilt_index


def read_varint(data, position):
    value, shift = 0, 0
    while True:
        byte = data[position]
        position += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, position
        shift += 7
        if shift > 70:
            raise ValueError("Invalid protobuf varint")


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def parse(data):
    result, position = [], 0
    while position < len(data):
        key, position = read_varint(data, position)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, position = read_varint(data, position)
        elif wire == 2:
            length, position = read_varint(data, position)
            value = data[position:position + length]
            position += length
        elif wire in (1, 5):
            length = 8 if wire == 1 else 4
            value = data[position:position + length]
            position += length
        else:
            raise ValueError("Unsupported protobuf wire type")
        result.append([number, wire, value])
    return result


def encode(fields):
    return b"".join(varint(n << 3 | w) + (varint(v) if w == 0 else
        varint(len(v)) + v if w == 2 else v) for n, w, v in fields)


def field(fields, number, optional=False):
    matches = [item for item in fields if item[0] == number]
    if optional and not matches:
        return None
    if len(matches) != 1:
        raise ValueError("Missing or duplicate protobuf field " + str(number))
    return matches[0]


def update_manifest(data, old_code, new_code, old_name, new_name):
    node = parse(data)
    element = parse(field(node, 1)[2])
    changed = []
    for attribute in (item for item in element if item[0] == 4):
        values = parse(attribute[2])
        namespace = field(values, 1, True)
        name = field(values, 2)[2].decode()
        if not namespace or namespace[2] != b"http://schemas.android.com/apk/res/android":
            continue
        if name == "versionCode":
            raw = field(values, 3, True)
            if raw:
                assert raw[2] == str(old_code).encode()
                raw[2] = str(new_code).encode()
            item = parse(field(values, 6)[2])
            primitive = parse(field(item, 7)[2])
            code = field(primitive, 6, True) or field(primitive, 7)
            assert code[1] == 0 and code[2] == old_code
            code[2] = new_code
            field(item, 7)[2] = encode(primitive)
            field(values, 6)[2] = encode(item)
        elif name == "versionName":
            assert field(values, 3)[2] == old_name.encode()
            field(values, 3)[2] = new_name.encode()
            compiled = field(values, 6, True)
            if compiled:
                item = parse(compiled[2])
                value = field(item, 2, True) or field(item, 3)
                string = parse(value[2])
                assert field(string, 1)[2] == old_name.encode()
                field(string, 1)[2] = new_name.encode()
                value[2] = encode(string)
                compiled[2] = encode(item)
        else:
            continue
        changed.append(name)
        attribute[2] = encode(values)
    assert sorted(changed) == ["versionCode", "versionName"]
    field(node, 1)[2] = encode(element)
    return encode(node)


def replace_zip_entries(original, replacements):
    raw = original.read_bytes()
    with zipfile.ZipFile(original) as archive:
        entries = sorted(archive.infolist(), key=lambda item: item.header_offset)
        start = archive.start_dir
    offsets, replacement_central, locals_, position = {}, {}, [], 0
    for index, entry in enumerate(entries):
        end = entries[index + 1].header_offset if index + 1 < len(entries) else start
        offsets[entry.filename] = position
        if entry.filename in replacements:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", compression=entry.compress_type, compresslevel=6) as out:
                out.writestr(copy.copy(entry), replacements[entry.filename])
            data = stream.getvalue()
            with zipfile.ZipFile(io.BytesIO(data)) as out:
                central_start = out.start_dir
            local = data[:central_start]
            replacement_central[entry.filename] = data[central_start:-22]
        else:
            local = raw[entry.header_offset:end]
        locals_.append(local)
        position += len(local)
    central, cursor = [], start
    while raw[cursor:cursor + 4] == b"PK\x01\x02":
        name_length, extra_length, comment_length = struct.unpack_from("<HHH", raw, cursor + 28)
        length = 46 + name_length + extra_length + comment_length
        name = raw[cursor + 46:cursor + 46 + name_length].decode("utf-8")
        record = bytearray(replacement_central.get(name, raw[cursor:cursor + length]))
        struct.pack_into("<I", record, 42, offsets[name])
        central.append(bytes(record))
        cursor += length
    assert raw[cursor:cursor + 4] == b"PK\x05\x06"
    added = sorted(set(replacements) - set(offsets))
    for name in added:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
            out.writestr(name,replacements[name])
        data = stream.getvalue()
        with zipfile.ZipFile(io.BytesIO(data)) as out:
            central_start = out.start_dir
        record = bytearray(data[central_start:-22])
        struct.pack_into('<I',record,42,position)
        central.append(bytes(record))
        locals_.append(data[:central_start])
        position += central_start
    directory = b"".join(central)
    eocd = bytearray(raw[cursor:])
    struct.pack_into('<HH',eocd,8,len(entries)+len(added),len(entries)+len(added))
    struct.pack_into("<II", eocd, 12, len(directory), position)
    return b"".join(locals_) + directory + eocd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("compiled", type=Path)
    parser.add_argument("--resources", type=Path,
                        help="Optional tree of exported replacement resources at their exact res:// paths")
    parser.add_argument("--old-code", required=True, type=int)
    parser.add_argument("--new-code", required=True, type=int)
    parser.add_argument("--old-name", required=True)
    parser.add_argument("--new-name", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    scripts = sorted(args.compiled.glob("*.gdc"))
    if not scripts:
        raise ValueError("No compiled .gdc scripts found directly in: " + str(args.compiled)
                         + ". Pass the folder containing the compiled script files.")
    _, errors = check_bundle(args.old)
    if errors:
        raise ValueError("Input bundle has a stale Android index: " + str(errors))
    with zipfile.ZipFile(args.old) as archive:
        _, prefix = index_location(archive)
        changes = {"base/manifest/AndroidManifest.xml": update_manifest(
            archive.read("base/manifest/AndroidManifest.xml"), args.old_code,
            args.new_code, args.old_name, args.new_name)}
        for script in scripts:
            target = prefix + "client/scripts/" + script.name
            changes[target] = script.read_bytes()
        if args.resources:
            resources = sorted(path for path in args.resources.rglob('*') if path.is_file())
            if not resources:
                raise ValueError("No exported replacement resources in: " + str(args.resources))
            for resource in resources:
                relative = resource.relative_to(args.resources).as_posix()
                target = prefix + relative
                if relative == "project.binary" or relative == "assets.sparsepck":
                    raise ValueError("Android project settings and sparse index are rebuilt separately")
                changes[target] = resource.read_bytes()
        project = prefix + "project.binary"
        previous = archive.read(project)
        assert len(args.old_name.encode()) == len(args.new_name.encode())
        assert previous.count(args.old_name.encode()) == 1
        changes[project] = previous.replace(args.old_name.encode(), args.new_name.encode())
        index, data = rebuilt_index(archive, changes)
        changes[index] = data
    data = replace_zip_entries(args.old, changes)
    args.new.parent.mkdir(parents=True, exist_ok=True)
    args.new.write_bytes(data)
    with zipfile.ZipFile(args.new) as current, zipfile.ZipFile(args.old) as previous:
        assert current.testzip() is None and set(previous.namelist()) <= set(current.namelist())
        for name in current.namelist():
            if name in changes:
                assert current.read(name) == changes[name]
            else:
                assert current.getinfo(name).CRC == previous.getinfo(name).CRC
                assert current.getinfo(name).file_size == previous.getinfo(name).file_size
    count, errors = check_bundle(args.new)
    assert not errors, errors
    report = {"version_code":args.new_code, "version_name":args.new_name,
        "aab_sha":hashlib.sha256(data).hexdigest(), "aab_size":len(data),
        "basis_sha":hashlib.sha256(args.old.read_bytes()).hexdigest(),
        "changed_entries":list(changes), "sparse_records_verified":count, "zip_crc":"PASS"}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
