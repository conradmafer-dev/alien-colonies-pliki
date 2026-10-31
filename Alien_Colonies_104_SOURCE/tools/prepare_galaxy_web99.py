"""Publish full-resolution galaxy art and cache-addressed web references."""
from pathlib import Path
import hashlib
import json
import subprocess

root=Path(__file__).resolve().parents[1]
path=root/'backend/web/play/art-manifest.js'
text=path.read_text()
start=text.index('Object.freeze(')+len('Object.freeze(')
end=text.rfind(');')
manifest=json.loads(text[start:end])
for name in ('aurora','nexus','omega','zephyr','eclipse','void'):
    source=root/f'docs/version99/galaxy_art_source/{name}_2048.png'
    records={}
    for width in (2048,1024):
        if width==2048:
            data=(root/f'client/assets/art/galaxies/{name}.webp').read_bytes()
        else:
            result=subprocess.run(['convert',str(source),'-resize',f'{width}x','-quality','93',
                '-define','webp:method=6','webp:-'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            data=result.stdout
        digest=hashlib.sha256(data).hexdigest()
        relative=f'assets/art/galaxies/{name}.{width}.{digest[:12]}.webp'
        (root/'backend/web'/relative).write_bytes(data)
        records[width]='/'+relative
    manifest['galaxies/'+name]={'src':records[2048],'small':records[1024],
        'width':2048,'height':1366,'smallWidth':1024}
path.write_text(text[:start]+json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+text[end:])
print('Updated6 high-resolution web images,6 previews and their cache-addressed references')
