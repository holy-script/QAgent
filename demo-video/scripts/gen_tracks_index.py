import os, json
names = sorted(f[:-5] for f in os.listdir("public/tracks") if f.endswith(".json"))
open("src/tracks.ts", "w").write("".join(f'import t_{n} from "../public/tracks/{n}.json";\n' for n in names) + "export const TRACKS: Record<string, Record<string, number[][]>> = {" + ", ".join(f"{n}: t_{n} as any" for n in names) + "};\n")
print(names)
