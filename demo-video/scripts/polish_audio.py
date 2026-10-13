"""Assemble each scene from its per-line takes: trim Orpheus's long silences, cap inner gaps, place the script's own pauses,
level-match, and write public/audio/<id>.wav + timing.json (with per-line start/end for subtitles and visual sync)."""
import json, subprocess, sys, os, numpy as np, soundfile as sf, librosa
voice = sys.argv[1]; SR = 24000
script = json.load(open("scripts/script3.json")); os.makedirs("public/audio", exist_ok=True); timing = []

def tidy(path):
    y, _ = librosa.load(path, sr=SR)
    iv = librosa.effects.split(y, top_db=38, frame_length=1024, hop_length=256)
    seg = []
    for s, e in iv:
        if seg and (s - seg[-1][1]) / SR < 0.14: seg[-1][1] = e
        else: seg.append([s, e])
    pad = int(0.05 * SR); out = []
    for k, (s, e) in enumerate(seg):
        if k: out.append(np.zeros(int(min(max((s - seg[k - 1][1]) / SR - 0.05, 0.16), 0.62) * SR), dtype="float32"))
        out.append(y[max(0, s - pad): min(len(y), e + pad)])
    return np.concatenate(out)

for sc in script:
    parts, lines, t = [np.zeros(int(0.08 * SR), dtype="float32")], [], 0.08
    ok = True
    for li, (text, temp, pause) in enumerate(sc["lines"]):
        p = f"audio/or_{voice}/lines/{sc['id']}_{li}.wav"
        if not os.path.exists(p): ok = False; break
        a = tidy(p); d = len(a) / SR
        lines.append({"text": text, "start": round(t, 2), "end": round(t + d, 2)}); parts += [a, np.zeros(int((pause + 0.1) * SR), dtype="float32")]; t += d + pause + 0.1
    if not ok: print("skip", sc["id"]); continue
    tmp = f"audio/_tmp_{sc['id']}.wav"; sf.write(tmp, np.concatenate(parts), SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af",
        "highpass=f=80,equalizer=f=200:t=q:w=1:g=1.2,equalizer=f=3500:t=q:w=1.2:g=1,acompressor=threshold=-21dB:ratio=2.2:attack=10:release=150,loudnorm=I=-16:TP=-1.5:LRA=7,afade=t=in:d=0.02",
        "-ar", "48000", "-ac", "1", f"public/audio/{sc['id']}.wav"], check=True); os.remove(tmp)
    dur = sf.info(f"public/audio/{sc['id']}.wav").duration
    timing.append({"id": sc["id"], "seconds": round(dur, 2), "lines": lines}); print(sc["id"], round(dur, 1))
json.dump(timing, open("public/audio/timing.json", "w"), indent=1); print("total", round(sum(x["seconds"] for x in timing), 1))
