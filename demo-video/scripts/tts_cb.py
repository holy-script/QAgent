import json, sys, torch, numpy as np, soundfile as sf, torchaudio as ta, os
from chatterbox.tts import ChatterboxTTS
dev = "mps" if torch.backends.mps.is_available() else "cpu"
m = ChatterboxTTS.from_pretrained(device=dev)
ref = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else None
only = sys.argv[2:] 
os.makedirs("audio/cb", exist_ok=True)
timing = []
for sc in json.load(open("scripts/script2.json")):
    if only and sc["id"] not in only: continue
    parts = []
    for text, ex, cfg, pause in sc["lines"]:
        torch.manual_seed(7)
        w = m.generate(text, audio_prompt_path=ref, exaggeration=ex, cfg_weight=cfg, temperature=0.8)
        a = w.squeeze().cpu().numpy(); parts += [a, np.zeros(int(m.sr * pause))]
        print(sc["id"], round(len(a) / m.sr, 1), "s |", text[:50], flush=True)
    audio = np.concatenate(parts); sf.write(f"audio/cb/{sc['id']}.wav", audio, m.sr)
    timing.append({"id": sc["id"], "seconds": round(len(audio) / m.sr, 2)})
json.dump(timing, open("audio/cb/timing.json", "w"), indent=1); print(timing, sum(t["seconds"] for t in timing))
