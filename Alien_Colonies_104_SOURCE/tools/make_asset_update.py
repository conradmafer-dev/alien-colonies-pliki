#!/usr/bin/env python3
"""Build a texture-only content pack after importing assets with Godot 4.5.1.

Example: python tools/make_asset_update.py --id icons-1 --origin
https://aliencolonies.com --out backend/web/play/content/packs client/assets/icon.png
Merge the generated pack record into content/manifest.json when publishing.
"""
import argparse,hashlib,json,pathlib,re,zipfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id',required=True)
    parser.add_argument('--origin',default='https://aliencolonies.com')
    parser.add_argument('--out',type=pathlib.Path,required=True)
    parser.add_argument('textures',nargs='+')
    args=parser.parse_args()
    root=pathlib.Path(__file__).resolve().parents[1]
    if not re.fullmatch(r'[a-z0-9_-]{1,64}',args.id):parser.error('Invalid pack id')
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?',args.origin):parser.error('Use an HTTPS server origin without a path')
    paths=set()
    for name in args.textures:
        name=name.replace('\\','/').removeprefix('res://')
        if '..' in name or not re.fullmatch(r'client/assets/[A-Za-z0-9_./-]+\.(png|webp|jpg|jpeg)',name):parser.error('Only project raster textures are accepted')
        imported=root/(name+'.import')
        text=imported.read_text(encoding='utf-8')
        if 'type="CompressedTexture2D"' not in text or 'importer="texture"' not in text:parser.error('Import the texture in Godot first')
        targets=re.findall(r'^path(?:\.[A-Za-z0-9_]+)?="res://(\.godot/imported/[A-Za-z0-9_.-]+\.ctex)"',text,re.M)
        if not targets:parser.error('No imported texture remapping found')
        paths.update([name,name+'.import',*targets])
    records=[]
    for name in sorted(paths):
        p=root/name
        if not p.is_file() or p.stat().st_size>16777216:parser.error('Missing or oversized imported texture: '+name)
        records.append({'path':name,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    if len(records)>512 or sum(r['size'] for r in records)>67108864:parser.error('Split this release into smaller packs')
    args.out.mkdir(parents=True,exist_ok=True)
    temporary=args.out/(args.id+'.zip.part')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for record in records:z.write(root/record['path'],record['path'])
    if temporary.stat().st_size>33554432:temporary.unlink();parser.error('Split this pack below 32 MiB')
    digest=hashlib.sha256(temporary.read_bytes()).hexdigest()
    target=args.out/(digest+'.zip');temporary.replace(target)
    record={'id':args.id,'url':args.origin+'/play/content/packs/'+target.name,'size':target.stat().st_size,'sha256':digest,'files':records}
    (args.out/(args.id+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pack':str(target),'record':str(args.out/(args.id+'.json'))}))
if __name__=='__main__':main()
