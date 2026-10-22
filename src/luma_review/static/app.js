/* Local discovery, onboarding, and portable guides. No UI framework or build step. */
(() => {
  'use strict';
  const exported = window.__EXPORTED_GUIDE__ || null;
  const token = exported ? '' : JSON.parse(document.getElementById('bootstrap').textContent).token;
  const app = document.getElementById('app');
  let state = {brief:null, events:[], questions:[], job:{}, settings:{backend:'agent',model:''}, connections:{}}, guide = exported;
  let eventId = exported?.event_id || '', view = 'discover', mode = 'stack', query = '', filter = 'suggested';
  let step = 0, answers = {}, editing = false, searchIndex = null, visibleLimit = 20, polling = null;
  let stackOffset = 0, lastBrowseWheel = 0;
  let undo = null, feedbackQueue = Promise.resolve(), pendingWrites = 0, pollBusy = false;
  const icons = {
    spark:'<path d="m12 2 2.6 7.4L22 12l-7.4 2.6L12 22l-2.6-7.4L2 12l7.4-2.6Z"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    save:'<path d="M6 4h12v17l-6-4-6 4Z"/>', meet:'<path d="m7 13 3 3 7-8"/><circle cx="12" cy="12" r="9"/>',
    close:'<path d="m6 6 12 12M6 18 18 6"/>', arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    back:'<path d="M20 12H4m6-6-6 6 6 6"/>', out:'<path d="M8 5h11v11M19 5 5 19"/>',
    user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
    mail:'<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
    linkedin:'<path d="M5 9v11M5 4v.5M10 20V9h4v2c1-3 6-3 6 1v8M14 12v8"/>',
    x:'<path d="m4 3 16 18h-4L0 3h4M20 3 4 21" transform="translate(2 0) scale(.9 1)"/>',
    cards:'<rect x="5" y="3" width="14" height="18" rx="3"/><path d="M2 7v10M22 7v10"/>',
    list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    graph:'<circle cx="5" cy="12" r="3"/><circle cx="18" cy="5" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8 10 7-4M8 14l7 4"/>',
    event:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6M17 2v6M3 11h18"/>',
    undo:'<path d="M4 10h10a6 6 0 1 1 0 12M4 10l5-5M4 10l5 5"/>'
  };
  const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.spark}</svg>`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const short = (v,n=160) => String(v||'').length>n ? String(v).slice(0,n-1)+'…' : String(v||'');
  const initials = name => String(name).replace(/\s*\(demo\)/g,'').trim().split(/\s+/).slice(0,2).map(p=>p[0]||'').join('');
  const sourceDate = value => value ? new Date(value).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}) : '';
  const recommended = p => ['Preference match','Meets required criteria'].includes(p.score.status);
  const decided = p => ['saved','meet','met','not_relevant'].includes(p.feedback?.status);
  function toast(message, action=null) {
    const el=document.getElementById('toast'); el.replaceChildren(document.createTextNode(message));
    if(action){const b=document.createElement('button');b.textContent='Undo';b.addEventListener('click',action);el.append(b);}
    el.classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.remove('visible'),6500);
  }
  async function api(path,data) {
    const response=await fetch(path,data!==undefined?{method:'POST',headers:{'Content-Type':'application/json','X-Luma-Token':token},body:JSON.stringify(data)}:{});
    const value=await response.json();if(!response.ok)throw new Error(value.error||'Please try again.');return value;
  }
  const bind=(id,event,fn)=>document.getElementById(id)?.addEventListener(event,fn);
  async function refresh() {
    if(exported)state={...state,brief:guide.brief,events:[{event_id:guide.event_id,event:guide.event}],criteria_markdown:guide.criteria_markdown};
    else {
      state=await api('/api/state');
      if(state.events.length&&!state.events.some(e=>e.event_id===eventId))eventId=state.events.at(-1).event_id;
      guide=eventId&&state.brief?await api('/api/guide?event='+encodeURIComponent(eventId)):null;
    }
    searchIndex=guide?new window.ProfileSearch(guide.people):null;
    if(state.brief&&state.settings?.setup_complete===false&&!editing){view='setup';step=6;}
    if(!Object.keys(answers).length&&state.brief)answers={...state.brief,interests:state.brief.interests.join(', ')};
    render();
    if(state.job.running&&!polling)polling=setInterval(async()=>{
      if(pollBusy||pendingWrites)return;pollBusy=true;
      try{const next=await api('/api/state');if(next.job.running){state.job=next.job;const progress=document.getElementById('analysis-progress');if(progress)progress.textContent=`Updating your guide · ${state.job.stage||'starting'} ${state.job.current||0}/${state.job.total||'…'}`;}else await refresh();}catch(e){toast(e.message);}finally{pollBusy=false;}
    },2500);
    if(!state.job.running&&polling){clearInterval(polling);polling=null;}
  }
  function navCount(name){return (guide?.people||[]).filter(p=>name==='saved'?p.feedback.status==='saved':['meet','met'].includes(p.feedback.status)).length;}
  function header() {
    return `<header class="topbar"><a href="#" id="home" class="brand"><span class="brand-mark">${icon('spark')}</span><strong>people</strong><span class="brand-sub">for Luma</span></a>${state.brief?`<nav aria-label="Main navigation">${[['discover','spark','Discover'],['saved','save','Saved'],['meet','meet','Meet'],['graph','graph','Context']].map(([id,i,label])=>`<button data-nav="${id}" class="nav-item ${view===id?'active':''}">${icon(i)}<span>${label}</span>${['saved','meet'].includes(id)&&navCount(id)?`<small>${navCount(id)}</small>`:''}</button>`).join('')}</nav>`:''}<div class="top-actions"><span class="local-dot" title="Local workspace">Local</span>${!exported?`<button id="settings" class="icon-button" aria-label="Connections">${icon('settings')}</button>${state.brief?`<button id="edit-brief" class="profile-button" aria-label="Your profile">${icon('user')}</button>`:''}`:''}</div></header>${guide?.demo?'<div class="demo-banner">FICTIONAL DEMO · Curated profiles and recommendations. No live inference.</div>':''}`;
  }
  function render() {
    const setup=!state.brief||view==='setup';
    app.innerHTML=header()+(setup?setupView():shell());
    bind('home','click',e=>{e.preventDefault();view=state.brief?'discover':'setup';render();});
    bind('edit-brief','click',()=>{editing=true;step=1;answers={...state.brief,interests:state.brief.interests.join(', ')};view='setup';render();});
    bind('settings','click',connectionModal);
    document.querySelectorAll('[data-nav]').forEach(b=>b.addEventListener('click',()=>{view=b.dataset.nav;query='';visibleLimit=20;stackOffset=0;render();}));
    if(setup)bindSetup();else bindShell();
    paintParticles();
  }
  function setupView() {
    const q=state.questions[step-1];
    return `<main class="setup"><aside class="setup-art"><div class="eyebrow">A little more serendipity.</div><h1>Find your<br>kind of people.</h1><canvas class="particle-art" width="480" height="380" aria-hidden="true"></canvas><p>Good conversations start with a little context.</p></aside><section class="setup-panel"><div class="setup-progress"><span>${step===0?'CONNECT':step===6?'YOUR AGENT':`YOUR PROFILE · ${step} OF 5`}</span><div class="progress-dots">${Array.from({length:7},(_,i)=>`<i class="${i<=step?'done':''}"></i>`).join('')}</div></div>${step===0?`<div class="setup-copy"><span class="setup-symbol">${icon('event')}</span><h2>Start with Luma.</h2><p>Sign in on Luma. Your agent uses that browser session.</p><a class="primary full" href="https://luma.com/signin" target="_blank" rel="noreferrer">Open Luma ${icon('out')}</a><p class="hint">Luma can email you a six-digit sign-in code. Enter it on Luma.</p><button id="luma-continue" class="secondary full">I’m signed in ${icon('arrow')}</button><details class="setup-detail"><summary>How the connection works</summary><p>Your browser-capable agent checks access when collecting an event. This app cannot verify the browser login itself. Organizer API keys are scoped to calendars; they do not unlock events you attend.</p><a href="https://help.luma.com/p/signing-in" target="_blank" rel="noreferrer">Luma sign-in help ↗</a></details><button id="snapshot-continue" class="text-button">Use a collected profile file instead</button><button id="try-demo" class="text-button">Explore the fictional demo</button></div>`:step===6?`<div class="setup-copy"><h2>Bring your agent.</h2><p>Use your existing session, a supported CLI, or your own API key.</p>${connectionFields()}<button class="primary full" id="finish-setup">${editing?'Save connections':'Find my people'} ${icon('arrow')}</button><p class="hint">You can change this anytime.</p></div>`:`<form id="question-form"><h2>${esc(q?.label)}</h2><p>${esc(q?.hint)}</p><textarea id="answer" name="answer" aria-label="${esc(q?.label)}" required maxlength="3000" placeholder="${esc(questionPlaceholder(q?.id))}">${esc(answers[q?.id]||'')}</textarea>${q?.id==='interests'?'<span class="hint">Separate topics with commas.</span>':''}${step===5?`<details class="setup-detail"><summary>Must-have criteria <span class="muted">optional</span></summary><textarea id="must-haves" aria-label="Must-have criteria" placeholder="One indispensable requirement per line">${esc((answers.must_haves||[]).join('\n'))}</textarea></details>`:''}<div class="step-actions"><button type="button" id="setup-back" class="text-button">${icon('back')} Back</button><button type="submit" class="primary">${step===5?'Create profile':'Continue'} ${icon('arrow')}</button></div></form>`}</section></main>`;
  }
  function questionPlaceholder(id){return {work:'I’m building…',interests:'AI infrastructure, design, climate…',looking_for:'A collaborator, practical feedback, a new perspective…',connect_with:'People building or researching…',can_offer:'Experience with…, an introduction, thoughtful feedback…'}[id]||'';}
  function bindSetup() {
    async function advance(luma){try{await api('/api/settings',{luma,setup_complete:false});state.settings.luma=luma;step=1;view='setup';render();}catch(e){toast(e.message);}}
    bind('luma-continue','click',()=>advance('browser_handoff'));bind('snapshot-continue','click',()=>advance('snapshot'));
    bind('try-demo','click',async()=>{try{const result=await api('/api/demo',{});eventId=result.event_id;view='discover';await refresh();}catch(e){toast(e.message);}});
    bind('setup-back','click',()=>{answers[state.questions[step-1].id]=document.getElementById('answer').value;step=Math.max(editing?1:0,step-1);render();});
    bind('question-form','submit',async e=>{
      e.preventDefault();answers[state.questions[step-1].id]=document.getElementById('answer').value.trim();
      if(step===5){answers.must_haves=(document.getElementById('must-haves')?.value||'').split('\n').filter(Boolean);e.submitter.disabled=true;
        try{await api('/api/onboard',answers);state=await api('/api/state');if(editing){view='discover';editing=false;await refresh();toast('Profile updated. Refresh analysis to apply it.');return;}}
        catch(error){toast(error.message);e.submitter.disabled=false;return;}}
      step++;view='setup';render();document.getElementById('answer')?.focus();
    });
    bindConnectionFields();
    bind('finish-setup','click',async()=>{try{await saveConnection();await api('/api/settings',{setup_complete:true});view='discover';await refresh();}catch(e){toast(e.message);}});
  }
  function shell() {
    const b=state.brief, options=state.events.map(e=>`<option value="${esc(e.event_id)}" ${e.event_id===eventId?'selected':''}>${esc(e.event.name)}</option>`).join('');
    return `<div class="workspace"><aside class="sidebar"><label class="eyebrow" for="event-select">YOUR ROOM</label>${options?`<select id="event-select">${options}</select>`:'<p>No event yet.</p>'}${guide?`<a class="quiet-link event-link" href="${esc(guide.event.url)}" target="_blank" rel="noreferrer">View on Luma ${icon('out')}</a>`:''}${!exported?'<button id="new-event" class="text-button add-event">+ Add event</button>':''}<div class="sidebar-rule"></div><div class="eyebrow">YOUR LENS</div><div class="chips lens-topics">${b.interests.slice(0,5).map(i=>`<span class="chip">${esc(i)}</span>`).join('')}</div><p class="lens-goal">${esc(short(b.looking_for,115))}</p><button id="nav-criteria" class="quiet-link">Edit preferences ${icon('out')}</button><canvas class="particle-art" width="480" height="380" aria-hidden="true"></canvas><p class="art-caption">A little less noise.<br>A little more connection.</p><div class="sidebar-bottom">${!exported?`<button id="collect-agent" class="quiet-link">${icon('spark')} Collect with my agent</button>`:'<span>Read-only guide</span>'}${!exported&&eventId?`<a href="/api/export?event=${encodeURIComponent(eventId)}" class="quiet-link">Export guide ${icon('out')}</a>`:''}</div></aside><main class="main">${view==='new-event'||!eventId?newEvent():view==='graph'?graphView():view==='criteria'?criteriaView():discoveryView()}</main></div>`;
  }
  function newEvent() {
    return `<div class="page-heading"><div class="eyebrow">YOUR NEXT ROOM</div><h1>Where are you going?</h1></div><section class="plain-panel"><form id="event-form"><label for="event-url">Luma event link</label><input id="event-url" name="url" type="url" required placeholder="https://luma.com/your-event"><label for="event-name">Event name <span class="muted">optional</span></label><input id="event-name" name="name" placeholder="AI night, a founder dinner…"><button type="submit" class="primary">Add event ${icon('arrow')}</button></form><p class="hint">Your agent collects the attendee list your account can access.</p>${!exported?'<button id="import-snapshot" class="text-button">Import a profile snapshot</button>':''}</section>`;
  }
  function discoveryView() {
    if(!guide)return '<div class="empty"><h2>Add an event to begin.</h2></div>';
    const counts=guide.counts, saved=view==='saved', meet=view==='meet';
    const title=saved?'Worth coming back to.':meet?'Make a connection.':'Find your people.';
    const sub=saved?'Your saved connections.':meet?'Your personal plan for the room.':'A few good conversations can change the whole evening.';
    const active=guide.people.filter(p=>recommended(p)&&!decided(p)).length;
    return `<div class="page-heading"><div class="eyebrow">${saved?'YOUR SHORTLIST':meet?'PEOPLE TO MEET':'A SMALLER ROOM'}</div><h1>${title}</h1><p>${sub}</p></div><div class="discovery-toolbar"><div class="search-wrap">${icon('search')}<input id="search" type="search" aria-label="Search people" placeholder="Name, company, or interest" value="${esc(query)}" autocomplete="off"><kbd>/</kbd></div><div class="segmented" aria-label="Browse style"><button data-mode="stack" class="${mode==='stack'?'active':''}" aria-label="Card stack" aria-pressed="${mode==='stack'}">${icon('cards')}</button><button data-mode="list" class="${mode==='list'?'active':''}" aria-label="Scroll profiles" aria-pressed="${mode==='list'}">${icon('list')}</button></div></div>${!saved&&!meet?`<div class="discovery-meta"><div class="small-tabs">${[['suggested','For you'],['all','All reviewed'],['verify','Needs context']].map(([id,label])=>`<button data-filter="${id}" class="${filter===id?'active':''}">${label}</button>`).join('')}</div><span class="coverage">${counts.reviewed} of ${counts.captured} reviewed${!exported?` <button id="analyze" aria-label="Refresh analysis" title="Refresh analysis">↻</button>`:''}</span></div>`:`<div class="discovery-meta"><span class="muted">${saved?navCount('saved'):navCount('meet')} ${(saved?navCount('saved'):navCount('meet'))===1?'person':'people'}</span><span class="hint">${meet?'Meet is a private plan; no message is sent.':''}</span></div>`}${state.job.running?`<div class="notice" id="analysis-progress" role="status">Updating your guide · ${esc(state.job.stage||'starting')} ${state.job.current||0}/${state.job.total||'…'}</div>`:''}${state.job.error?`<div class="notice error">${esc(state.job.error)}</div>`:''}${Object.keys(guide.errors||{}).length?'<div class="notice error">Some profiles need another analysis attempt.</div>':''}<div id="discovery-results" aria-live="polite">${cardsView()}</div><div class="guide-footer"><span id="remaining-count">${saved?navCount('saved')+' saved':meet?navCount('meet')+' to meet':active+' in your stack'}</span><span>${exported?'Read-only export':'Private to this workspace'}</span></div>`;
  }
  function filteredPeople() {
    if(!searchIndex)return [];
    return searchIndex.search(query).map(r=>r.person).filter(p=>{
      if(view==='saved')return p.feedback.status==='saved';
      if(view==='meet')return ['meet','met'].includes(p.feedback.status);
      if(decided(p))return false;
      return filter==='all'||filter==='suggested'&&recommended(p)||filter==='verify'&&p.score.status==='Needs verification';
    });
  }
  function cardsView() {
    const people=filteredPeople();
    if(mode==='stack'&&people.length){stackOffset%=people.length;people.push(...people.splice(0,stackOffset));}
    if(!people.length)return `<section class="empty"><span class="empty-mark">${icon(query?'search':'spark')}</span><h2>${query?'No matches yet.':view==='saved'?'Save a little serendipity.':view==='meet'?'Your next hello starts here.':'You’ve explored this stack.'}</h2><p>${query?'Try a name, company, or a different topic.':view==='saved'?'Save someone from Discover to find them here.':view==='meet'?'Choose Meet on a profile to add it to your plan.':guide.counts.reviewed?'Switch to All reviewed or collect more profiles.':'Collect profiles with your agent, then prepare your guide.'}</p>${undo&&!exported?'<button id="undo-action" class="secondary">Undo last action</button>':''}${!guide.counts.reviewed&&!exported?'<button id="prepare-empty" class="primary">Prepare guide</button>':''}</section>`;
    if(mode==='list')return `<div class="profile-list">${people.slice(0,visibleLimit).map(p=>card(p,false)).join('')}</div>${people.length>visibleLimit?'<button class="secondary load-more" id="load-more">Show more people</button>':''}`;
    return `<div class="stack-counter"><span>${people.length} ${query?(people.length===1?'match':'matches'):(people.length===1?'person to explore':'people to explore')}</span><div>${undo&&!exported?`<button id="undo-action" class="quiet-link" aria-label="Undo last action">${icon('undo')} Undo</button>`:''}<button id="next-card" class="quiet-link" aria-label="Next profile">Next ${icon('arrow')}</button></div></div><div class="card-stack">${card(people[0],true)}${people.length>1?'<div class="stack-layer layer-one" aria-hidden="true"></div>':''}${people.length>2?'<div class="stack-layer layer-two" aria-hidden="true"></div>':''}</div><div class="stack-hint"><span>← Not relevant</span><span>↑ Save</span><span>Meet →</span></div>`;
  }
  function card(p,stack) {
    const facts=p.professional?.facts||[], role=facts.filter(f=>['role','organization'].includes(f.kind)).map(f=>f.value).join(' · ');
    const topics=facts.filter(f=>['interest','skill','project'].includes(f.kind)).slice(0,3), contacts=p.contact_links||{};
    const photo=p.photo_url?`<img src="${esc(p.photo_url)}" alt="${esc(p.name)}" referrerpolicy="no-referrer" loading="lazy" draggable="false">`:'';
    const badge=recommended(p)?'A good overlap':p.score.status==='Needs verification'?'Needs context':p.score.status==='Outside criteria'?'Outside your criteria':'Limited overlap';
    const actions=exported?'<span class="hint">Read-only export</span>':`<div class="card-actions"><button data-feedback="not_relevant" data-person="${esc(p.profile_url)}" class="action-pass">${icon('close')}<span>Not relevant</span></button><button data-feedback="saved" data-person="${esc(p.profile_url)}" class="action-save">${icon('save')}<span>Save</span></button><button data-feedback="meet" data-person="${esc(p.profile_url)}" class="action-meet">${icon('meet')}<span>Meet</span></button></div>`;
    return `<article class="person-card ${stack?'front-card':''}" data-profile="${esc(p.profile_url)}" tabindex="0" aria-label="Profile of ${esc(p.name)}"><div class="card-overline"><span class="match-badge">${icon('spark')}${badge}</span>${p.feedback.status==='met'?'<span class="hint">Met</span>':''}</div><div class="identity"><div class="avatar"><span>${esc(initials(p.name))}</span>${photo}</div><div class="identity-text"><h2>${esc(p.name.replace(' (demo)',''))}</h2><p>${esc(short(role,130)||'Professional background not yet established')}</p><div class="contact-links">${[['email','mail','Email'],['x','x','X'],['linkedin','linkedin','LinkedIn']].map(([id,i,label])=>contacts[id]?`<a href="${esc(id==='email'?'mailto:'+contacts[id]:contacts[id])}" target="_blank" rel="noreferrer" aria-label="${esc(label+' · '+p.name)}" title="${label}">${icon(i)}</a>`:`<span class="contact-unavailable" aria-label="${label} not available" title="${label} not available">${icon(i)}</span>`).join('')}<a href="${esc(p.profile_url)}" target="_blank" rel="noreferrer" class="luma-profile">Luma ${icon('out')}</a></div></div></div><p class="person-summary">${esc(short(p.summary,210))}</p><div class="chips">${topics.map(t=>`<span class="chip">${esc(short(t.value,47))}</span>`).join('')}</div>${p.why.length?`<div class="match-reason"><span class="eyebrow">WHY YOU MIGHT CONNECT</span><p>${esc(short(p.why[0],245))}</p></div>`:'<div class="match-reason"><p class="muted">More professional context would help establish relevance.</p></div>'}<details class="profile-details"><summary>Conversation starter & sources <span>+</span></summary><div class="details-content"><div class="conversation">${icon('spark')}<p>${esc(p.conversation_starter)}</p></div>${p.uncertainties.length?`<p class="hint">Still worth checking: ${esc(short(p.uncertainties.join(' '),400))}</p>`:''}${evidence(p)}<div class="hint">${p.score.known_criteria}/${p.score.total_criteria} criteria have conclusive evidence.</div></div></details>${actions}${view!=='discover'&&!exported?`<div class="collection-actions"><button data-feedback="none" data-person="${esc(p.profile_url)}" class="text-button">Return to Discover</button>${view==='meet'&&p.feedback.status!=='met'?`<button data-feedback="met" data-person="${esc(p.profile_url)}" class="text-button">Mark as met ✓</button>`:''}</div>`:''}</article>`;
  }
  function evidence(p) {
    const sources=Object.fromEntries(p.sources.map(s=>[s.id,s]));
    return p.assessments.filter(a=>a.evidence.length).map(a=>`<div class="evidence-row"><strong>${esc(a.criterion_id)} · ${esc(a.verdict)}</strong><p>${esc(a.reason)}</p>${a.evidence.map(e=>`<blockquote>${esc(e.quote)}<a href="${esc(sources[e.source_id]?.url)}" target="_blank" rel="noreferrer">${esc(sources[e.source_id]?.title)} ↗ <span>${esc(sourceDate(sources[e.source_id]?.retrieved_at))}</span></a></blockquote>`).join('')}</div>`).join('')||'<p class="hint">No supporting excerpts available.</p>';
  }
  function redrawResults() {
    const container=document.getElementById('discovery-results');if(!container)return;
    container.innerHTML=cardsView();bindCards();
    const count=document.getElementById('remaining-count');if(count)count.textContent=guide.people.filter(p=>recommended(p)&&!decided(p)).length+' in your stack';
  }
  function bindShell() {
    bind('event-select','change',async e=>{eventId=e.target.value;query='';view='discover';undo=null;try{await feedbackQueue;await refresh();}catch(error){toast(error.message);}});
    bind('new-event','click',()=>{view='new-event';render();});bind('nav-criteria','click',()=>{view='criteria';render();});
    bind('event-form','submit',async e=>{e.preventDefault();try{const value=await api('/api/events',Object.fromEntries(new FormData(e.target)));eventId=value.event_id;view='discover';await refresh();agentModal().catch(error=>toast(error.message));}catch(error){toast(error.message);}});
    bind('import-snapshot','click',()=>agentModal().catch(e=>toast(e.message)));bind('collect-agent','click',()=>agentModal().catch(e=>toast(e.message)));
    bind('analyze','click',analysisModal);
    bind('search','input',e=>{query=e.target.value;visibleLimit=20;stackOffset=0;redrawResults();});
    document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;render();}));
    document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;stackOffset=0;render();}));
    bind('save-criteria','click',async()=>{try{await api('/api/criteria',{markdown:document.getElementById('criteria-editor').value});await refresh();toast('Preferences saved. Refresh analysis to apply them.');}catch(e){toast(e.message);}});
    bindCards();bindGraph();
  }
  function bindCards() {
    document.querySelectorAll('[data-feedback]').forEach(b=>b.addEventListener('click',()=>act(b.dataset.person,b.dataset.feedback)));
    document.querySelectorAll('.avatar img').forEach(img=>img.addEventListener('error',()=>img.remove()));
    bind('undo-action','click',undoAction);bind('prepare-empty','click',analysisModal);
    bind('load-more','click',()=>{visibleLimit+=20;redrawResults();});
    bind('next-card','click',()=>{const people=filteredPeople();if(people.length>1){stackOffset=(stackOffset+1)%people.length;redrawResults();}});
    const front=document.querySelector('.front-card');if(!front)return;
    let pointer=null;
    front.addEventListener('pointerdown',e=>{if(e.target.closest('a,button,summary,details'))return;pointer={x:e.clientX,y:e.clientY};front.setPointerCapture(e.pointerId);});
    front.addEventListener('pointermove',e=>{if(!pointer||exported)return;const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;if(Math.abs(dx)>15&&Math.abs(dx)>Math.abs(dy)*1.2){front.style.transform=`translateX(${Math.max(-100,Math.min(100,dx))}px) rotate(${dx/50}deg)`;front.style.opacity=String(Math.max(.5,1-Math.abs(dx)/600));}});
    front.addEventListener('pointerup',e=>{if(!pointer)return;front.style.transform='';front.style.opacity='';const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;pointer=null;
      if(exported)return;if(Math.abs(dx)>85&&Math.abs(dx)>Math.abs(dy)*1.5)act(front.dataset.profile,dx>0?'meet':'not_relevant');
      else if(dy < -85&&Math.abs(dy)>Math.abs(dx)*1.5)act(front.dataset.profile,'saved');
    });
    front.addEventListener('pointercancel',()=>{pointer=null;front.style.transform='';front.style.opacity='';});
    front.addEventListener('wheel',e=>{if(e.target.closest('details[open]')||Math.abs(e.deltaY)<35)return;if(e.deltaY>0){e.preventDefault();if(Date.now()-lastBrowseWheel<500)return;lastBrowseWheel=Date.now();document.getElementById('next-card')?.click();}},{passive:false});
  }
  function act(url,status) {
    if(exported)return;
    const person=guide.people.find(p=>p.profile_url===url);if(!person)return;
    const previous={...person.feedback}, targetEvent=eventId;
    person.feedback={...previous,status};undo={person,previous,event:targetEvent};pendingWrites++;
    render();toast(status==='meet'?'Added to your meet list.':status==='saved'?'Saved.':status==='not_relevant'?'Removed from your stack.':status==='met'?'Marked as met.':'Back in Discover.',undoAction);
    feedbackQueue=feedbackQueue.then(()=>api('/api/feedback',{event_id:targetEvent,profile_url:url,status,note:previous.note||''})).catch(error=>{
      person.feedback=previous;if(undo?.person===person)undo=null;if(eventId===targetEvent)render();toast('Could not save: '+error.message);
    }).finally(()=>pendingWrites--);
  }
  function undoAction() {
    if(!undo)return;const value=undo;undo=null;value.person.feedback=value.previous;pendingWrites++;
    if(eventId===value.event)render();
    feedbackQueue=feedbackQueue.then(()=>api('/api/feedback',{event_id:value.event,profile_url:value.person.profile_url,status:value.previous.status||'none',note:value.previous.note||''})).catch(error=>{toast('Undo could not be saved: '+error.message);refresh().catch(e=>toast(e.message));}).finally(()=>pendingWrites--);
    toast('Last action undone.');
  }
  document.addEventListener('keydown',e=>{
    if(e.target.closest('input,textarea,select,button,a,summary')||document.querySelector('.modal-backdrop'))return;
    if(e.key==='/'&&document.getElementById('search')){e.preventDefault();document.getElementById('search').focus();return;}
    if(mode!=='stack'||exported)return;
    const front=document.querySelector('.front-card');if(!front||front.querySelector('details[open]'))return;
    const status={ArrowLeft:'not_relevant',ArrowRight:'meet',ArrowUp:'saved'}[e.key];
    if(status){e.preventDefault();act(front.dataset.profile,status);}
  });
  function criteriaView(){return `<div class="page-heading"><div class="eyebrow">YOUR PREFERENCES</div><h1>A good connection, defined.</h1><p>From your five answers. Edit anytime.</p></div><textarea id="criteria-editor" class="criteria-editor" aria-label="Matching criteria Markdown" ${exported?'readonly':''}>${esc(state.criteria_markdown||guide?.criteria_markdown||'')}</textarea>${!exported?'<button id="save-criteria" class="primary">Save preferences</button>':''}`;}
  function graphView(){
    if(!guide)return '<div class="empty">Add an event to see shared context.</div>';
    const graph=guide.graph, linked=new Set(graph.edges.flatMap(e=>[e.source,e.target])), nodes=graph.nodes.filter(n=>linked.has(n.id));
    const people=nodes.filter(n=>n.type==='person'), contexts=nodes.filter(n=>!['person','user'].includes(n.type));
    const height=Math.max(400,people.length*60+30,contexts.length*52+30),positions={'user:self':[45,height/2]};
    people.forEach((n,i)=>positions[n.id]=[235,30+i*60]);contexts.forEach((n,i)=>positions[n.id]=[570,30+i*52]);
    const color=n=>({topic:'#9f91c5',organization:'#8fa999',project:'#b5a78e',user:'#5c5577'}[n.type]||'#7e8894');
    return `<div class="page-heading"><div class="eyebrow">SHARED CONTEXT</div><h1>A place to start.</h1><p>Documented interests, projects, and organizations.</p></div><div class="graph-wrap"><svg viewBox="0 0 850 ${height}" role="group" aria-label="Professional context graph">${graph.edges.filter(e=>positions[e.source]&&positions[e.target]).map(e=>`<line class="graph-line" x1="${positions[e.source][0]}" y1="${positions[e.source][1]}" x2="${positions[e.target][0]}" y2="${positions[e.target][1]}"/>`).join('')}${nodes.filter(n=>positions[n.id]).map(n=>`<g data-node="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(n.label)}"><circle cx="${positions[n.id][0]}" cy="${positions[n.id][1]}" r="8" fill="${color(n)}"/><text x="${positions[n.id][0]+14}" y="${positions[n.id][1]+4}">${esc(short(n.label.replace(' (demo)',''),29))}</text></g>`).join('')}</svg></div><div id="graph-selection" class="notice">Select a node for its sources.</div><p class="hint">Shared context does not establish a personal relationship.</p>`;
  }
  function bindGraph(){document.querySelectorAll('[data-node]').forEach(el=>{
    const select=()=>{const id=el.dataset.node,graph=guide.graph,node=graph.nodes.find(n=>n.id===id);document.getElementById('graph-selection').innerHTML=`<strong>${esc(node.label)}</strong>${graph.edges.filter(e=>e.source===id||e.target===id).map(e=>`<p>${esc(e.type.replaceAll('_',' '))}: ${esc(graph.nodes.find(n=>n.id===(e.source===id?e.target:e.source))?.label||'')}</p>${e.evidence.map(ref=>ref.source_url?`<a href="${esc(ref.source_url)}" target="_blank" rel="noreferrer">${esc(ref.quote)} ↗</a>`:'From your profile').join('<br>')}`).join('')}`;};
    el.addEventListener('click',select);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});
  });}
  function modal(content,label='Connections') {
    document.querySelector('.modal-backdrop')?.remove();const lastFocus=document.activeElement;
    const bg=document.createElement('div');bg.className='modal-backdrop';bg.innerHTML=`<section class="modal" role="dialog" aria-modal="true" aria-label="${esc(label)}"><button class="close icon-button" aria-label="Close dialog">${icon('close')}</button>${content}</section>`;
    document.body.append(bg);const close=()=>{bg.remove();lastFocus?.focus();};bg.querySelector('.close').addEventListener('click',close);
    bg.addEventListener('click',e=>{if(e.target===bg)close();});
    bg.addEventListener('keydown',e=>{if(e.key==='Escape')close();if(e.key==='Tab'){const focusable=[...bg.querySelectorAll('button,a,input,select,textarea,summary')].filter(el=>!el.disabled&&el.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
    bg.querySelector('.close').focus();return bg;
  }
  function connectionFields(){
    const current=state.settings?.backend||'agent';
    return `<label for="backend">Run with</label><select id="backend">${[['agent','My current agent'],['codex','Codex CLI · saved login'],['claude','Claude Code · saved login'],['ollama','Ollama · local model'],['openai','OpenAI API · API key'],['anthropic','Anthropic API · API key']].map(([id,label])=>`<option value="${id}" ${current===id?'selected':''}>${label}</option>`).join('')}</select><div id="connection-options"></div>`;
  }
  function bindConnectionFields(){bind('backend','change',connectionOptions);connectionOptions();}
  function connectionOptions(){
    const b=document.getElementById('backend')?.value,box=document.getElementById('connection-options');if(!box)return;
    if(b==='agent'){box.innerHTML='<p class="connection-note">Use the model in your current agent session. No extra key.</p><button id="agent-setup" class="text-button">Get agent setup ↗</button>';bind('agent-setup','click',()=>agentModal().catch(e=>toast(e.message)));return;}
    const saved=b===state.settings?.backend?state.settings?.model||'':'';
    box.innerHTML=`<label for="model">Model ${['codex','claude'].includes(b)?'<span class="muted">optional</span>':''}</label><input id="model" value="${esc(saved)}" placeholder="${b==='ollama'?'Installed model name':['openai','anthropic'].includes(b)?'Model ID from your provider':'Use the CLI default'}">${['openai','anthropic'].includes(b)?`<label for="api-key">API key</label><input id="api-key" type="password" autocomplete="off" spellcheck="false" placeholder="${state.connections?.[b]?.key_present?'Key available · leave blank to keep':'Paste your API key'}"><p class="hint">Session only. Never written to disk or sent to the browser again. API usage is billed separately.</p>${state.connections?.[b]?.key_present?'<button id="clear-key" class="text-button">Forget session key</button>':''}`:`<p class="connection-note">${b==='ollama'?'Runs on your local Ollama server.':`Uses ${b==='codex'?'Codex':'Claude Code'}’s saved login and normal account limits.`}</p><button id="check-connection" class="text-button">Check ${b==='ollama'?'server':'login'}</button><div id="check-result" class="hint" role="status"></div>`}`;
    bind('clear-key','click',async()=>{try{Object.assign(state,await api('/api/settings',{backend:b,clear_key:true}));connectionOptions();toast('Session key removed. Environment credentials, if set, still apply.');}catch(e){toast(e.message);}});
    bind('check-connection','click',async e=>{e.target.disabled=true;document.getElementById('check-result').textContent='Checking…';try{const result=await api('/api/check',{backend:b});document.getElementById('check-result').textContent=result.available?'Ready'+(result.models?.length?' · '+result.models.slice(0,4).join(', '):''):(result.note||'Sign in with the official CLI first.');}catch(error){document.getElementById('check-result').textContent=error.message;}finally{e.target.disabled=false;}});
  }
  async function saveConnection(){const data={backend:document.getElementById('backend').value,model:document.getElementById('model')?.value.trim()||''};const key=document.getElementById('api-key')?.value.trim();if(['openai','anthropic','ollama'].includes(data.backend)&&!data.model)throw new Error('Enter a model ID first.');if(['openai','anthropic'].includes(data.backend)&&!key&&!state.connections?.[data.backend]?.key_present)throw new Error('Add an API key for this session.');if(key)data.api_key=key;Object.assign(state,await api('/api/settings',data));document.getElementById('api-key')&&(document.getElementById('api-key').value='');}
  function connectionModal(){
    modal(`<div class="eyebrow">YOUR CONNECTIONS</div><h2>Keep setup light.</h2><div class="luma-connection"><span class="luma-symbol">${icon('event')}</span><div><strong>Luma</strong><p>Browser sign-in · verified by your agent during collection</p></div><a href="https://luma.com/signin" target="_blank" rel="noreferrer" class="secondary">Open ${icon('out')}</a></div>${connectionFields()}<button id="save-connections" class="primary full">Save connection</button>`);
    bindConnectionFields();bind('save-connections','click',async()=>{try{await saveConnection();document.querySelector('.modal-backdrop').remove();toast('Connection saved.');}catch(e){toast(e.message);}});
  }
  async function agentModal(){
    const dialog=modal(`<div class="eyebrow">BRING YOUR AGENT</div><h2>One workspace. Your model.</h2><label for="agent-choice">Your agent</label><select id="agent-choice">${[['codex','Codex'],['claude','Claude Code'],['cursor','Cursor'],['copilot','GitHub Copilot / VS Code'],['opencode','OpenCode'],['claude-desktop','Claude Desktop']].map(([id,name])=>`<option value="${id}">${name}</option>`).join('')}</select><div id="agent-config"></div>${guide?'<button id="copy-assignment" class="primary full">Copy event task</button>':''}<p class="hint">Requires browser tools in your agent. Sign in to Luma in that same browser.</p><details class="import-area"><summary>Import a profile snapshot</summary><input id="import-file" type="file" accept="application/json,.json" aria-label="Profile snapshot JSON"></details>`,'Agent setup');
    async function config(){const value=await api('/api/integration?agent='+dialog.querySelector('#agent-choice').value);dialog.querySelector('#agent-config').innerHTML=`<details open><summary>MCP configuration</summary><p class="hint">${esc(value.location)}</p><pre>${esc(value.configuration)}</pre><p class="hint">Requires the optional MCP package. See the repository setup guide.</p></details>`;}
    dialog.querySelector('#agent-choice').addEventListener('change',()=>config().catch(e=>toast(e.message)));
    dialog.querySelector('#copy-assignment')?.addEventListener('click',async()=>{
      const request=`Use the Luma Profile Review MCP tools and shared skill. Resume event ${eventId} at ${guide.event.url}. My brief is saved. Use your browser to verify I am signed in to Luma (email code entry stays on Luma), then collect the accessible attendee list. Record observed photo_url and published contact_links (email, linkedin, x) when present; never guess them. Follow relevant linked professional sources, save excerpts and limitations, structure profiles with evidence, and match against my criteria using your current model. Do not infer personal relationships from a shared company or event. Return the personalized guide with collection coverage.`;
      try{await navigator.clipboard.writeText(request);toast('Event task copied.');}catch{const area=document.createElement('textarea');area.value=request;dialog.querySelector('.modal').append(area);area.select();toast('Copy the selected task into your agent.');}
    });
    dialog.querySelector('#import-file').addEventListener('change',async e=>{try{if(!e.target.files[0])return;const result=await api('/api/import',JSON.parse(await e.target.files[0].text()));eventId=result.event_id;view='discover';dialog.remove();await refresh();toast('Profiles imported.');}catch(error){toast(error.message);}});await config();
  }
  function analysisModal(){
    if(state.settings?.backend==='agent'){agentModal().catch(e=>toast(e.message));return;}
    const dialog=modal(`<div class="eyebrow">REFRESH YOUR GUIDE</div><h2>Find the overlap.</h2>${connectionFields()}<p class="hint">Analyzes collected excerpts and your professional brief. Cloud providers receive this information. API modes incur usage charges.</p><button id="start-analysis" class="primary full">Prepare guide</button>`,'Analysis');bindConnectionFields();
    bind('start-analysis','click',async e=>{e.target.disabled=true;try{await saveConnection();if(state.settings.backend==='agent'){dialog.remove();await agentModal();return;}await api('/api/analyze',{event_id:eventId,backend:state.settings.backend,model:state.settings.model||null});dialog.remove();await refresh();}catch(error){toast(error.message);e.target.disabled=false;}});
  }
  function paintParticles(){
    document.querySelectorAll('.particle-art').forEach(canvas=>{
      const ctx=canvas.getContext('2d');if(!ctx)return;const w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
      let seed=44;const rand=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646;};
      const vertices=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]];
      const edges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
      for(let i=0;i<1900;i++){const edge=edges[i%12],t=rand(),a=vertices[edge[0]],b=vertices[edge[1]];
        let x=a[0]+(b[0]-a[0])*t,y=a[1]+(b[1]-a[1])*t,z=a[2]+(b[2]-a[2])*t;
        x+=Math.sin(t*18+z*3)*.045+(rand()-.5)*.13;y+=(rand()-.5)*.13;z+=(rand()-.5)*.13;
        const rx=x*.82+z*.57,rz=-x*.57+z*.82,ry=y*.93-rz*.36,depth=y*.36+rz*.93;
        const scale=95/(1+depth*.13),px=w/2+rx*scale,py=h/2+ry*scale;
        ctx.beginPath();ctx.fillStyle=`rgba(${i%7===0?'139,123,167':'76,74,91'},${.13+rand()*.36})`;ctx.arc(px,py,.5+rand()*.65,0,Math.PI*2);ctx.fill();
      }
    });
  }
  refresh().catch(error=>{app.innerHTML=`<main class="empty"><h2>Could not load your guide.</h2><p>${esc(error.message)}</p><button onclick="location.reload()">Reload</button></main>`;});
})();
