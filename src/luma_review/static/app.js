/* Local UI and self-contained, read-only event guides. No remote assets. */
(() => {
  'use strict';
  const exported = window.__EXPORTED_GUIDE__ || null;
  const token = exported ? '' : JSON.parse(document.getElementById('bootstrap').textContent).token;
  const app = document.getElementById('app');
  let state = {brief:null, events:[], questions:[], job:{}}, guide = exported;
  let eventId = exported?.event_id || '', view = 'guide', filter = 'recommended', query = '', polling = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const short = (value,n=170) => String(value || '').length > n ? String(value).slice(0,n-1)+'…' : String(value || '');
  const initials = name => name.replace(/\s*\(demo\)/g,'').split(/\s+/).slice(0,2).map(p=>p[0]).join('');
  const isRecommended = p => ['Preference match','Meets required criteria'].includes(p.score.status) && p.feedback.status!=='not_relevant';
  function toast(message) { const element=document.getElementById('toast'); element.textContent=message; element.style.display='block'; setTimeout(()=>element.style.display='none',4500); }
  async function api(path, data) {
    const response=await fetch(path,data ? {method:'POST',headers:{'Content-Type':'application/json','X-Luma-Token':token},body:JSON.stringify(data)} : {});
    const value=await response.json(); if(!response.ok) throw new Error(value.error || 'The request could not be completed.'); return value;
  }
  const bind = (id, event, handler) => { const element=document.getElementById(id); if(element) element.addEventListener(event,handler); };
  async function refresh() {
    if(exported) { state={brief:guide.brief,events:[{event_id:guide.event_id,event:guide.event}],questions:[],criteria_markdown:guide.criteria_markdown,job:{}}; render(); return; }
    state=await api('/api/state');
    if(state.events.length && !state.events.some(e=>e.event_id===eventId)) eventId=state.events[state.events.length-1].event_id;
    guide=eventId && state.brief ? await api('/api/guide?event='+encodeURIComponent(eventId)) : null;
    render();
    if(state.job.running && !polling) polling=setInterval(()=>refresh().catch(e=>toast(e.message)),2000);
    if(!state.job.running && polling) { clearInterval(polling); polling=null; }
  }
  function header() {
    return `<header class="topbar"><a class="brand" href="#" id="home"><span class="mark">↗</span>Luma Profile Review</a><div class="top-actions"><span class="local-badge">${exported?'Your event guide':'Local workspace'}</span>${!exported?'<button class="text-button" id="edit-brief">Your brief</button>':''}</div></header>${guide?.demo?'<div class="demo-banner">FICTIONAL DEMO · Profiles, sources, and recommendations are curated examples. No live inference.</div>':''}`;
  }
  function render() {
    app.innerHTML=header()+(!state.brief || view==='onboard' ? onboarding() : shell());
    bind('home','click',e=>{e.preventDefault();view='guide';render();});
    bind('edit-brief','click',()=>{view='onboard';render();window.scrollTo(0,0);});
    if(!state.brief || view==='onboard') bindOnboarding(); else bindShell();
  }
  function onboarding() {
    const brief=state.brief||{};
    return `<main class="onboard"><section class="onboard-aside"><div class="eyebrow">Better conversations start here</div><h1>Make the room<br>feel smaller.</h1><p class="intro">San Francisco has no shortage of events. Find the people who make showing up worthwhile.</p><p class="intro">Five short answers give your event guide a purpose: who to meet, why it matters, and where to start the conversation.</p><div class="promise">Your priorities are editable.<br>Every suggestion links back to its sources.<br>Missing information stays visible.</div>${!state.brief?'<button class="text-button" id="try-demo">Explore a fictional sample guide ↗</button>':''}</section><form id="onboard-form" class="onboard-form">${state.questions.map((q,i)=>`<div class="question"><label for="q-${q.id}"><span class="number">0${i+1}</span>${esc(q.label)}</label>${q.id==='interests'?`<input id="q-${q.id}" name="${q.id}" type="text" required maxlength="3000" value="${esc((brief.interests||[]).join(', '))}" placeholder="LLM inference, climate tech, developer tools…">`:`<textarea id="q-${q.id}" name="${q.id}" required maxlength="3000">${esc(brief[q.id]||'')}</textarea>`}<span class="hint">${esc(q.hint)}</span></div>`).join('')}<details><summary>Any indispensable requirements? <span class="muted">Optional</span></summary><textarea name="must_haves" aria-label="Indispensable requirements" placeholder="Only add conditions someone must meet. One per line.">${esc((brief.must_haves||[]).join('\n'))}</textarea><span class="hint">Everything else becomes an editable preference, not a hard filter.</span></details><button class="primary" type="submit">${state.brief?'Update my brief':'Create my event brief'} →</button><span class="hint">Your brief is stored locally. A selected cloud model receives the excerpts and context needed for analysis.</span></form></main>`;
  }
  function bindOnboarding() {
    bind('onboard-form','submit',async e=>{
      e.preventDefault(); const button=e.target.querySelector('button[type=submit]');button.disabled=true;
      try { const answers=Object.fromEntries(new FormData(e.target));await api('/api/onboard',answers);view='guide';await refresh();toast('Your brief is ready. You can refine the matching criteria anytime.'); }
      catch(error){toast(error.message);button.disabled=false;}
    });
    bind('try-demo','click',async()=>{try{const result=await api('/api/demo',{});eventId=result.event_id;await refresh();}catch(e){toast(e.message);}});
  }
  function shell() {
    const brief=state.brief;
    const options=state.events.map(e=>`<option value="${esc(e.event_id)}" ${e.event_id===eventId?'selected':''}>${esc(e.event.name)}</option>`).join('');
    const counts=guide?.counts||{};
    return `<div class="layout"><aside class="sidebar"><div class="section-label">Your north star</div><h3>${esc(short(brief.looking_for,130))}</h3><p class="muted">${esc(short(brief.work,160))}</p><div class="chips">${brief.interests.map(i=>`<span class="chip">${esc(i)}</span>`).join('')}</div><hr><label class="section-label" for="event-select">Your events</label>${options?`<select id="event-select">${options}</select>`:'<p class="muted">Your first event starts here.</p>'}<nav class="side-nav"><button id="nav-guide" class="${view==='guide'?'active':''}">Your people <span class="count">${counts.recommended||0}</span></button><button id="nav-graph" class="${view==='graph'?'active':''}">Shared context <span class="count">${guide?.graph.shared_contexts.length||0}</span></button><button id="nav-criteria" class="${view==='criteria'?'active':''}">Matching preferences</button></nav>${!exported?'<button class="primary" id="new-event">+ Add an event</button>':''}<p class="readonly-note">${exported?'Read-only export. Original source pages may change.':'Sources and feedback stay in this local workspace.'}</p></aside><main class="main">${view==='new-event'||!eventId?newEvent():view==='graph'?graphView():view==='criteria'?criteriaView():guideView()}</main></div>`;
  }
  function newEvent() {
    return `<div class="eyebrow">Your next room</div><h1>Which event are you heading to?</h1><p class="lede">Add the Luma event, then let your connected agent collect the accessible attendee profiles and professional sources.</p><div class="empty"><h2>Start with an event link</h2><form id="event-form" class="event-form"><label class="hint" for="event-url">Luma event URL</label><input id="event-url" name="url" type="url" required placeholder="https://luma.com/your-event"><label class="hint" for="event-name">Event name <span class="muted">optional</span></label><input id="event-name" name="name" type="text" placeholder="A name you’ll recognize"><button type="submit" class="primary">Add event →</button></form><p class="small">The tool works with profiles your account can access.</p></div>`;
  }
  function guideView() {
    if(!guide) return '<div class="empty">Add an event to build your guide.</div>';
    const c=guide.counts, job=state.job;
    return `<div class="event-heading"><div class="eyebrow">Your personal event guide</div>${exported?'':`<a class="quiet-link" href="/api/export?event=${encodeURIComponent(eventId)}">Export guide ↗</a>`}</div><h1>A few good conversations.</h1><p class="lede">${esc(guide.event.name)}<br>Find people relevant to ${esc(short(state.brief.looking_for,130)).replace(/\.$/,'')}.</p><div class="stats"><div class="stat"><strong>${c.recommended}</strong><span>suggested connections</span></div><div class="stat"><strong>${c.captured}</strong><span>profiles captured</span></div><div class="stat"><strong>${c.with_sources}</strong><span>with readable sources</span></div><div class="stat"><strong>${c.reviewed}</strong><span>reviewed</span></div></div>${job.running?`<div class="notice running" role="status">Preparing your guide · ${esc(job.stage||'starting')} ${job.current||0}/${job.total||'…'}. You can keep exploring.</div>`:''}${job.error?`<div class="notice error">${esc(job.error)}</div>`:''}${Object.keys(guide.errors||{}).length?`<details class="notice error"><summary>Some profiles could not be analyzed</summary>${Object.values(guide.errors).map(e=>`<p>${esc(e)}</p>`).join('')}</details>`:''}${c.captured&&!exported?`<div class="row"><button id="collect-agent">Collect & enrich with my agent ↗</button><button id="analyze" ${job.running?'disabled':''}>${c.reviewed?'Refresh analysis':'Prepare my guide'}</button></div>`:''}${!c.captured?`<div class="empty"><h2>Your guide begins with the people.</h2><p>Connect your agent to collect the guest list, open profiles,<br>and read the professional sources relevant to your brief.</p>${!exported?'<button class="primary" id="collect-agent">Collect with my agent →</button>':''}</div>`:`<div class="toolbar"><div class="filters">${[['recommended','Suggested'],['verify','Needs checking'],['saved','Saved'],['all','All reviewed']].map(([id,label])=>`<button class="filter ${filter===id?'active':''}" data-filter="${id}">${label}</button>`).join('')}</div><input class="search" id="search" type="text" aria-label="Search people" placeholder="Search names, topics, reasons…" value="${esc(query)}"></div><div class="cards" id="cards">${cardsView()}</div>`}<p class="footer-note">${esc(guide.event.collection_scope)} ${guide.event.roster_complete?'':'The accessible attendee list has not yet been marked complete.'} Suggestions reflect available professional evidence, not willingness to meet or collaborate.</p>`;
  }
  function cardsView() {
    const people=guide.people.filter(p=> (filter==='all'||filter==='recommended'&&isRecommended(p)||filter==='verify'&&p.score.status==='Needs verification'||filter==='saved'&&['saved','met'].includes(p.feedback.status)) && JSON.stringify([p.name,p.summary,p.why,p.professional?.facts]).toLowerCase().includes(query.toLowerCase()));
    if(!people.length) return `<div class="empty">${guide.counts.reviewed?'No reviewed profiles match this view. Try another filter or refine your brief.':'The profiles are ready for research. Collect source excerpts, then prepare your guide.'}</div>`;
    return people.map((p,index)=>{
      const check=p.score.status==='Needs verification',out=p.score.status==='Outside criteria',unmatched=p.score.status==='No preferences matched',sources=Object.fromEntries(p.sources.map(s=>[s.id,s]));
      const topics=(p.professional?.facts||[]).filter(f=>['interest','skill','project'].includes(f.kind)).slice(0,3);
      return `<article class="person-card"><div class="person-top"><div class="avatar a${index%3}">${esc(initials(p.name))}</div><div class="person-title"><h2><a href="${esc(p.profile_url)}" target="_blank" rel="noreferrer">${esc(p.name)} ↗</a></h2><div class="small muted">${esc(short((p.professional?.facts||[]).filter(f=>['role','organization'].includes(f.kind)).map(f=>f.value).join(' · '),100)||'Professional background not yet established')}</div></div><span class="badge ${check?'check':out||unmatched?'out':''}">${check?'Needs verification':out?'Outside required criteria':unmatched?'No preferences matched':'Relevant to your brief'}</span></div><p class="person-summary">${esc(short(p.summary,245))}</p>${p.why.length?`<ul class="reasons">${p.why.slice(0,2).map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`:''}<div class="chips">${topics.map(t=>`<span class="chip">${esc(t.value)}</span>`).join('')}</div><div class="person-bottom"><span class="small">${p.score.known_criteria}/${p.score.total_criteria} criteria have conclusive evidence · ${p.sources.length} source${p.sources.length===1?'':'s'}</span>${!exported?`<div class="feedback"><button data-feedback="saved" data-person="${esc(p.profile_url)}" class="${p.feedback.status==='saved'?'chosen':''}">${p.feedback.status==='saved'?'Saved ✓':'Save'}</button><button data-feedback="met" data-person="${esc(p.profile_url)}" class="${p.feedback.status==='met'?'chosen':''}">Met</button><button data-feedback="not_relevant" data-person="${esc(p.profile_url)}" class="${p.feedback.status==='not_relevant'?'chosen':''}">Not relevant</button></div>`:''}</div><details><summary>Why meet, what to ask, and supporting sources</summary><div class="details-content"><div class="conversation"><strong>A place to start</strong><br>${esc(p.conversation_starter)}<br><span class="muted">You can bring: ${esc(p.your_contribution)}</span></div>${p.uncertainties.length?`<p><strong>Still worth checking</strong></p><ul>${p.uncertainties.map(u=>`<li>${esc(u)}</li>`).join('')}</ul>`:''}<div class="evidence-list">${p.assessments.map(a=>`<div class="evidence-row"><b>${esc(a.criterion_id)} · ${esc(a.verdict)}</b><br>${esc(a.reason)}${a.evidence.map(e=>`<blockquote>“${esc(e.quote)}”<br><a href="${esc(sources[e.source_id]?.url)}" target="_blank" rel="noreferrer">${esc(sources[e.source_id]?.title)} ↗</a> · ${esc((sources[e.source_id]?.retrieved_at||'').slice(0,10))}</blockquote>`).join('')}</div>`).join('')}</div></div></details></article>`;
    }).join('');
  }
  function graphView() {
    if(!guide) return '<div class="empty">Add an event to explore shared context.</div>';
    const graph=guide.graph,nodes=graph.nodes,people=nodes.filter(n=>n.type==='person'),contexts=nodes.filter(n=>!['person','user'].includes(n.type)).slice(0,30);
    const height=Math.max(460,people.length*64+30,contexts.length*58+30),positions={'user:self':[65,height/2]};
    people.forEach((n,i)=>positions[n.id]=[330,45+i*64]);contexts.forEach((n,i)=>positions[n.id]=[665,35+i*58]);
    const color=n=>n.type==='topic'?'#de875f':n.type==='organization'?'#75a183':n.type==='project'?'#bdad82':n.type==='user'?'#dc6d49':'#496576';
    const svg=`<svg viewBox="0 0 900 ${height}" role="group" aria-label="Professional context graph: people linked to documented topics, organizations, and projects"><title>Shared professional context</title>${graph.edges.filter(e=>positions[e.source]&&positions[e.target]).map(e=>`<line class="graph-line" x1="${positions[e.source][0]}" y1="${positions[e.source][1]}" x2="${positions[e.target][0]}" y2="${positions[e.target][1]}"><title>${esc(e.type)}</title></line>`).join('')}${nodes.filter(n=>positions[n.id]).map(n=>`<g class="graph-node" data-node="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(n.label)}"><circle cx="${positions[n.id][0]}" cy="${positions[n.id][1]}" r="${n.type==='user'?17:10}" fill="${color(n)}"></circle><text class="graph-label" x="${positions[n.id][0]+19}" y="${positions[n.id][1]+4}">${esc(short(n.label.replace(' (demo)',''),28))}</text></g>`).join('')}</svg>`;
    return `<div class="eyebrow">The context behind a connection</div><h1>Find a useful way in.</h1><p class="lede">Explore common professional interests, organizations, and projects. Shared context gives you something to discuss; it does not mean two people know each other.</p><div class="graph-wrap"><div class="legend"><span><i style="background:#496576"></i>People</span><span><i style="background:#de875f"></i>Topics</span><span><i style="background:#75a183"></i>Organizations</span><span><i style="background:#bdad82"></i>Projects</span></div>${svg}<div id="graph-selection" class="notice">Select a node to see its documented context.</div></div><div class="shared-contexts">${graph.shared_contexts.map(c=>`<div class="context-card"><strong>${esc(c.context.label)}</strong>${c.people.map(id=>esc(nodes.find(n=>n.id===id)?.label||id)).join(' · ')}<div class="hint">Shared context, not a verified personal connection.</div></div>`).join('')}</div><p class="footer-note">${nodes.length} nodes · ${graph.edges.length} evidence-linked edges. The graph does not use popularity to rank recommendations.</p>`;
  }
  function criteriaView() {
    return `<div class="eyebrow">Your definition of a good conversation</div><h1>Keep the guide yours.</h1><p class="lede">These preferences come from your onboarding answers. Adjust the wording and weights, or add a required condition when it really is indispensable. Updating them makes previous assessments stale until you analyze again.</p><textarea id="criteria-editor" class="criteria-editor" aria-label="Matching criteria Markdown" ${exported?'readonly':''}>${esc(state.criteria_markdown||guide?.criteria_markdown||'')}</textarea>${!exported?'<button class="primary" id="save-criteria" style="margin-top:15px">Save preferences</button>':''}`;
  }
  function bindShell() {
    for(const name of ['guide','graph','criteria']) bind('nav-'+name,'click',()=>{view=name;render();window.scrollTo(0,0);});
    bind('new-event','click',()=>{view='new-event';render();window.scrollTo(0,0);});
    bind('event-select','change',async e=>{eventId=e.target.value;view='guide';await refresh();});
    bind('event-form','submit',async e=>{e.preventDefault();try{const data=Object.fromEntries(new FormData(e.target));const result=await api('/api/events',data);eventId=result.event_id;view='guide';await refresh();}catch(error){toast(error.message);}});
    bind('collect-agent','click',()=>agentModal().catch(e=>toast(e.message)));
    bind('analyze','click',analysisModal);
    bind('save-criteria','click',async()=>{try{await api('/api/criteria',{markdown:document.getElementById('criteria-editor').value});await refresh();toast('Preferences saved. Prepare your guide again to apply them.');}catch(e){toast(e.message);}});
    document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;render();}));
    bind('search','input',e=>{query=e.target.value;document.getElementById('cards').innerHTML=cardsView();bindCards();});
    bindCards();
    document.querySelectorAll('[data-node]').forEach(element=>{
      const select=()=>{
        const id=element.dataset.node,graph=guide.graph,node=graph.nodes.find(n=>n.id===id);
        const edges=graph.edges.filter(e=>e.source===id||e.target===id);
        document.getElementById('graph-selection').innerHTML=`<strong>${esc(node.label)}</strong><br>${edges.map(e=>`${esc(e.type.replaceAll('_',' '))}: ${esc(graph.nodes.find(n=>n.id===(e.source===id?e.target:e.source))?.label||'')}<div class="graph-evidence">${e.evidence.map(ref=>ref.source_url?`<a href="${esc(ref.source_url)}" target="_blank" rel="noreferrer">${esc(ref.quote)} ↗</a>`:'From your onboarding brief').join('<br>')}</div>`).join('<br>')||'No established professional context yet.'}`;
      };
      element.addEventListener('click',select);element.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});
    });
  }
  function bindCards() {
    document.querySelectorAll('[data-feedback]').forEach(b=>b.addEventListener('click',async()=>{try{await api('/api/feedback',{event_id:eventId,profile_url:b.dataset.person,status:guide.people.find(p=>p.profile_url===b.dataset.person)?.feedback.status===b.dataset.feedback?'none':b.dataset.feedback});await refresh();}catch(e){toast(e.message);}}));
  }
  function modal(content) {
    document.querySelector('.modal-backdrop')?.remove();
    const background=document.createElement('div');background.className='modal-backdrop';
    background.innerHTML=`<section class="modal" role="dialog" aria-modal="true" aria-label="Event workflow"><button class="close" aria-label="Close dialog">×</button>${content}</section>`;
    document.body.append(background);background.querySelector('.close').addEventListener('click',()=>background.remove());
    background.addEventListener('click',e=>{if(e.target===background)background.remove();});background.querySelector('button').focus();
    background.addEventListener('keydown',e=>{if(e.key==='Escape')background.remove();});
    return background;
  }
  async function agentModal() {
    const dialog=modal(`<h2>Bring your agent to the room.</h2><p>Your agent can use its browser to collect the accessible Luma guest list, follow relevant professional links, and build your guide. Progress and sources are saved as it goes.</p><label for="agent-choice">Your agent</label><select id="agent-choice"><option value="codex">Codex</option><option value="claude">Claude Code</option><option value="cursor">Cursor</option><option value="copilot">GitHub Copilot / VS Code</option><option value="opencode">OpenCode</option><option value="claude-desktop">Claude Desktop</option></select><div id="agent-config"></div><button class="primary" id="copy-assignment">Copy the event task</button><p class="hint">Requires this local MCP server and browser tools in your agent. The tool does not bypass restricted profiles or guest lists.</p><details class="import-area"><summary>Already have a participant snapshot?</summary><label for="import-file">Import a version 1 profile JSON file</label><input id="import-file" type="file" accept="application/json,.json"></details>`);
    async function config() {const value=await api('/api/integration?agent='+dialog.querySelector('#agent-choice').value);dialog.querySelector('#agent-config').innerHTML=`<details><summary class="small">One-time MCP setup · ${esc(value.location)}</summary><p>Install this project's MCP extra, then add this server configuration to your agent.</p><pre>${esc(value.configuration)}</pre></details><p class="hint">The same workspace is shared with this local guide.</p>`;}
    dialog.querySelector('#agent-choice').addEventListener('change',()=>config().catch(e=>toast(e.message)));
    dialog.querySelector('#copy-assignment').addEventListener('click',async()=>{const request=`Use the Luma Profile Review MCP tools and shared skill. My professional brief is already saved. Collect the accessible attendee list for ${guide.event.url}. Resume event ${eventId}; read Luma profiles and relevant linked LinkedIn, GitHub, company, and personal pages using your browser tools. Save excerpts and access limitations, structure each profile with evidence, then match against my criteria using your current model. Do not infer personal relationships from a shared company or event. Return my personalized event guide with sources and collection coverage.`;try{await navigator.clipboard.writeText(request);toast('Event task copied. Paste it into your connected agent.');}catch{const area=document.createElement('textarea');area.value=request;dialog.querySelector('.modal').append(area);area.select();toast('Copy the selected task into your agent.');}});
    dialog.querySelector('#import-file').addEventListener('change',async e=>{try{const value=JSON.parse(await e.target.files[0].text());const result=await api('/api/import',value);eventId=result.event_id;dialog.remove();await refresh();toast('Participant snapshot imported.');}catch(error){toast(error.message);}});
    await config();
  }
  function analysisModal() {
    const dialog=modal(`<h2>Prepare your conversations.</h2><p>Analysis uses the sources already collected for this event. It structures professional facts and evaluates your criteria. Cloud backends receive these excerpts and your brief.</p><label for="backend">Where to run the analysis</label><select id="backend"><option value="codex">Codex CLI · saved login</option><option value="claude">Claude Code · saved login</option><option value="ollama">Ollama · local model</option></select><label for="model">Model <span class="muted">optional for Codex or Claude</span></label><input id="model" type="text" placeholder="Use the CLI default, or enter an installed Ollama model"><button class="primary" id="start-analysis" style="margin-top:20px">Build my guide →</button><p class="hint">To use your current agent's model, choose “Collect & enrich with my agent” instead.</p>`);
    dialog.querySelector('#start-analysis').addEventListener('click',async e=>{e.target.disabled=true;try{await api('/api/analyze',{event_id:eventId,backend:dialog.querySelector('#backend').value,model:dialog.querySelector('#model').value||null});dialog.remove();await refresh();}catch(error){toast(error.message);e.target.disabled=false;}});
  }
  refresh().catch(error=>{app.innerHTML=`<main class="empty"><h2>Your local guide could not load.</h2><p>${esc(error.message)}</p></main>`;});
})();
