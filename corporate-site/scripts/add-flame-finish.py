"""Add a photographic animated flame layer to the approved silent master; smoke unchanged."""
from pathlib import Path
import os,math,subprocess
from PIL import Image,ImageChops,ImageEnhance
root=Path(__file__).resolve().parents[1];ff=os.environ['FFMPEG'];W,H,FPS=1920,1080,24
flame=Image.open(root/'assets/teaser/flame-overlay.png').convert('RGB').resize((1000,580),Image.Resampling.LANCZOS)
# Keep the VFX plate's black field completely neutral when screen-composited.
flame=flame.point(lambda v: max(0,v-8))
reader=subprocess.Popen([ff,'-v','error','-i',str(root/'dist/regfire-atmosphere-final.mp4'),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
writer=subprocess.Popen([ff,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','24','-i','-','-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart','-t','30',str(root/'dist/regfire-cinematic-flame-final.mp4')],stdin=subprocess.PIPE)
for n in range(720):
 t=n/FPS;raw=reader.stdout.read(W*H*3);assert len(raw)==W*H*3
 base=Image.frombytes('RGB',(W,H),raw)
 def point(x,y):
  strength=max(0,(y-350)/190)
  return (x+20+strength*(7*math.sin(y/44+t*2.7)+4*math.sin(x/65+t*3.3)),y+18+strength*(7*math.sin(x/38-t*3.2)+4*math.cos(x/71+t*4.1)))
 mesh=[]
 for y in range(0,540,30):
  for x in range(0,960,60):
   mesh.append(((x,y,x+60,y+30),point(x,y)+point(x,y+30)+point(x+60,y+30)+point(x+60,y)))
 layer=flame.transform((960,540),Image.Transform.MESH,mesh,Image.Resampling.BICUBIC).resize((W,H),Image.Resampling.BILINEAR)
 # A soft spatial mask confines new flame to the bottom edge, away from type and smoke.
 mask=Image.new('L',(1,H));mask.putdata([int(255*max(0,min(1,(y-H*.74)/(H*.12)))) for y in range(H)])
 layer=Image.composite(layer,Image.new('RGB',(W,H)),mask.resize((W,H)))
 layer=ImageEnhance.Brightness(layer).enhance((.66+.06*math.sin(t*3.4)+.025*math.sin(t*7))*min(1,t/.7))
 out=ImageChops.screen(base,layer)
 if n in [72,192,408,468,672]:out.save(root/f'work/flame-final-{n}.jpg',quality=94)
 if n==672:out.save(root/'dist/regfire-cinematic-flame-poster.jpg',quality=95)
 writer.stdin.write(out.tobytes())
reader.stdout.close();assert reader.wait()==0
writer.stdin.close();assert writer.wait()==0
print('Finished 720-frame silent flame composite. Approved smoke master retained unchanged beneath flame layer.')
