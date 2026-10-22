const test = require('node:test');
const assert = require('node:assert/strict');
const ProfileSearch = require('../src/luma_review/static/search.js');
const people = [
  {name:'Zoë Chen',summary:'GPU inference engineer',why:['Open source scheduler'],professional:{facts:[]}},
  {name:'Alex Park',summary:'Jewelry designer',why:[],professional:{facts:[]}},
  {name:'Jordan Smith',summary:'GPU infrastructure and inference benchmarks',why:[],professional:{facts:[]}},
];
const index = new ProfileSearch(people);
test('an empty query preserves the evidence-based ranking',()=>assert.deepEqual(index.search('').map(r=>r.person.name),people.map(p=>p.name)));
test('names normalize accents and support a partial last term',()=>assert.equal(index.search('zoe ch')[0].person.name,'Zoë Chen'));
test('all query terms must match; unrelated people are excluded',()=>assert.deepEqual(index.search('gpu infer').map(r=>r.person.name).sort(),['Jordan Smith','Zoë Chen']));
test('unmatched terms never create fabricated semantic matches',()=>assert.equal(index.search('robotics').length,0));
test('search remains safe for punctuation-only and HTML-like input',()=>{assert.equal(index.search('<script>alert(1)</script>').length,0);assert.equal(index.search('!!!').length,3);});
