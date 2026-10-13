#!/bin/bash
# usage: sheet.sh clip [step]   -> footage/_sh_<clip>.png (tiles labelled by time)
c=$1; step=${2:-3}; d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 footage/$c.mp4)
rows=$(python3 -c "import math;print(math.ceil($d/$step/6))")
ffmpeg -y -loglevel error -i footage/$c.mp4 -vf "fps=1/$step,scale=480:-1,tile=6x$rows" -frames:v 1 footage/_sh_$c.png 2>&1 | tail -1
echo "$c ${d}s step $step"
