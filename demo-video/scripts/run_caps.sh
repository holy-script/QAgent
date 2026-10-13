#!/bin/bash
cd /Users/holyscript/Desktop/projects/QAgent/demo-video
PY=/Users/holyscript/.pyenv/versions/3.12.9/bin/python3
export PYTHONPATH=scripts QAGENT_EMAIL='admin@chryselys.com' QAGENT_PASSWORD='Admin@QAgent!2026' ECO_PASSWORD='forecastiq2025'
for sc in cap_eco2 cap_qa_setup cap_qa_plan cap_qa_results2 cap_qa_bugs cap_qa_quick; do echo "== $sc"; $PY scripts/$sc.py 2>&1 | tail -4; done
echo ALLDONE
