"""Build the public, browser-only app. Never reads an existing user workspace."""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from luma_review.demo import load_demo
from luma_review.workspace import Workspace

parser=argparse.ArgumentParser()
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
args.out.mkdir(parents=True,exist_ok=True)
static=ROOT/'src/luma_review/static'
for name in ('app.css','polish.css','app.js','search.js','context-graph.js','ambient.js','browser-workspace.js'):
    shutil.copy2(static/name,args.out/name)
for name in ('fonts','vendor'):
    shutil.copytree(static/name,args.out/name,dirs_exist_ok=True)
page=(static/'index.html').read_text().replace('<script id="bootstrap" type="application/json">{"token":"__LOCAL_TOKEN__"}</script>', '<script>window.__BROWSER_WORKSPACE__=true;</script>')
page=page.replace('<script src="/app.js" defer></script>','<script src="/browser-workspace.js" defer></script><script src="/app.js" defer></script>')
(args.out/'index.html').write_text(page)
with tempfile.TemporaryDirectory() as directory:
    demo=load_demo(Workspace(Path(directory)))
(args.out/'demo.json').write_text(json.dumps(demo,ensure_ascii=False,indent=2))
shutil.copy2(ROOT/'LICENSE',args.out/'LICENSE.txt')
(args.out/'_headers').write_text('/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Content-Security-Policy: default-src \'self\'; script-src \'self\' \'unsafe-inline\'; style-src \'self\' \'unsafe-inline\'; img-src https: http: data:; font-src \'self\'; connect-src \'self\'; frame-ancestors \'none\'; base-uri \'none\'\n')
print('Public browser app built with fictional demo data only.')
