#!/usr/bin/env python3
"""Draw measured CAD top-outline and nominal plate envelope in a common XY frame."""
from pathlib import Path
import argparse,json
import numpy as np
import cadquery as cq

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1]);p=ap.parse_args().package
 s=cq.importers.importStep(str(p/'cad/vpiper_main_local_mm.step')).solids().val()
 f=max([x for x in s.Faces() if x.geomType()=='PLANE' and x.normalAt().z>.999 and abs(x.Center().z-50)<1e-5],key=lambda x:x.Area())
 ox,oy,k=650,435,3.1
 def pt(x,y):return (ox+x*k,oy-y*k)
 segments=[]
 for e in f.outerWire().Edges():
  n=1 if e.geomType()=='LINE' else 24
  segments.append([pt(e.positionAt(i/n).x,e.positionAt(i/n).y) for i in range(n+1)])
 points=segments.pop(0)
 while segments:
  options=[(float(np.linalg.norm(np.array(points[-1])-seg[idx])),j,idx) for j,seg in enumerate(segments) for idx in [0,-1]]
  dist,j,idx=min(options);assert dist<1e-3, 'Disconnected CAD wire'
  seg=segments.pop(j)
  if idx==-1:seg=seg[::-1]
  points.extend(seg[1:])
 assert np.linalg.norm(np.array(points[0])-points[-1])<1e-3
 parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="960" viewBox="0 0 1500 960">',
 '<defs><marker id="a" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto-start-reverse"><path d="M7,3.5 L0,0 L0,7 Z" fill="#222"/></marker></defs>',
 '<rect width="1500" height="960" fill="white"/>',
 '<style>text{font-family:DejaVu Sans,sans-serif;fill:#202020}.title{font-size:30px;font-weight:bold}.sub{font-size:20px}.label{font-size:21px}.small{font-size:18px}.dim{stroke:#222;stroke-width:1.8;fill:none;marker-start:url(#a);marker-end:url(#a)}.ext{stroke:#777;stroke-width:1;fill:none}</style>',
 '<text x="60" y="56" class="title">Plate width datum | top view in Vpiper local XY</text>',
 '<text x="60" y="94" class="sub">Solid outline = supplied CAD top face. Dashed rectangle = final 250 x 100 x 5 mm plate envelope.</text>']
 parts.append('<polygon points="'+' '.join(f'{x:.3f},{y:.3f}' for x,y in points)+'" fill="#eeeeee" stroke="#333" stroke-width="3"/>')
 x,y=pt(-125,50);parts.append(f'<rect x="{x}" y="{y}" width="{250*k}" height="{100*k}" fill="none" stroke="#111" stroke-width="3" stroke-dasharray="13 8"/>')
 def line(x1,y1,x2,y2,cl='ext'):parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cl}"/>')
 def txt(x,y,t,cl='label'):parts.append(f'<text x="{x}" y="{y}" class="{cl}">{t}</text>')
 # Length.
 x0,_=pt(-125,0);x1,_=pt(125,0);line(x0,715,x0,788);line(x1,591,x1,788);line(x0,771,x1,771,'dim');txt(575,809,'250 mm retained length')
 # Overall width at the head segment (including corner radii).
 _,y0=pt(0,50);_,y1=pt(0,-50);line(1010,y0,1145,y0);line(1010,y1,1145,y1);line(1130,y0,1130,y1,'dim');txt(1160,404,'100 mm');txt(1160,435,'overall head width');txt(1160,468,'= final plate width','small')
 # Straight leading edge, distinguish from full width.
 xs=pt(125,0)[0];ya=pt(125,40)[1];yb=pt(125,-40)[1];line(xs+20,ya,xs+20,yb,'dim');txt(805,429,'80 mm straight edge','small');txt(827,459,'+ R10 corners','small')
 # Rear wide envelope.
 xr=196;yr0=pt(0,86.552145976477)[1];yr1=pt(0,-86.55214395105)[1];line(x0,yr0,xr-18,yr0);line(x0,yr1,xr-18,yr1);line(xr,yr0,xr,yr1,'dim');txt(55,357,'173.104 mm','small');txt(55,386,'rear width','small');txt(55,414,'NOT plate width','small')
 txt(440,205,'Vpiper rear shoulder unchanged','small')
 # Forward axis.
 line(685,663,900,663,'ext');parts.append('<path d="M900,663 l-12,-5 l0,10 Z" fill="#222"/>');txt(712,700,'+X toward A2 head','small')
 parts+=['<line x1="60" y1="846" x2="1440" y2="846" stroke="#bbb"/>',
 '<text x="60" y="883" class="small">Only plate width changed. Vpiper itself is not cropped or rescaled. Slot/hole/corner details of the real plate are unmeasured.</text>',
 '<text x="60" y="917" class="small">100 mm is the CAD narrow-head outer width, not a ruler measurement extracted from the photograph.</text>','</svg>']
 out=p/'figures/plate_width_datums.svg';out.write_text('\n'.join(parts))
 try:
  import cairosvg
  cairosvg.svg2png(url=str(out),write_to=str(p/'figures/plate_width_datums.png'))
 except ImportError:print('SVG written; cairosvg absent, PNG omitted.')
if __name__=='__main__':main()
