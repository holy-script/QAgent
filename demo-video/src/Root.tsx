import React from "react";
import { AbsoluteFill, Audio, Composition, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import timingJson from "../public/audio/timing.json";
import { Bg, BigText, InfoCard, Intro, Outro, SpeedTag, Stack } from "./Cards";
import { ScreenClip } from "./Camera";
import { Subtitles } from "./Subtitles";
import { buildScenes, GAP, INTRO, SceneDef, Timing } from "./scenes";
import { FPS, H, W } from "./theme";

const timing = timingJson as Timing;
const SCENES = buildScenes(timing);
const layout = () => { let t = INTRO; const out = SCENES.map((def) => { const vo = timing.find((x) => x.id === def.id)!.seconds; const dur = vo + (def.tail ?? GAP); const r = { def, start: t, dur }; t += dur; return r; }); return { out, total: t }; };
const L = layout();

const Scene: React.FC<{ def: SceneDef; dur: number }> = ({ def, dur }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig(); const t = frame / fps;
  const lines = timing.find((x) => x.id === def.id)!.lines;
  return (
    <Bg>
      {def.shots.map((s, i) => {
        const next = def.shots[i + 1]; const end = next ? next.from + 0.35 : dur;
        const op = interpolate(t, [s.from, s.from + 0.35, end - 0.35, end], [i === 0 ? 1 : 0, 1, 1, next ? 0 : 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <Sequence key={i} from={Math.round(s.from * fps)} durationInFrames={Math.max(1, Math.round((end - s.from) * fps))} layout="none">
            <AbsoluteFill style={{ opacity: op }}>
              {s.clip && <ScreenClip clip={s.clip} />}
              {s.info && <InfoCard {...s.info} />}
              {s.outro && <Outro />}
              {s.logo && <Intro />}
              {s.stack && <Stack items={s.stack.items} />}
              {s.tag && <SpeedTag text={s.tag} />}
            </AbsoluteFill>
          </Sequence>
        );
      })}
      {(def.overlays ?? []).map((o, i) => <BigText key={i} {...o} />)}
      {!def.noSubs && <Subtitles lines={lines} chapter={def.chapter} />}
    </Bg>
  );
};

const Video: React.FC = () => (
  <AbsoluteFill style={{ background: "#0a2236" }}>
    <Audio src={staticFile("audio/bed.wav")} volume={(f) => 0.09 * interpolate(f, [0, 30, L.total * FPS - 75, L.total * FPS], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
    <Sequence from={0} durationInFrames={Math.round(INTRO * FPS)}><Intro /></Sequence>
    {L.out.map(({ def, start, dur }) => (
      <Sequence key={def.id} from={Math.round(start * FPS)} durationInFrames={Math.round(dur * FPS)}>
        <Scene def={def} dur={dur} />
        <Audio src={staticFile(`audio/${def.id}.wav`)} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

export const Root: React.FC = () => <Composition id="Demo" component={Video} durationInFrames={Math.round(L.total * FPS)} fps={FPS} width={W} height={H} />;
