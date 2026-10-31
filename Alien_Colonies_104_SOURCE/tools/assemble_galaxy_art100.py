"""Assemble generated detail tiles while retaining the original galaxy composition/colors.
Pixel editing is performed by ImageMagick; Pillow is used only for measurement.
"""
from pathlib import Path
import subprocess,json,hashlib,sys
from PIL import Image,ImageStat
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'docs/version100/galaxy_art_source'
def run(*args):
 # Capture complete output, then one write: never overwrite an input PNG in-place.
 target=Path(args[-1])
 fmt='jpeg' if target.suffix.lower() in ('.jpg','.jpeg') else 'png'
 result=subprocess.run(['convert',*[str(x) for x in args[:-1]],fmt+':-'],check=True,stdout=subprocess.PIPE)
 import io
 with Image.open(io.BytesIO(result.stdout)) as image:image.verify()
 target.write_bytes(result.stdout)
def mean(path):
 image=Image.open(path).convert('RGB')
 return sum(ImageStat.Stat(image).mean)/3
def assemble(name):
 out=WORK/'assembled';out.mkdir(exist_ok=True)
 g=out/f'{name}_detail.png'
 run('-size','3840x2560','xc:black',g)
 source=WORK/'base'/f'{name}.png'
 ref=WORK/'reference'/f'{name}.webp'
 target=mean(ref)*.9
 ref_scaled=out/f'{name}_reference.png'
 run(source,'-filter','Lanczos','-resize','3840x2560!','-evaluate','Multiply',target/mean(source),ref_scaled)
 tiles=[]
 for row,y in enumerate([0,748,1492]):
  for col,x in enumerate([0,1120,2240]):
   tile=WORK/'tiles'/f'{name}_{row}{col}.png'
   if not tile.exists():raise FileNotFoundError(tile)
   shape=Image.open(tile).size
   assert shape[0]>=1536 and shape[1]>=1024, (tile,shape)
   tiles.append({'name':tile.name,'native_pixels':list(shape),'sha256':hashlib.sha256(tile.read_bytes()).hexdigest()})
   patch=out/'tile.png';mask=out/'mask.png'
   run(tile,'-filter','Lanczos','-resize','1600x1068!',patch)
   fx=('min(1,max(0,(i-224)/32))' if col else '1')+'*'+('min(1,max(0,(j-144)/32))' if row else '1')
   run('-size','1600x1068','xc:white','-fx',fx,mask)
   run(patch,mask,'-alpha','off','-compose','CopyOpacity','-composite',patch)
   run(g,patch,'-geometry',f'+{x}+{y}','-compose','Over','-composite',g)
 blur=out/f'{name}_detail_low.png';hp=out/f'{name}_fine.png';master=out/f'{name}_master.png'
 run(g,'-blur','0x3',blur)
 run(g,blur,'-fx','u-v+.5',hp)
 # Only generated fine detail is merged. Broad color/dust structure remains faithful.
 run(ref_scaled,hp,'-fx','u+0.55*(v-.5)',master)
 run(master,'-evaluate','Multiply',target/mean(master),'-depth','8',master)
 run(master,'-resize','1152x768',out/f'{name}_preview.jpg')
 report={'galaxy':name,'master_pixels':[3840,2560],'original_pixels':[1536,1024],
  'generated_tiles':tiles,'method':'9 overlapping generated detail renders; original broad structure/colors retained; ImageMagick assembly',
  'mean_rgb_original':mean(ref),'mean_rgb_final':mean(master),'brightness_ratio':mean(master)/mean(ref),
  'sha256':hashlib.sha256(master.read_bytes()).hexdigest()}
 (out/f'{name}_assembly.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='generated_tiles'}),flush=True)
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);ap.add_argument('galaxies',nargs='*')
 args=ap.parse_args();WORK=args.work.resolve()
 for name in args.galaxies or ['aurora','nexus','omega','zephyr','eclipse','void']:assemble(name)
