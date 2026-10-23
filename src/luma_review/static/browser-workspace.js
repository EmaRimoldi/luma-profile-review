/* Hosted workspace: browser-only storage, no account database, keys, or model proxy. */
(function(root){
  'use strict';
  const KEY='people-for-luma.workspace.v1';
  const QUESTIONS=[
    {id:'work',label:'What are you working on?',hint:'Your role, project, or company in one sentence.'},
    {id:'interests',label:'What catches your curiosity?',hint:'A few professional topics you could talk about for hours.'},
    {id:'looking_for',label:'What would make this event worthwhile?',hint:'A collaborator, feedback, customers, or a fresh perspective.'},
    {id:'connect_with',label:'Who would you love to meet?',hint:'The roles, experience, or backgrounds that matter to you.'},
    {id:'can_offer',label:'What can you bring to the conversation?',hint:'Experience, useful feedback, an introduction, or something to build together.'}
  ];
  const clone=value=>JSON.parse(JSON.stringify(value));
  // Older onboarding added this unused tag without asking the user. Keep IDs and reviewed work.
  const cleanLegacyBrief=brief=>{if(brief?.region==='San Francisco Bay Area'){const {region,...rest}=brief;return rest;}return brief;};
  function url(value,luma=false){const parsed=new URL(value);if(!['https:','http:'].includes(parsed.protocol)||parsed.username||parsed.password)throw new Error('Use a valid HTTP(S) link.');if(luma&&!['luma.com','lu.ma','www.luma.com'].includes(parsed.hostname))throw new Error('Use a Luma event link.');if(luma){parsed.hostname='luma.com';parsed.protocol='https:';parsed.search='';parsed.hash='';}return parsed.href.replace(/\/$/,'');}
  function criteria(brief){
    const cell=v=>String(v).replace(/\|/g,'\\|').replace(/[\r\n]+/g,' ');
    const rows=['# My networking brief','','Status: active','','## Context','',`My work: ${brief.work}`,'',`My goal: ${brief.looking_for}`,'',`People I hope to meet: ${brief.connect_with}`,'',`What I can offer: ${brief.can_offer}`,'','## Criteria','','| ID | Type | Weight | Criterion | Required evidence |','| --- | --- | --- | --- | --- |'];
    brief.must_haves.forEach((v,i)=>rows.push(`| M${i+1} | must | 0 | ${cell(v)} | Explicit professional evidence; missing information is unknown |`));
    const preferences=[['P1',4,'Professional work or interests relevant to: '+brief.interests.join(', ')],['P2',5,'Background relevant to: '+brief.connect_with],['P3',5,'Experience that could contribute to: '+brief.looking_for],['P4',2,'Professional context where my contribution may be useful: '+brief.can_offer]];
    for(const [id,weight,condition] of preferences)rows.push(`| ${id} | prefer | ${weight} | ${cell(condition)} | A specific role, project, or declared professional activity; no inferred willingness |`);
    rows.push('','## Rules','','Apply a geographic preference only when I explicitly state one in my answers or criteria.','Use English for summaries and reasons. Preserve source quotes verbatim. Missing evidence means unknown, not no. Shared context does not establish a personal relationship.');return rows.join('\n')+'\n';
  }
  function makeBrief(value){
    const brief={version:1,id:'browser-profile'};
    for(const q of QUESTIONS){let answer=value[q.id];if(q.id==='interests'){answer=Array.isArray(answer)?answer:String(answer||'').split(',');brief.interests=[...new Set(answer.map(s=>String(s).trim()).filter(Boolean))];if(!brief.interests.length||brief.interests.length>20)throw new Error('Add between one and twenty interests.');}else{if(typeof answer!=='string'||!answer.trim()||answer.length>3000)throw new Error('Add a short answer to each question.');brief[q.id]=answer.trim();}}
    brief.must_haves=Array.isArray(value.must_haves)?value.must_haves:String(value.must_haves||'').split('\n').map(s=>s.trim()).filter(Boolean);if(brief.must_haves.length>20||brief.must_haves.some(v=>typeof v!=='string'||!v.trim()||v.length>3000))throw new Error('Keep must-have criteria below twenty.');return brief;
  }
  function validateGuide(value){
    if(!value||!Array.isArray(value.people)||!value.event||!value.brief||!value.graph||!Array.isArray(value.graph.nodes)||!Array.isArray(value.graph.edges)||typeof value.criteria_markdown!=='string')throw new Error('Choose a reviewed guide JSON, exported by your agent or the local app.');
    const guide=clone(value);guide.event.url=url(guide.event.url,true);makeBrief(guide.brief);guide.brief=cleanLegacyBrief(guide.brief);
    if(!guide.event_id||!guide.people.length||guide.people.length>10000)throw new Error('The guide needs an event ID and reviewed profiles.');
    const seen=new Set(),statuses=['Preference match','Meets required criteria','Needs verification','No preferences matched','Outside criteria'];
    for(const p of guide.people){
      const original=clone(p);p.profile_url=url(p.profile_url,true);if(!new URL(p.profile_url).pathname.startsWith('/user/')||seen.has(p.profile_url))throw new Error('Each person needs a unique Luma profile.');seen.add(p.profile_url);
      if(typeof p.name!=='string'||typeof p.summary!=='string'||!Array.isArray(p.why)||!Array.isArray(p.sources)||!Array.isArray(p.assessments)||!statuses.includes(p.score?.status))throw new Error('The file is missing reviewed profile details.');
      if(p.photo_url)p.photo_url=url(p.photo_url);p.contact_links={};
      for(const source of p.sources)source.url=url(source.url);
      for(const link of original.outbound_links||[]){const u=new URL(url(link));if(u.hostname.replace(/^www\./,'')==='linkedin.com'&&u.pathname.startsWith('/in/'))p.contact_links.linkedin=u.href;if(['x.com','twitter.com'].includes(u.hostname.replace(/^www\./,'')))p.contact_links.x=u.href;}
      const supplied=original.contact_links||{};
      for(const kind of ['linkedin','x'])if(supplied[kind]){const u=new URL(url(supplied[kind])),host=u.hostname.replace(/^www\./,'');if((kind==='linkedin'?['linkedin.com']:['x.com','twitter.com']).includes(host))p.contact_links[kind]=u.href;}
      p.uncertainties=Array.isArray(p.uncertainties)?p.uncertainties:[];p.feedback={status:'none'};
      const sources=new Map(p.sources.map(s=>[s.id,s]));
      for(const assessment of p.assessments){if(!Array.isArray(assessment.evidence))throw new Error('Each assessment needs an evidence list.');for(const ref of assessment.evidence){const source=sources.get(ref.source_id);if(!source||typeof ref.quote!=='string'||!String(source.text).replace(/\s+/g,' ').includes(ref.quote.replace(/\s+/g,' ')))throw new Error('A cited quote is missing from its source.');}}
    }
    const ids=new Set(guide.graph.nodes.map(n=>n.id));for(const edge of guide.graph.edges){if(!ids.has(edge.source)||!ids.has(edge.target))throw new Error('A graph edge references a missing node.');for(const ref of edge.evidence||[])if(ref.source_url)ref.source_url=url(ref.source_url);}
    guide.analysis_stale=false;guide.counts={...guide.counts,reviewed:guide.people.length};return guide;
  }
  function create(storage,fetcher){
    let current;try{current=JSON.parse(storage.getItem(KEY)||'null');}catch{}current=current||{brief:null,events:[],guides:{},settings:{backend:'agent',model:'',luma:'browser',setup_complete:true}};
    current.brief=cleanLegacyBrief(current.brief);for(const guide of Object.values(current.guides))guide.brief=cleanLegacyBrief(guide.brief);
    function save(next){storage.setItem(KEY,JSON.stringify(next));current=next;}
    async function request(path,data){
      const next=clone(current),parsed=new URL(path,'https://people.example'),route=parsed.pathname;
      if(data===undefined){
        if(route==='/api/state')return clone({brief:current.brief,events:current.events,settings:current.settings,questions:QUESTIONS,job:{},criteria_markdown:current.criteria_markdown||'',connections:{}});
        if(route==='/api/guide'||route==='/api/export'){const id=parsed.searchParams.get('event');if(!current.guides[id])throw new Error('Add an event first.');const g=clone(current.guides[id]);if(g.analysis_stale){g.brief=current.brief;g.criteria_markdown=current.criteria_markdown;g.people=[];g.counts.reviewed=0;g.counts.recommended=0;g.graph={nodes:[],edges:[],shared_contexts:[]};}return g;}
        if(route==='/api/integration'){
          const agent=parsed.searchParams.get('agent'),args=['--python','3.13','--from','luma-profile-review[mcp] @ git+https://github.com/EmaRimoldi/luma-profile-review.git@main','luma-review','mcp'];
          const server={command:'uvx',args};let config=agent==='copilot'?{servers:{people_for_luma:{type:'stdio',...server}}}:agent==='opencode'?{mcp:{people_for_luma:{type:'local',command:['uvx',...args],enabled:true}}}:{mcpServers:{people_for_luma:server}};
          return {location:'Your agent’s MCP settings · requires uv',configuration:agent==='codex'?'[mcp_servers.people_for_luma]\ncommand = "uvx"\nargs = '+JSON.stringify(args):JSON.stringify(config,null,2)};
        }
        throw new Error('This action needs the local companion.');
      }
      if(route==='/api/onboard'){next.brief=makeBrief(data);next.criteria_markdown=criteria(next.brief);for(const g of Object.values(next.guides)){g.analysis_stale=true;}save(next);return clone({brief:next.brief});}
      if(route==='/api/settings'){if(data.backend&&data.backend!=='agent'||data.api_key)throw new Error('Use the local companion for CLI logins or API keys.');next.settings={...next.settings,...data};save(next);return clone({settings:next.settings,connections:{}});}
      if(route==='/api/events'){
        const eventUrl=url(data.url,true),event_id='web-'+Array.from(new TextEncoder().encode(new URL(eventUrl).pathname)).map(v=>v.toString(16).padStart(2,'0')).join('');
        const event={name:data.name||'Your next event',url:eventUrl,collection_scope:'Collect the accessible guest list with your agent.',roster_complete:false};
        if(!next.guides[event_id]){next.events.push({event_id,event,captured:0});next.guides[event_id]={event_id,event,brief:next.brief,criteria_markdown:next.criteria_markdown,people:[],counts:{captured:0,reviewed:0,with_sources:0,recommended:0},graph:{nodes:[],edges:[],shared_contexts:[]},errors:{}};}save(next);return clone({event_id,event});
      }
      if(route==='/api/import'){
        const guide=validateGuide(data);if(JSON.stringify(next.brief)!==JSON.stringify(guide.brief)||next.criteria_markdown!==guide.criteria_markdown)for(const old of Object.values(next.guides))old.analysis_stale=true;next.brief=guide.brief;next.criteria_markdown=guide.criteria_markdown;next.guides[guide.event_id]=guide;next.events=next.events.filter(e=>e.event_id!==guide.event_id);next.events.push({event_id:guide.event_id,event:guide.event,captured:guide.counts.captured});next.settings.setup_complete=true;save(next);return {event_id:guide.event_id};
      }
      if(route==='/api/feedback'){
        if(!['none','saved','meet','met','not_relevant'].includes(data.status))throw new Error('Unknown choice.');const p=next.guides[data.event_id]?.people.find(p=>p.profile_url===data.profile_url);if(!p)throw new Error('That person is not in this guide.');p.feedback={status:data.status,note:data.note||''};save(next);return {saved:true};
      }
      if(route==='/api/criteria'){next.criteria_markdown=data.markdown;for(const g of Object.values(next.guides)){g.analysis_stale=true;}save(next);return {saved:true};}
      if(route==='/api/demo'){if(next.brief||next.events.length)throw new Error('The sample opens in an empty browser workspace.');const response=await fetcher('/demo.json');if(!response.ok)throw new Error('The sample could not load.');const demo=validateGuide(await response.json());next.brief=demo.brief;next.criteria_markdown=demo.criteria_markdown;next.guides[demo.event_id]=demo;next.events=[{event_id:demo.event_id,event:demo.event,captured:demo.counts.captured}];save(next);return {event_id:demo.event_id};}
      throw new Error('Run the local companion to prepare new profiles, then import the reviewed guide here.');
    }
    return {request};
  }
  const api={create,validateGuide,makeBrief,criteria,QUESTIONS};if(typeof module!=='undefined'&&module.exports)module.exports=api;else if(root.__BROWSER_WORKSPACE__)root.PeopleBrowserWorkspace=create(root.localStorage,root.fetch.bind(root));
})(typeof window==='undefined'?this:window);
