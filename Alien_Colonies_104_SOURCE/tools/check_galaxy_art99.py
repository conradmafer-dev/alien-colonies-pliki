"""Measure actual optical cores/horizons and optionally align both map clients."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import numpy as np
from PIL import Image
from galaxy_art_measure99 import optical_core


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibrate',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    masters=root/'docs/version99/galaxy_art_source'
    profiles={}
    for name in ('aurora','nexus','omega','zephyr','eclipse','void'):
        measured=optical_core(masters/f'{name}_2048.png',name)
        w,h=measured['dimensions']
        assert (w,h)==(2048,1366)
        cx,cy=measured['core_pixels']
        profile=dict(measured,core=[cx/w,cy/h])
        if name in ('void','eclipse'):
            radius=measured['dark_horizon_radius_pixels']
            fit=min(2.2*1.65/w,1.2*1.65/h)
            minimum_inner_distance=.102*.6/fit
            profile.update(diameter_fraction_width=2*radius/w,
                minimum_inner_orbit_distance_pixels=minimum_inner_distance,
                minimum_center_clearance_pixels=minimum_inner_distance-radius)
            assert minimum_inner_distance-radius>12, (name,profile)
            if name=='void':assert 2*radius/w<.025
        profiles[name]=dict(profile,dimensions=[int(w),int(h)])
    report=root/'docs/version99/galaxy_optical_profiles99.json'
    report.write_text(json.dumps(profiles,indent=2)+'\n')
    if args.calibrate:
        path=root/'client/scripts/galaxy_map.gd'
        block='const GALAXY_CORE_POINTS: Dictionary = {\n'+''.join(
            '\t"%s": Vector2(%.9f, %.9f),\n' % (name,*profile['core']) for name,profile in profiles.items())+'}'
        source=path.read_text()
        source,count=re.subn(r'const GALAXY_CORE_POINTS: Dictionary = \{.*?\}',block,source,count=1,flags=re.S)
        assert count==1
        path.write_text(source)
        path=root/'backend/web/play/galaxy-map.js'
        block='export const GALAXY_CORES = '+json.dumps({name:profile['core'] for name,profile in profiles.items()},separators=(',',':'))+';'
        source,count=re.subn(r'export const GALAXY_CORES = .*?;',block,path.read_text(),count=1)
        assert count==1
        path.write_text(source)
    print(json.dumps(profiles,indent=2))


if __name__=='__main__':
    main()
