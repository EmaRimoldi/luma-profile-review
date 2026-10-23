const test = require('node:test');
const assert = require('node:assert/strict');
const {create,validateGuide,makeBrief,criteria}=require('../src/luma_review/static/browser-workspace.js');
const {elements}=require('../src/luma_review/static/context-graph.js');
const brief={work:'Building inference tools',interests:['GPUs'],looking_for:'Technical collaborators',connect_with:'Engineers',can_offer:'Benchmarks',must_haves:[]};
function guide(){return {event_id:'event',event:{url:'https://luma.com/example?ticket=private',name:'Sample'},brief,criteria_markdown:'# Criteria',counts:{captured:1,reviewed:1,recommended:1},people:[{profile_url:'https://luma.com/user/sample',name:'Sample',summary:'Engineer',why:['GPUs'],sources:[{id:'s1',url:'https://example.org',text:'GPU engineer'}],assessments:[{evidence:[{source_id:'s1',quote:'GPU engineer'}]}],score:{status:'Preference match'},contact_links:{email:'no@example.org',linkedin:'https://www.linkedin.com/in/sample'}}],graph:{nodes:[{id:'person',type:'person',label:'Sample'},{id:'topic',type:'topic',label:'GPUs'},{id:'isolated',label:'Unused'}],edges:[{id:'edge',source:'person',target:'topic',evidence:[{quote:'GPU engineer',source_url:'https://example.org'}]}]}};}
function store(){const values=new Map();return {getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),values};}
test('onboarding assigns no city and keeps only explicit location requirements',()=>{
  const profile=makeBrief({...brief,must_haves:['Currently works in São Paulo']});
  assert.equal(profile.region,undefined);
  assert.match(criteria(profile),/Currently works in São Paulo/);
  assert.doesNotMatch(criteria(profile),/San Francisco/);
});
test('legacy automatic region tags do not discard reviewed work or explicit preferences',async()=>{
  const storage=store(),api=create(storage);
  await api.request('/api/import',guide());
  const key=[...storage.values.keys()][0],saved=JSON.parse(storage.getItem(key));
  saved.brief={...saved.brief,id:'legacy-profile',region:'San Francisco Bay Area'};
  saved.guides.event.brief={...saved.brief};
  saved.criteria_markdown+='\nUser-specified location: San Francisco.';
  saved.guides.event.criteria_markdown=saved.criteria_markdown;
  storage.setItem(key,JSON.stringify(saved));
  const reopened=create(storage),state=await reopened.request('/api/state');
  assert.equal(state.brief.region,undefined);
  assert.equal(state.brief.id,'legacy-profile');
  const restored=await reopened.request('/api/guide?event=event');
  assert.equal(restored.brief.region,undefined);
  assert.equal(restored.people.length,1);
  assert.equal(restored.analysis_stale,false);
  assert.match(restored.criteria_markdown,/User-specified location: San Francisco/);
});
test('guide imports remove the old default but retain custom region metadata',()=>{
  const old=guide();old.brief={...brief,region:'San Francisco Bay Area'};
  assert.equal(validateGuide(old).brief.region,undefined);
  assert.equal(old.brief.region,'San Francisco Bay Area');
  old.brief.region='Berlin';
  assert.equal(validateGuide(old).brief.region,'Berlin');
});
test('events outside the US use the same browser workflow and current distribution',async()=>{
  const api=create(store());await api.request('/api/onboard',brief);
  for(const [name,slug] of [['Berlin','berlin'],['Singapore','singapore'],['São Paulo','sao-paulo']]){
    const event=await api.request('/api/events',{name,url:'https://luma.com/test-'+slug});
    const g=await api.request('/api/guide?event='+event.event_id);
    assert.equal(g.event.name,name);
    assert.equal(g.brief.region,undefined);
  }
  const config=await api.request('/api/integration?agent=codex');
  assert.match(config.configuration,/\.git@main/);
  assert.doesNotMatch(config.configuration,/feature\/personal-event-guide/);
});
test('guide import validates evidence and URLs and drops unavailable email contacts',()=>{const value=validateGuide(guide());assert.equal(value.event.url,'https://luma.com/example');assert.equal(value.people[0].contact_links.email,undefined);for(const mutate of [g=>g.people[0].sources[0].url='javascript:alert(1)',g=>g.people[0].assessments[0].evidence[0].quote='Invented claim',g=>g.graph.edges[0].target='missing']){const g=guide();mutate(g);assert.throws(()=>validateGuide(g));}});
test('decisions persist across browser sessions',async()=>{const storage=store(),api=create(storage);await api.request('/api/import',guide());await api.request('/api/feedback',{event_id:'event',profile_url:'https://luma.com/user/sample',status:'meet'});const reopened=create(storage);assert.equal((await reopened.request('/api/guide?event=event')).people[0].feedback.status,'meet');});
test('new profile hides stale recommendations but retains original evidence on disk',async()=>{const storage=store(),api=create(storage);await api.request('/api/import',guide());await api.request('/api/onboard',{...brief,interests:['Robotics']});const stale=await api.request('/api/guide?event=event');assert.equal(stale.analysis_stale,true);assert.deepEqual(stale.people,[]);assert.equal(stale.counts.recommended,0);assert.equal(JSON.parse([...storage.values.values()][0]).guides.event.people[0].sources[0].text,'GPU engineer');});
test('quota failures keep the previous workspace usable and API keys are rejected',async()=>{const storage=store(),api=create(storage);await api.request('/api/import',guide());storage.setItem=()=>{throw new Error('Quota exceeded');};await assert.rejects(api.request('/api/feedback',{event_id:'event',profile_url:'https://luma.com/user/sample',status:'meet'}));assert.equal((await api.request('/api/guide?event=event')).people[0].feedback.status,'none');await assert.rejects(api.request('/api/settings',{api_key:'secret'}));});
test('graph presentation keeps evidence and omits disconnected nodes',()=>{const g=guide(),rows=elements(g.graph,g.people);assert.equal(rows.length,3);assert.equal(rows.find(r=>r.data.id==='isolated'),undefined);assert.deepEqual(rows.find(r=>r.data.id==='edge').data.evidence,g.graph.edges[0].evidence);});
