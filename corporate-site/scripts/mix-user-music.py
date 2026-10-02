"""Mix uploaded music under approved narration; preserve voice and video timing."""
import os,subprocess,wave,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1];ff=os.environ['FFMPEG'];sr=48000;N=30*sr

def decode(path,channels):
 raw=subprocess.check_output([ff,'-v','error','-i',str(path),'-ar',str(sr),'-ac',str(channels),'-f','f32le','-'])
 return np.frombuffer(raw,dtype='<f4').reshape(-1,channels)
voice=decode(root/'work/user-voiceover-timed.wav',1)[:N]
music=decode(root/'assets/teaser/user-music.wav',2)[:N]
assert len(voice)==N and len(music)==N
# Broad phrase envelopes avoid pumping between individual words.
t=np.arange(N)/sr;gain=np.full(N,.33);intervals=[(.8,4.85),(6.4,10.34),(12.3,16.16),(18.3,20.38),(23.3,29.641020833333332)]
for start,end in intervals:
 attack=np.clip((t-(start-.18))/.18,0,1)
 release=np.clip((end+.4-t)/.4,0,1)
 gain=np.minimum(gain,.33-.22*np.minimum(attack,release))
fades=np.minimum(1,t/.7)*np.clip((30-t)/1.3,0,1)
bed=music*(gain*fades)[:,None]*10**(3/20)  # User-requested +3 dB music increase.
# Preserve the narration level; reduce only the music if summed peaks need headroom.
for _ in range(20):
 mix=voice+bed
 if np.max(np.abs(mix))<=.94:break
 bed*=.92
assert np.max(np.abs(mix))<=.94
report=[]
for start,end in intervals:
 a=round(start*sr);b=round(end*sr);v=np.sqrt(np.mean(voice[a:b]**2));m=np.sqrt(np.mean(bed[a:b]**2))
 report.append({'start':start,'end':end,'voice_above_music_db':float(20*np.log10(v/max(m,1e-9)))})
assert min(x['voice_above_music_db'] for x in report)>12
with wave.open(str(root/'work/approved-voice-and-music.wav'),'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((mix*32767).astype('<i2').tobytes())
subprocess.run([ff,'-y','-v','error','-i',str(root/'dist/regfire-teaser-user-voiceover.mp4'),'-i',str(root/'work/approved-voice-and-music.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k','-t','30','-movflags','+faststart',str(root/'dist/regfire-teaser-music-louder.mp4')],check=True)
print(json.dumps({'duration':30,'peak_dbfs':float(20*np.log10(np.max(np.abs(mix)))),'voice_unchanged':True,'music_fades':[.7,1.3],'speech_balance':report},indent=2))
