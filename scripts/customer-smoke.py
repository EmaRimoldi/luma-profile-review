"""Reproducible customer CLI smoke test using public fictional examples only.

Run with the Python interpreter of a non-editable installed distribution.
No developer workspaces, browser sessions, response fixtures, or credentials are copied.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--backend',choices=['codex','claude','ollama','openai','anthropic'],required=True)
parser.add_argument('--model')
parser.add_argument('--batch-size',type=int,choices=[1,3])
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
args.workspace.mkdir(parents=True,exist_ok=True)
answers={'work':'I build open-source inference tools.','interests':['LLM inference'],
         'looking_for':'Technical feedback','connect_with':'Inference engineers',
         'can_offer':'Benchmarking experience','must_haves':[]}
answers_file=args.workspace/'smoke-answers.json'
answers_file.write_text(json.dumps(answers))
def cli(*command):
    result=subprocess.run([sys.executable,'-m','luma_review',*command,'--workspace',str(args.workspace)],capture_output=True,text=True,timeout=420)
    if result.returncode and (command[0]!='analyze' or not result.stdout.lstrip().startswith('{')):
        raise RuntimeError(result.stdout+'\n'+result.stderr)
    return json.loads(result.stdout)
cli('onboard','--answers',str(answers_file))
event=cli('import','--profiles',str(root/'examples/profiles.json'))['event_id']
command=['analyze','--event',event,'--backend',args.backend,'--timeout','120']
if args.model:command+=['--model',args.model]
if args.batch_size is not None:command+=['--batch-size',str(args.batch_size)]
started=time.monotonic()
result=cli(*command)
elapsed=time.monotonic()-started
assert result['counts']['reviewed']==3,result
guide=cli('guide','--event',event)
by_url={p['profile_url']:p for p in guide['people']}
def verdict(url,criterion):
    return next((a['verdict'] for a in by_url[url]['assessments'] if a['criterion_id']==criterion),None)
quality={'positive_inference_match':verdict('https://luma.com/user/demo-builder','P1')=='yes',
         'explicit_negative_match':verdict('https://luma.com/user/demo-photographer','P1')=='no',
         'missing_source_is_unknown':all(a['verdict']=='unknown' for a in by_url['https://luma.com/user/demo-unavailable']['assessments'])}
export=args.workspace/'guide.html'
cli('guide','--event',event,'--out',str(export))
assert '<!doctype html>' in export.read_text().lower()
usage_path=args.workspace/'work/usage.jsonl'
usage=usage_path.read_text().splitlines() if usage_path.exists() else []
if not result['errors']:cli(*command)
assert (usage_path.read_text().splitlines() if usage_path.exists() else [])==usage,'Repeat run should use validated cache'
print(json.dumps({'backend':args.backend,'model':args.model,'seconds':round(elapsed,3),
                  'counts':result['counts'],'errors':result['errors'],'quality_checks':quality,
                  'model_requests':len(usage),'repeat_model_requests':0 if not result['errors'] else None,
                  'usage':[json.loads(line) for line in usage],'export_bytes':export.stat().st_size},indent=2))

sys.exit(0 if not result['errors'] and all(quality.values()) else 1)
