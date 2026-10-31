#!/usr/bin/env python3
"""Rebuild frontend language catalogs and checksums after editing this release.
Run from any directory: python tools/build_web_release.py
No network access or production database is used.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'

def main():
    version=re.search(r'^VERSION = "([^"]+)"', (ROOT/'app.py').read_text(), re.M).group(1)
    keys=json.loads((WEB/'play/locale-keys.json').read_text())
    for lang in ('en','pl','de','es','fr'):
        source=json.loads((ROOT/(lang+'.json')).read_text())
        missing=[key for key in keys if key not in source] if lang!='pl' else []
        if missing:raise ValueError(f'{lang}: missing translations: {missing}')
        output={key:key if lang=='pl' else source[key] for key in keys}
        for key,value in output.items():
            if set(re.findall(r'\{\d+\}',key))!=set(re.findall(r'\{\d+\}',value)):
                raise ValueError(f'{lang}: mismatched placeholders: {key}')
        (WEB/'play/locales'/f'{lang}.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    files={}
    for directory in ('play','assets/art'):
        for file in sorted((WEB/directory).rglob('*')):
            if file.is_file() and file.name!='release.json' and not any(part.startswith('.') for part in file.relative_to(WEB).parts):
                files[file.relative_to(WEB).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
    (WEB/'play/release.json').write_text(json.dumps({'version':version,'files':files},indent=2)+'\n',encoding='utf-8')
    print(f'Alien Colonies {version}: {len(keys)} UI keys in 5 languages; {len(files)} checked files.')

if __name__=='__main__':main()
