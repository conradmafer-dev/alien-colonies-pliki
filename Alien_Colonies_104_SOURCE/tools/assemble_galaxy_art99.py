"""Assemble two overlapping, newly generated detail renders per galaxy.

The source tiles add real generated detail; this does not upscale old game art.
ImageMagick handles raster formatting and a narrow blend away from the core.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image
from galaxy_art_measure99 import optical_core

NAMES = ('aurora','nexus','omega','zephyr','eclipse','void')


def image_command(arguments):
    result=subprocess.run(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tiles',type=Path,required=True)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    masters=args.project/'docs/version99/galaxy_art_source'
    masters.mkdir(parents=True,exist_ok=True)
    records=[]
    with tempfile.TemporaryDirectory(prefix='galaxy99-assembly-') as directory:
        work=Path(directory)
        for name in NAMES:
            sources={}
            base=optical_core(masters/f'{name}_base.png',name)
            target_x=base['core_pixels'][0]*2048/base['dimensions'][0]
            target_y=base['core_pixels'][1]*1366/base['dimensions'][1]
            shifts={}
            for side in ('left','right'):
                source=args.tiles/f'{name}_{side}.png'
                with Image.open(source) as image:
                    native_size=image.size
                    image.verify()
                sources[side]={'native_size':native_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
                core=optical_core(source,name,side)
                origin=0 if side=='left' else 896
                shifts[side]=(round(target_x-origin-core['core_pixels'][0]*1152/native_size[0]),
                              round(target_y-core['core_pixels'][1]*1366/native_size[1]))
                sources[side]['alignment_shift']=shifts[side]
                normalized=image_command(['convert',str(source),'-resize','1152x1366!','-colorspace','sRGB',
                                          '-alpha','off','-depth','8','-strip','png:-'])
                (work/f'{side}.png').write_bytes(normalized)
            left_end=1152+shifts['left'][0]
            right_origin=896+shifts['right'][0]
            assert left_end-right_origin>96, (name,shifts)
            fade_end=left_end-right_origin-8
            fade_start=fade_end-80
            mask=work/'blend.png'
            mask.write_bytes(image_command(['convert','-size','1152x1366','xc:black',
                '-fx',f'min(1,max(0,(i-{fade_start})/80))','-depth','8','png:-']))
            right=work/'right-feather.png'
            right.write_bytes(image_command(['convert',str(work/'right.png'),str(mask),'-alpha','off',
                '-compose','CopyOpacity','-composite','png:-']))
            data=image_command(['convert','-size','2048x1366','xc:black',str(work/'left.png'),
                '-geometry','%+d%+d'%shifts['left'],'-compose','Over','-composite',str(right),
                '-geometry','%+d%+d'%(right_origin,shifts['right'][1]),
                '-compose','Over','-composite','-alpha','off','-depth','8','-strip','png:-'])
            with Image.open(io.BytesIO(data)) as image:
                assert image.size==(2048,1366) and image.mode=='RGB'
                image.verify()
            master=masters/f'{name}_2048.png'
            master.write_bytes(data)
            target=args.project/f'client/assets/art/galaxies/{name}.webp'
            target.write_bytes(image_command(['convert',str(master),'-define','webp:lossless=true','-define','webp:method=6','webp:-']))
            records.append({'galaxy':name,'dimensions':[2048,1366],
                'master_sha256':hashlib.sha256(data).hexdigest(),'runtime_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                'runtime_bytes':target.stat().st_size,'lossless_runtime':True,'detail_renders':sources,
                'assembly':'Two overlapping generated detail renders aligned by their optical cores, output2048x1366'})
    report=args.project/'docs/version99/galaxy_art99.json'
    report.write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(records,indent=2))


if __name__=='__main__':
    main()
