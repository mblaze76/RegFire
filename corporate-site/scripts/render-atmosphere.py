"""Silent 30-second RegFire title film. FFMPEG environment variable required."""
import os,math,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageEnhance,ImageFilter,ImageChops
W,H,FPS=1920,1080,24
root=Path(__file__).resolve().parents[1]
plate=Image.open(root/'assets/teaser/atmosphere.png').convert('RGB').resize((2074,1167),Image.Resampling.LANCZOS)
# Extend both atmospheric edges inward, keeping the center low contrast.
left=Image.new('RGB',plate.size);left.paste(plate.crop((0,0,1037,1167)),(240,0))
right=Image.new('RGB',plate.size);right.paste(plate.crop((1037,0,2074,1167)),(797,0))
plate=ImageChops.screen(plate,ImageEnhance.Brightness(ImageChops.add(left,right).filter(ImageFilter.GaussianBlur(18))).enhance(.68))
logo=Image.open(root/'assets/teaser/regfire-3d-clean.png').convert('RGB')
font='/System/Library/Fonts/Supplemental/Arial.ttf'
bold='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def ease(x):
 x=max(0,min(1,x));return x*x*(3-2*x)
def title(im,text,cy,size,alpha=1,spacing=7,color=(238,237,234),heavy=False):
 cy+=int(32*(1-alpha));spacing+=3*(1-alpha)
 layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer);f=ImageFont.truetype(bold if heavy else font,size)
 widths=[d.textlength(c,font=f) for c in text];x=(W-sum(widths)-spacing*(len(text)-1))/2
 for c,w in zip(text,widths):d.text((x,cy),c,font=f,fill=(*color,int(255*max(0,min(1,alpha)))));x+=w+spacing
 if alpha<.98:layer=layer.filter(ImageFilter.GaussianBlur(3*(1-alpha)))
 return Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
def scene(t):
 # Animate the photographic haze with a continuous, low-amplitude mesh flow.
 # Center remains quiet; edge smoke drifts upward and rolls independently.
 def source(x,y):
  edge=abs(x-W/2)/(W/2)
  dx=(16+26*edge)*math.sin(y/280+t*.58)+12*math.sin(x/460+t*.31)
  dy=23*math.sin(x/370-t*.44)+18*math.sin(y/410+t*.24)
  return (x+70+dx,y+44+dy)
 mesh=[]
 for y in range(0,H,90):
  for x in range(0,W,120):
   x2=min(W,x+120);y2=min(H,y+90)
   points=source(x,y)+source(x,y2)+source(x2,y2)+source(x2,y)
   mesh.append(((x,y,x2,y2),points))
 im=plate.transform((W,H),Image.Transform.MESH,mesh,Image.Resampling.BICUBIC)
 im=ImageEnhance.Brightness(im).enhance(.67+.09*math.sin(t*.7))
 if t<6:
  a=ease((t-.5)/1)*ease((6-t)/.9)
  im=title(im,'BEFORE THE DOORS OPEN.',425,67,a,5)
  im=title(im,'BEFORE THE FIRST HELLO.',555,36,a,5,(195,193,188))
 elif t<12:
  a=ease((t-6)/.9)*ease((12-t)/.9)
  im=title(im,'THERE IS A MOMENT.',420,76,a,7)
  im=title(im,'WHEN EVERYTHING COMES TOGETHER.',560,35,a,4,(195,193,188))
 elif t<18:
  i=min(2,int((t-12)/2));u=(t-12)%2;a=ease(u/.45)*ease((2-u)/.4)
  im=title(im,['THE PEOPLE.','THE ENERGY.','THE POSSIBILITY.'][i],442,88,a,7)
 elif t<22:
  a=ease((t-18)/.8)*ease((22-t)/.7)
  im=title(im,'MAKE IT',350,40,a,10,(177,175,170))
  im=title(im,'UNFORGETTABLE.',470,97,a,5,heavy=True)
 elif t<23:
  im=ImageEnhance.Brightness(im).enhance(.55)
 else:
  u=t-23;a=ease(u/1.1);size=int(550+40*ease(u/2.3));lg=logo.resize((size,size),Image.Resampling.LANCZOS)
  # Existing brand artwork is preserved; blend its black matte into the plate.
  from PIL import ImageChops
  layer=Image.new('RGB',(W,H));layer.paste(lg,((W-size)//2,65+(590-size)//2))
  im=ImageChops.lighter(im,ImageEnhance.Brightness(layer).enhance(a))
  im=title(im,'REGISTRATION. REIGNITED.',710,37,ease((u-.5)/.9),5)
  im=title(im,'COMING SOON',817,40,ease((u-1.2)/.9),8,(211,193,174))
 return ImageEnhance.Brightness(im).enhance(ease(t/.6))
ff=os.environ['FFMPEG'];output=root/'work/atmosphere-master.mp4'
p=subprocess.Popen([ff,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart','-t','30',str(output)],stdin=subprocess.PIPE)
frames=[]
for n in range(30*FPS):
 im=scene(n/FPS)
 if n in [72,192,312,360,408,468,552,588,672]:
  im.save(root/f'work/atmosphere-{n}.jpg',quality=94);frames.append(im.resize((640,360)))
 if n==672:im.save(root/'dist/regfire-atmosphere-wide-poster.jpg',quality=95)
 p.stdin.write(im.tobytes())
p.stdin.close();assert p.wait()==0
# Final restrained shadow lift adds presence to smoke and ember glow, preserving black and white.
subprocess.run([ff,'-y','-v','error','-i',str(output),'-vf',"curves=all='0/0 0.08/0.10 0.20/0.23 0.50/0.51 1/1'",'-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-t','30','-movflags','+faststart',str(root/'dist/regfire-atmosphere-final.mp4')],check=True)
sheet=Image.new('RGB',(1920,1080))
for i,im in enumerate(frames):sheet.paste(im,((i%3)*640,(i//3)*360))
sheet.save(root/'work/atmosphere-contact.jpg',quality=94)
print('Rendered 720 frames, 1920x1080, 30 seconds, no audio stream.')
