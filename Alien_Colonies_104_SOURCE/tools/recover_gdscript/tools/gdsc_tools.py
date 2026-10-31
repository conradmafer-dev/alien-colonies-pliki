#!/usr/bin/env python3
"""Read Godot 4.5.1 GDSC101 tokenizer buffers; compare token meaning and layout.

Format matches godotengine/godot 4.5.1-stable
modules/gdscript/gdscript_tokenizer_buffer.cpp. No decompilation or evaluation.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
import zstandard


def require(condition, message):
    if not condition:
        raise ValueError(message)


def variant(data, offset):
    start = offset
    header = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    kind, wide = header & 0xffff, bool(header & 0x10000)
    if kind == 0:
        value = None
    elif kind in (1, 2):
        value = struct.unpack_from('<q' if wide else '<i', data, offset)[0]
        offset += 8 if wide else 4
    elif kind == 3:
        number = struct.unpack_from('<d' if wide else '<f', data, offset)[0]
        value = number.hex() if math.isfinite(number) else str(number)
        offset += 8 if wide else 4
    elif kind in (4, 21):
        length = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        value = data[offset:offset + length].decode('utf8')
        offset += (length + 3) & ~3
    else:
        raise ValueError('Unsupported tokenizer constant Variant %s at %s' % (kind, start))
    require(offset <= len(data), 'Truncated Variant')
    return (kind, value), offset


def parse(data):
    require(data[:4] == b'GDSC' and len(data) >= 12, 'Not a GDSC buffer')
    version, size = struct.unpack_from('<II', data, 4)
    require(version == 101, 'Expected tokenizer version101')
    raw = zstandard.ZstdDecompressor().decompress(data[12:], max_output_size=size) if size else data[12:]
    require(not size or len(raw) == size, 'Incorrect GDSC size')
    ni, nc, nl, nt = struct.unpack_from('<4I', raw)
    offset = 16
    identifiers, constants = [], []
    for _ in range(ni):
        length = struct.unpack_from('<I', raw, offset)[0]
        offset += 4
        require(offset + length * 4 <= len(raw), 'Truncated identifier')
        identifiers.append(bytes(x ^ 0xb6 for x in raw[offset:offset + length * 4]).decode('utf-32-le'))
        offset += length * 4
    for _ in range(nc):
        item, offset = variant(raw, offset)
        constants.append(item)
    maps = []
    for _ in range(2):
        mapping = {}
        for _ in range(nl):
            index, value = struct.unpack_from('<II', raw, offset)
            offset += 8
            require(index not in mapping and index < nt, 'Invalid line-map entry')
            mapping[index] = value
        maps.append(mapping)
    require(set(maps[0]) == set(maps[1]), 'Line and column maps differ')
    canonical, raw_tokens = [], []
    for _ in range(nt):
        wide = bool(raw[offset] & 0x80)
        value = struct.unpack_from('<I', raw, offset)[0] if wide else raw[offset]
        offset += 4 if wide else 1
        line = struct.unpack_from('<I', raw, offset)[0]
        offset += 4
        kind, index = value & 0x7f, value >> 8
        if kind in (1, 2):
            require(index < len(identifiers), 'Identifier token out of range')
            item = (kind, identifiers[index])
        elif kind == 3:
            require(index < len(constants), 'Constant token out of range')
            item = (kind, constants[index])
        else:
            item = (kind,)
        canonical.append(item)
        raw_tokens.append((kind, index, line))
    require(offset == len(raw), 'Unexpected GDSC trailing bytes')
    # Preserve line-boundary token indices and exact indentation columns. Absolute
    # source line numbers do not affect execution; columns/line boundaries can.
    layout = sorted(maps[1].items())
    return {'version': version, 'tokens': canonical, 'layout': layout, 'raw_tokens': raw_tokens, 'identifiers': identifiers, 'constants': constants}


def differences(left, right, limit=5):
    result = []
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        if a != b:
            result.append({'index': index, 'original': a, 'roundtrip': b})
            if len(result) >= limit:
                break
    return result


def compare(original, roundtrip):
    a, b = parse(original), parse(roundtrip)
    tokens_equal = a['tokens'] == b['tokens']
    layout_equal = a['layout'] == b['layout']
    return {
        'equivalent': tokens_equal and layout_equal,
        'tokens_equal': tokens_equal, 'layout_equal': layout_equal,
        'original_tokens': len(a['tokens']), 'roundtrip_tokens': len(b['tokens']),
        'token_differences': differences(a['tokens'], b['tokens']),
        'layout_differences': differences(a['layout'], b['layout']),
    }


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('original', type=Path)
    args.add_argument('roundtrip', type=Path)
    args.add_argument('--report', type=Path)
    args = args.parse_args()
    if args.original.is_dir():
        files = sorted(args.original.rglob('*.gdc'))
        require(bool(files), 'No original GDSC files')
        results = {}
        for original in files:
            relative = original.relative_to(args.original)
            target = args.roundtrip / relative
            results[str(relative)] = compare(original.read_bytes(), target.read_bytes()) if target.is_file() else {'equivalent': False, 'error': 'Missing roundtrip file'}
        report = {'all_equivalent': all(r['equivalent'] for r in results.values()), 'file_count': len(results), 'files': results}
    else:
        report = compare(args.original.read_bytes(), args.roundtrip.read_bytes())
    formatted = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.report:
        args.report.write_text(formatted)
    print(formatted)
    raise SystemExit(0 if report.get('all_equivalent', report.get('equivalent')) else 1)


if __name__ == '__main__':
    main()
