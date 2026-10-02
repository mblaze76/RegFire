"""Preserve all uploaded narration samples; insert silence only at measured natural pauses."""
from pathlib import Path
import os,subprocess,wave,json
import numpy as np
root=Path(__file__).resolve().parents[1];ff=os.environ['FFMPEG'];sr=48000
raw=subprocess.check_output([ff,'-v','error','-i',str(root/'assets/teaser/user-voiceover.mp3'),'-ar',str(sr),'-ac','1','-f','f32le','-'])
source=np.frombuffer(raw,dtype='<f4');out=np.zeros(sr*30,dtype=np.float32)
bounds=[0,round(4.05*sr),round(7.99*sr),round(11.85*sr),round(13.93*sr),len(source)]
starts=[.8,6.4,12.3,18.3,23.3];retained=[];segments=[]
for i,start in enumerate(starts):
 part=source[bounds[i]:bounds[i+1]];a=round(start*sr);b=a+len(part)
 assert b<=len(out)
 out[a:b]=part*.85;retained.append(part)
 segments.append({'source_start':bounds[i]/sr,'source_end':bounds[i+1]/sr,'video_start':start,'video_end':b/sr})
assert np.array_equal(np.concatenate(retained),source)
with wave.open(str(root/'work/user-voiceover-timed.wav'),'wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((out*32767).astype('<i2').tobytes())
subprocess.run([ff,'-y','-v','error','-i',str(root/'dist/regfire-cinematic-flame-final.mp4'),'-i',str(root/'work/user-voiceover-timed.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t','30','-movflags','+faststart',str(root/'dist/regfire-teaser-user-voiceover.mp4')],check=True)
print(json.dumps({'source_duration':len(source)/sr,'all_source_samples_retained':True,'source_pitch_and_speed':'unchanged','video_duration':30,'music_added':False,'segments':segments,'mix_peak_dbfs':float(20*np.log10(np.max(np.abs(out))))},indent=2))
