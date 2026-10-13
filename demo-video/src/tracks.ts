import t_eco_app from "../public/tracks/eco_app.json";
import t_qa_bugs from "../public/tracks/qa_bugs.json";
import t_qa_plan from "../public/tracks/qa_plan.json";
import t_qa_quick from "../public/tracks/qa_quick.json";
import t_qa_quickrun from "../public/tracks/qa_quickrun.json";
import t_qa_results from "../public/tracks/qa_results.json";
import t_qa_setup from "../public/tracks/qa_setup.json";
export const TRACKS: Record<string, Record<string, number[][]>> = {eco_app: t_eco_app as any, qa_bugs: t_qa_bugs as any, qa_plan: t_qa_plan as any, qa_quick: t_qa_quick as any, qa_quickrun: t_qa_quickrun as any, qa_results: t_qa_results as any, qa_setup: t_qa_setup as any};
