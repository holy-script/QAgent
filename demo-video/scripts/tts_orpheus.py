import json, sys, time, numpy as np, soundfile as sf, mlx.core as mx
from mlx_audio.tts.utils import load_model
voice = sys.argv[1]; only = sys.argv[2:]
m = load_model("mlx-community/orpheus-3b-0.1-ft-bf16")
import os; os.makedirs(f"audio/or_{voice}", exist_ok=True); timing=[]
for sc in json.load(open("scripts/script3.json")):
    if only and sc["id"] not in only: continue
    parts=[]
    os.makedirs(f"audio/or_{voice}/lines", exist_ok=True)
    for li,(text, temp, pause) in enumerate(sc["lines"]):
        t0=time.time(); best=None
        for r in m.generate(text=text, voice=voice, temperature=temp, top_p=0.9, max_tokens=2400):
            a=np.array(r.audio).astype("float32"); best=a if best is None else np.concatenate([best,a])
        sf.write(f"audio/or_{voice}/lines/{sc['id']}_{li}.wav", best, 24000)
        parts += [best, np.zeros(int(24000*pause), dtype="float32")]
        print(sc["id"], round(len(best)/24000,1),"s gen",round(time.time()-t0),"s |", text[:48], flush=True)
    audio=np.concatenate(parts); sf.write(f"audio/or_{voice}/{sc['id']}.wav", audio, 24000)
    timing.append({"id":sc["id"],"seconds":round(len(audio)/24000,2)})
json.dump(timing, open(f"audio/or_{voice}/timing_{'_'.join(only) or 'all'}.json","w"), indent=1); print(timing)
