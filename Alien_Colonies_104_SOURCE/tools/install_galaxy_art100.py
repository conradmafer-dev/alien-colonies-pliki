"""Install the six 4K galaxy masters and keep native/web calibration in sync.
Usage: python tools/install_galaxy_art100.py --masters /path/to/assembled
All raster conversion uses ImageMagick; Pillow is used for verification only.
"""
from pathlib import Path
import argparse,subprocess,os,io,json,hashlib,re,concurrent.futures
from PIL import Image
from galaxy_art_measure99 import optical_core
NAMES=('aurora','nexus','omega','zephyr','eclipse','void')
def convert(*args):
 env=dict(os.environ,MAGICK_THREAD_LIMIT='2')
 return subprocess.run(['convert',*[str(a) for a in args]],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env).stdout
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--masters',type=Path,required=True);ap.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1]);a=ap.parse_args()
 root=a.project.resolve();docs=root/'docs/version100';dst=docs/'galaxy_art_source';dst.mkdir(parents=True,exist_ok=True)
 def install(name):
  source=next((p for p in (a.masters/f'{name}_master.png',a.masters/f'{name}_3840.png') if p.exists()),None)
  if not source:raise FileNotFoundError(name)
  data=convert(source,'-strip','-depth','8','png:-')
  with Image.open(io.BytesIO(data)) as image:image.load();assert image.size==(3840,2560);rgb=image.convert('RGB').tobytes()
  master=dst/f'{name}_3840.png';master.write_bytes(data)
  native=convert(master,'-define','webp:lossless=true','-define','webp:method=6','-quality','100','webp:-')
  with Image.open(io.BytesIO(native)) as image:image.load();assert image.convert('RGB').tobytes()==rgb
  (root/f'client/assets/art/galaxies/{name}.webp').write_bytes(native)
  small=convert(master,'-resize','1024x','-quality','93','-define','webp:method=6','webp:-')
  records={}
  for width,content in [(3840,native),(1024,small)]:
   digest=hashlib.sha256(content).hexdigest();relative=f'assets/art/galaxies/{name}.{width}.{digest[:12]}.webp'
   (root/'backend/web'/relative).write_bytes(content);records[width]='/'+relative
  print('Installed',name,len(native),flush=True)
  return name,{'src':records[3840],'small':records[1024],'width':3840,'height':2560,'smallWidth':1024},hashlib.sha256(rgb).hexdigest()
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:installed=list(pool.map(install,NAMES))
 profiles={}
 for name in NAMES:
  info=optical_core(dst/f'{name}_3840.png',name);w,h=info['dimensions'];info['core']=[info['core_pixels'][0]/w,info['core_pixels'][1]/h];profiles[name]=info
  print('Calibrated',name,info,flush=True)
 (docs/'galaxy_optical_profiles100.json').write_text(json.dumps(profiles,indent=2)+'\n')
 (root/'backend/web/play/tests/fixtures/galaxy-art100.json').write_text(json.dumps(profiles,indent=2)+'\n')
 gd=root/'client/scripts/galaxy_map.gd';s=gd.read_text()
 core='const GALAXY_CORE_POINTS: Dictionary = {\n'+''.join('\t"%s": Vector2(%.12f, %.12f),\n'%(n,*profiles[n]['core']) for n in NAMES)+'}'
 s,count=re.subn(r'const GALAXY_CORE_POINTS: Dictionary = \{.*?\n\}',core,s,count=1,flags=re.S);assert count==1;gd.write_text(s)
 js=root/'backend/web/play/galaxy-map.js';s=js.read_text();s,count=re.subn(r'export const GALAXY_CORES = \{[^\n]+\};','export const GALAXY_CORES = '+json.dumps({n:profiles[n]['core'] for n in NAMES},separators=(',',':'))+';',s,count=1);assert count==1;js.write_text(s)
 path=root/'backend/web/play/art-manifest.js';s=path.read_text();start=s.index('Object.freeze(')+len('Object.freeze(');end=s.rfind(');');manifest=json.loads(s[start:end])
 for name,entry,_ in installed:manifest['galaxies/'+name]=entry
 path.write_text(s[:start]+json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+s[end:])
 (docs/'runtime_galaxies100.json').write_text(json.dumps([{'galaxy':n,'runtime':e,'pixel_sha256':sha} for n,e,sha in installed],indent=2)+'\n')
if __name__=='__main__':main()

