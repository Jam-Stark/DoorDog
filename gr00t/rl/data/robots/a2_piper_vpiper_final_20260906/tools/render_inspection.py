#!/usr/bin/env python3
"""Deterministic mesh render of the delivered URDF; no physics or image generation.
The joint pose is for inspection only and is not inferred from the owner's photo.
"""
from pathlib import Path
import argparse,json
import numpy as np
import trimesh,vtk
from PIL import Image,ImageDraw,ImageFont
from verify_models import urdf_tree,transform


def font(size,bold=False):
    base=Path('/usr/share/fonts/truetype/dejavu')
    name='DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    return ImageFont.truetype(str(base/name),size)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1]);args=ap.parse_args();p=args.package.resolve()
    cfg=json.loads((p/'config/mount_parameters.json').read_text());q=json.loads((p/'config/inspection_pose.json').read_text())
    root,links,joints,fk=urdf_tree(p/'a2_piper.urdf');poses=fk(q)
    scene=trimesh.Scene();actors=[]
    for name,link in links.items():
        for vi,vis in enumerate(link.findall('visual')):
            shape=vis.find('geometry/mesh')
            if shape is None:continue
            path=p/shape.get('filename');o=vis.find('origin');T=poses[name]@transform(o.get('xyz'),o.get('rpy'))
            c=vis.find('material/color');color=np.fromstring(c.get('rgba'),sep=' ') if c is not None else np.array([.52,.54,.58,1])
            if name=='metal_plate_5mm':color=np.array([.88,.58,.14,1])
            mesh=trimesh.load(path,process=False);mesh.visual.face_colors=(color*255).astype(np.uint8)
            scene.add_geometry(mesh,node_name=name,geom_name=name,transform=T)
            reader=vtk.vtkSTLReader();reader.SetFileName(str(path));reader.Update()
            normals=vtk.vtkPolyDataNormals();normals.SetInputConnection(reader.GetOutputPort());normals.SetFeatureAngle(45);normals.ConsistencyOn();normals.SplittingOn();normals.Update()
            mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
            actor=vtk.vtkActor();actor.SetMapper(mapper);mat=vtk.vtkMatrix4x4()
            for i in range(4):
                for j in range(4):mat.SetElement(i,j,T[i,j])
            actor.SetUserMatrix(mat);actor.GetProperty().SetColor(*color[:3]);actor.GetProperty().SetInterpolationToPhong();actor.GetProperty().SetSpecular(.15);actor.GetProperty().SetSpecularPower(25)
            actors.append((name,actor))
    scene.export(p/'cad/assembly_inspection_pose_m.glb')
    for stem,title,subtitle,cam,focal,scale,subset in [
        ('assembly_inspection','A2 + PiPER | corrected mount geometry','Supplied A2/PiPER meshes + Vpiper CAD + revised 100 mm head-width plate', [1.5,-1.65,1.0],[.075,0,.02],.59,None),
        ('mount_closeup','Mount detail | 250 x 100 x 5 mm plate','Upper arm links omitted for clarity. Plate holes/slots are not modeled.', [.65,-.80,.48],[.125,0,.125],.215,{'trunk','vpiper_main','vpiper_support','metal_plate_5mm','arm_body0','arm_body1'})]:
        r=vtk.vtkRenderer();r.SetBackground(.972,.98,.987)
        for name,actor in actors:
            if subset is None or name in subset:r.AddActor(actor)
        camera=r.GetActiveCamera();camera.SetPosition(*cam);camera.SetFocalPoint(*focal);camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();camera.SetParallelScale(scale)
        r.ResetCameraClippingRange();w=vtk.vtkRenderWindow();w.SetOffScreenRendering(1);w.SetSize(1800,1100);w.SetMultiSamples(8);w.AddRenderer(r);w.Render()
        cap=vtk.vtkWindowToImageFilter();cap.SetInput(w);cap.Update();wr=vtk.vtkPNGWriter();raw=p/'figures'/f'_{stem}_raw.png';wr.SetFileName(str(raw));wr.SetInputConnection(cap.GetOutputPort());wr.Write();w.Finalize()
        base=Image.open(raw).convert('RGB');img=Image.new('RGB',(1800,1400),'white');img.paste(base,(0,140));d=ImageDraw.Draw(img)
        d.text((60,30),title,font=font(40,True),fill='#172431');d.text((60,87),subtitle,font=font(23),fill='#42596b')
        d.line((60,1280,1740,1280),fill='#b8c5ce',width=2)
        xyz=np.array(cfg['primary_arm_origin_B_m'])*1000
        d.text((60,1300),f"PiPER origin in trunk B: [{xyz[0]:.3f}, {xyz[1]:.3f}, {xyz[2]:.3f}] mm | RPY = [0, 0, 0]",font=font(25,True),fill='#172431')
        d.text((60,1345),'Original X/Y retained. CAD-derived Z. Inspection pose only. Highlighted = extra 5 mm plate.',font=font(22),fill='#42596b')
        img.save(p/'figures'/f'{stem}.png');raw.unlink()
    print('Wrote two deterministic renders and a static, metre-scale GLB.')

if __name__=='__main__':main()
