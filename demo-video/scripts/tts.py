import json, sys, numpy as np, soundfile as sf
from kokoro import KPipeline
voice = sys.argv[1] if len(sys.argv) > 1 else "af_heart"
lines = json.load(open("scripts/script.json"))
pipe = KPipeline(lang_code="a")
out = []
for l in lines:
    chunks = [a for _, _, a in pipe(l["text"], voice=voice, speed=l["speed"], split_pattern=r"(?<=[.])\s+")]
    audio = np.concatenate([np.concatenate([c, np.zeros(int(24000*0.18))]) for c in chunks])  # beat between sentences
    sf.write(f"audio/{l['id']}.wav", audio, 24000)
    out.append({"id": l["id"], "seconds": round(len(audio)/24000, 2), "pause": l["pause"]})
    print(out[-1])
json.dump(out, open("audio/timing.json", "w"), indent=1)
print("total", round(sum(o["seconds"]+o["pause"] for o in out), 1))
