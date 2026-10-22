"""Measure extraction payload/CPU and optional public HTTP cold/warm latency.

The synthetic comparison is the previous DOM tool response shape versus the
new bounded reader. It is not a claim about end-to-end model quality or tokens.
"""
import argparse
import json
import tempfile
import time
from pathlib import Path
from luma_review.research import PageReader, extract_page

p=argparse.ArgumentParser();p.add_argument('--url');args=p.parse_args()
url='https://example.org/synthetic-professional'
noise=' '.join('Navigation item '+str(i) for i in range(1200))
bio='Synthetic engineer building open-source inference systems. ' * 20
links=[{'name':'Navigation '+str(i),'url':'https://example.org/navigation/'+str(i),'photo':None} for i in range(600)]
html=('<title>Synthetic engineer</title><nav>'+noise+''.join('<a href="'+a['url']+'">'+a['name']+'</a>' for a in links)+'</nav><main>'+bio+'</main>').encode()
old={'url':url,'title':'Synthetic engineer','text':(noise+' '+bio)[:24000],'links':links,'buttons':[]}
started=time.process_time()
for _ in range(100):new=extract_page(html,'text/html',url)
cpu=time.process_time()-started
before,after=len(json.dumps(old)),len(json.dumps(new))
result={'fixture':'Synthetic navigation-heavy professional page; same bio in both inputs',
        'old_dom_payload_characters':before,'new_http_payload_characters':after,
        'payload_reduction_percent':round(100*(1-after/before),2),
        'extraction_cpu_ms_per_page':round(cpu*1000/100,3),
        'browser_starts':0,'token_counts':'Not estimated: actual provider usage is recorded by customer-smoke.py'}
if args.url:
    with tempfile.TemporaryDirectory() as directory:
        reader=PageReader(Path(directory))
        started=time.monotonic();page=reader.read(args.url);cold=time.monotonic()-started
        started=time.monotonic();cached=PageReader(Path(directory)).read(args.url);warm=time.monotonic()-started
        assert cached['cached'] and cached['text']==page['text']
        result['public_http']={'url':args.url,'cold_seconds':round(cold,4),'warm_seconds':round(warm,4),
                               'text_characters':len(page['text']),'metrics':reader.metrics}
print(json.dumps(result,indent=2))
