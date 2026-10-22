/* Local discovery, onboarding, and portable guides. No UI framework or build step. */
(() => {
  'use strict';
  const exported = window.__EXPORTED_GUIDE__ || null;
  const hosted = !!window.__BROWSER_WORKSPACE__;
  let graphController = null;
  const token = exported || hosted ? '' : JSON.parse(document.getElementById('bootstrap').textContent).token;
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
    pause:'<path d="M8 5v14M16 5v14"/>', play:'<path d="m8 5 11 7-11 7Z"/>',
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
    if(hosted)return window.PeopleBrowserWorkspace.request(path,data);
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
      try{const next=await api('/api/state');if(next.job.running){state.job=next.job;state.agent=next.agent;const progress=document.getElementById('analysis-progress');if(progress){const text=progress.querySelector('span');if(text)text.textContent=`${state.job.stage||'Starting'} · ${state.job.current||0}/${state.job.total||'…'}`;}}else await refresh();}catch(e){toast(e.message);}finally{pollBusy=false;}
    },2500);
    if(!state.job.running&&polling){clearInterval(polling);polling=null;}
  }
  function navCount(name){return (guide?.people||[]).filter(p=>name==='saved'?p.feedback.status==='saved':['meet','met'].includes(p.feedback.status)).length;}
  function header() {
    return `<header class="topbar"><a href="#" id="home" class="brand"><span class="brand-mark">${icon('spark')}</span><strong>people</strong><span class="brand-sub">for Luma</span></a>${state.brief?`<nav aria-label="Main navigation">${[['discover','spark','Discover'],['saved','save','Saved'],['meet','meet','Meet'],['graph','graph','Context']].map(([id,i,label])=>`<button data-nav="${id}" class="nav-item ${view===id?'active':''}">${icon(i)}<span>${label}</span>${['saved','meet'].includes(id)&&navCount(id)?`<small>${navCount(id)}</small>`:''}</button>`).join('')}</nav>`:''}<div class="top-actions"><button id="toggle-motion" class="icon-button motion-button" aria-label="${window.PeopleMotion?.paused?'Play':'Pause'} background animation" title="${window.PeopleMotion?.paused?'Play':'Pause'} background animation">${icon(window.PeopleMotion?.paused?'play':'pause')}</button>${!exported?`<button id="settings" class="icon-button" aria-label="Connections">${icon('settings')}</button>${state.brief?`<button id="edit-brief" class="profile-button" aria-label="Your profile">${icon('user')}</button>`:''}`:''}</div></header>${guide?.demo?'<div class="demo-banner">FICTIONAL DEMO · Curated profiles and recommendations. No live inference.</div>':''}`;
  }
  function render() {
    graphController?.destroy();graphController=null;
    const setup=!state.brief||view==='setup';
    app.innerHTML=header()+(setup?setupView():shell());
    bind('home','click',e=>{e.preventDefault();view=state.brief?'discover':'setup';render();});
    bind('edit-brief','click',()=>{editing=true;step=1;answers={...state.brief,interests:state.brief.interests.join(', ')};view='setup';render();});
    bind('settings','click',connectionModal);
    document.querySelectorAll('[data-nav]').forEach(b=>b.addEventListener('click',()=>{view=b.dataset.nav;query='';visibleLimit=20;stackOffset=0;render();}));
    if(setup)bindSetup();else bindShell();
    bind('toggle-motion','click',()=>{window.PeopleMotion?.toggle();const b=document.getElementById('toggle-motion');b.innerHTML=icon(window.PeopleMotion?.paused?'play':'pause');b.setAttribute('aria-label',(window.PeopleMotion?.paused?'Play':'Pause')+' background animation');});
  }
  function setupView() {
    const q=state.questions[step-1];
    return `<main class="setup"><aside class="setup-art"><div class="eyebrow">MAKE EVERY HELLO COUNT</div><h1>Arrive prepared.<br><em>Know who to meet.</em></h1><p>Your interests. The right people.<br>A reason to say hello.</p></aside><section class="setup-panel"><div class="setup-progress"><span>${step===0?'CONNECT':step===6?'YOUR AGENT':`YOUR PROFILE · ${step} OF 5`}</span><div class="progress-dots">${Array.from({length:7},(_,i)=>`<i class="${i<=step?'done':''}"></i>`).join('')}</div></div>${step===0?`<div class="setup-copy"><span class="setup-symbol">${icon('event')}</span><h2>${hosted?'A better evening starts here.':'Connect your room.'}</h2><p>${hosted?'Five quick questions. Your agent takes care of the research.':'Sign in to Luma once in the app’s research browser.'}</p>${!hosted?'<button id="setup-luma" class="primary full">Connect Luma ↗</button><p class="hint">Enter your verification code on Luma, then return here.</p>':''}<button id="luma-continue" class="${hosted?'primary':'secondary'} full">${hosted?'Get started':'Continue'} ${icon('arrow')}</button><button id="try-demo" class="text-button">Explore the fictional demo</button></div>`:step===6?`<div class="setup-copy"><h2>Connect once. Meet better.</h2><p>Codex does the research. You make the connection.</p>${connectionFields()}<button class="primary full" id="finish-setup">${editing?'Save connections':'Find my people'} ${icon('arrow')}</button><p class="hint">You can change this anytime.</p></div>`:`<form id="question-form"><h2>${esc(q?.label)}</h2><p>${esc(q?.hint)}</p><textarea id="answer" name="answer" aria-label="${esc(q?.label)}" required maxlength="3000" placeholder="${esc(questionPlaceholder(q?.id))}">${esc(answers[q?.id]||'')}</textarea>${q?.id==='interests'?'<span class="hint">Separate topics with commas.</span>':''}${step===5?`<details class="setup-detail"><summary>Must-have criteria <span class="muted">optional</span></summary><textarea id="must-haves" aria-label="Must-have criteria" placeholder="One indispensable requirement per line">${esc((answers.must_haves||[]).join('\n'))}</textarea></details>`:''}<div class="step-actions"><button type="button" id="setup-back" class="text-button">${icon('back')} Back</button><button type="submit" class="primary">${step===5?'Create profile':'Continue'} ${icon('arrow')}</button></div></form>`}</section></main>`;
  }
  function questionPlaceholder(id){return {work:'I’m building…',interests:'AI infrastructure, design, climate…',looking_for:'A collaborator, practical feedback, a new perspective…',connect_with:'People building or researching…',can_offer:'Experience with…, an introduction, thoughtful feedback…'}[id]||'';}
  function bindSetup() {
    async function advance(luma){try{await api('/api/settings',{luma,setup_complete:false});state.settings.luma=luma;step=1;view='setup';render();}catch(e){toast(e.message);}}
    bind('setup-luma','click',()=>agentModal().catch(e=>toast(e.message)));bind('luma-continue','click',()=>advance('browser_handoff'));
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
    return `<div class="workspace"><aside class="sidebar"><label class="eyebrow" for="event-select">YOUR ROOM</label>${options?`<select id="event-select">${options}</select>`:'<p>No event yet.</p>'}${guide?`<a class="quiet-link event-link" href="${esc(guide.event.url)}" target="_blank" rel="noreferrer">View on Luma ${icon('out')}</a>`:''}${!exported?'<button id="new-event" class="text-button add-event">+ Add event</button>':''}<div class="sidebar-rule"></div><div class="eyebrow">YOUR LENS</div><div class="chips lens-topics">${b.interests.slice(0,5).map(i=>`<span class="chip">${esc(i)}</span>`).join('')}</div><button id="nav-criteria" class="quiet-link">Edit preferences ${icon('out')}</button><div class="sidebar-bottom">${!exported?`<button id="collect-agent" class="quiet-link">${icon('spark')} Prepare with Codex</button>`:'<span>Read-only guide</span>'}${!exported&&eventId?`<button id="export-guide" class="quiet-link">Export guide ${icon('out')}</button>`:''}</div></aside><main class="main">${view==='new-event'||!eventId?newEvent():view==='graph'?graphView():view==='criteria'?criteriaView():discoveryView()}</main></div>`;
  }
  function newEvent() {
    return `<div class="page-heading"><div class="eyebrow">YOUR NEXT ROOM</div><h1>Where are you going?</h1></div><section class="plain-panel"><form id="event-form"><label for="event-url">Luma event link</label><input id="event-url" name="url" type="url" required placeholder="https://luma.com/your-event"><label for="event-name">Event name <span class="muted">optional</span></label><input id="event-name" name="name" placeholder="AI night, a founder dinner…"><button type="submit" class="primary">Add event ${icon('arrow')}</button></form><p class="hint">Codex collects accessible profiles and prepares your guide here.</p></section>`;
  }
  function discoveryView() {
    if(!guide)return '<div class="empty"><h2>Add an event to begin.</h2></div>';
    const counts=guide.counts, saved=view==='saved', meet=view==='meet';
    const title=saved?'Worth another look.':meet?'Your next hello.':'Arrive prepared.<br><em>Know who to meet.</em>';
    const sub=saved?'Good connections are worth keeping.':meet?'A few people. A better evening.':'Tap <b>X</b> to skip, <b>Save</b> to revisit later, or <b>Meet</b> if you’d like to meet them.';
    const active=guide.people.filter(p=>recommended(p)&&!decided(p)).length;
    return `<div class="page-heading"><div class="eyebrow">${saved?'YOUR SHORTLIST':meet?'PEOPLE TO MEET':'A SMALLER ROOM'}</div><h1>${title}</h1><p>${sub}</p></div><div class="discovery-toolbar"><div class="search-wrap">${icon('search')}<input id="search" type="search" aria-label="Search people" placeholder="Name, company, or interest" value="${esc(query)}" autocomplete="off"><kbd>/</kbd></div><div class="segmented" aria-label="Browse style"><button data-mode="stack" class="${mode==='stack'?'active':''}" aria-label="Card stack" aria-pressed="${mode==='stack'}">${icon('cards')}</button><button data-mode="list" class="${mode==='list'?'active':''}" aria-label="Scroll profiles" aria-pressed="${mode==='list'}">${icon('list')}</button></div></div>${!saved&&!meet?`<div class="discovery-meta"><div class="small-tabs">${[['suggested','For you'],['all','All reviewed'],['verify','Needs context']].map(([id,label])=>`<button data-filter="${id}" class="${filter===id?'active':''}">${label}</button>`).join('')}</div><span class="coverage">${counts.reviewed} reviewed · ${counts.captured} collected${guide.event.displayed_guest_count>counts.captured?' · '+guide.event.displayed_guest_count+' shown on Luma':''}${guide.event.roster_complete===false?' · partial list':''}${!exported?` <button id="analyze" aria-label="Refresh analysis" title="Refresh analysis">↻</button>`:''}</span></div>`:`<div class="discovery-meta"><span class="muted">${saved?navCount('saved'):navCount('meet')} ${(saved?navCount('saved'):navCount('meet'))===1?'person':'people'}</span><span class="hint">${meet?'Meet is a private plan; no message is sent.':''}</span></div>`}${state.job.running?`<div class="notice" id="analysis-progress" role="status">Updating your guide · <span>${esc(state.job.stage||'Starting')} · ${state.job.current||0}/${state.job.total||'…'}</span>${state.job.kind==='agent'?'<button id="stop-agent" class="text-button">Stop</button>':''}</div>`:''}${state.agent?.needs_action?`<div class="notice">${esc(state.agent.needs_action)} <button id="agent-action-needed" class="text-button">Open connections</button></div>`:''}${state.job.error?`<div class="notice error">${esc(state.job.error)}</div>`:''}${Object.keys(guide.errors||{}).length?'<div class="notice error">Some profiles need another analysis attempt.</div>':''}<div id="discovery-results" aria-live="polite">${cardsView()}</div><div class="guide-footer"><span id="remaining-count">${saved?navCount('saved')+' saved':meet?navCount('meet')+' to meet':active+' in your stack'}</span>${exported?'<span>Read-only export</span>':''}</div>`;
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
    if(!people.length)return `<section class="empty"><span class="empty-mark">${icon(query?'search':'spark')}</span><h2>${query?'No matches yet.':view==='saved'?'Save a little serendipity.':view==='meet'?'Your next hello starts here.':!guide.counts.reviewed?(state.job.running?'Finding your people…':'Your guide is one click away.'):'You’ve explored this stack.'}</h2><p>${query?'Try a name, company, or a different topic.':view==='saved'?'Save someone from Discover to find them here.':view==='meet'?'Choose Meet on a profile to add it to your plan.':guide.counts.reviewed?'Switch to All reviewed or collect more profiles.':'Choose Prepare guide. Codex will research the room and bring your matches here.'}</p>${undo&&!exported?'<button id="undo-action" class="secondary">Undo last action</button>':''}${!guide.counts.reviewed&&!exported&&!state.job.running?'<button id="prepare-empty" class="primary">Prepare guide</button>':''}</section>`;
    if(mode==='list')return `<div class="profile-list">${people.slice(0,visibleLimit).map(p=>card(p,false)).join('')}</div>${people.length>visibleLimit?'<button class="secondary load-more" id="load-more">Show more people</button>':''}`;
    return `<div class="stack-counter"><span>${people.length} ${query?(people.length===1?'match':'matches'):(people.length===1?'person to explore':'people to explore')}</span><div>${undo&&!exported?`<button id="undo-action" class="quiet-link" aria-label="Undo last action">${icon('undo')} Undo</button>`:''}<button id="next-card" class="quiet-link" aria-label="Next profile">Next ${icon('arrow')}</button></div></div><div class="card-stack">${card(people[0],true)}${people.length>1?'<div class="stack-layer layer-one" aria-hidden="true"></div>':''}${people.length>2?'<div class="stack-layer layer-two" aria-hidden="true"></div>':''}</div><div class="stack-hint"><span>← Skip</span><span>↑ Save</span><span>Meet →</span></div>`;
  }
  function card(p,stack) {
    const facts=p.professional?.facts||[], role=facts.filter(f=>['role','organization'].includes(f.kind)).map(f=>f.value).join(' · ');
    const topics=facts.filter(f=>['interest','skill','project'].includes(f.kind)).slice(0,3), contacts=p.contact_links||{};
    const photo=p.photo_url?`<img src="${esc(p.photo_url)}" alt="${esc(p.name)}" referrerpolicy="no-referrer" loading="lazy" draggable="false">`:'';
    const badge=recommended(p)?'A good overlap':p.score.status==='Needs verification'?'Needs context':p.score.status==='Outside criteria'?'Outside your criteria':'Limited overlap';
    const actions=exported?'<span class="hint">Read-only export</span>':`<div class="card-actions"><button data-feedback="not_relevant" data-person="${esc(p.profile_url)}" class="action-pass" aria-label="Skip this person">${icon('close')}<span>Skip</span></button><button data-feedback="saved" data-person="${esc(p.profile_url)}" class="action-save">${icon('save')}<span>Save</span></button><button data-feedback="meet" data-person="${esc(p.profile_url)}" class="action-meet">${icon('meet')}<span>Meet</span></button></div>`;
    return `<article class="person-card ${stack?'front-card':''}" data-profile="${esc(p.profile_url)}" tabindex="0" aria-label="Profile of ${esc(p.name)}"><div class="card-overline"><span class="match-badge">${icon('spark')}${badge}</span>${p.feedback.status==='met'?'<span class="hint">Met</span>':''}</div><div class="identity"><div class="avatar"><span>${esc(initials(p.name))}</span>${photo}</div><div class="identity-text"><h2>${esc(p.name.replace(' (demo)',''))}</h2><p>${esc(short(role,130)||'Professional background not yet established')}</p><div class="contact-links">${[['x','x','X'],['linkedin','linkedin','LinkedIn']].map(([id,i,label])=>contacts[id]?`<a href="${esc(contacts[id])}" target="_blank" rel="noreferrer" aria-label="${esc(label+' · '+p.name)}" title="${label}">${icon(i)}</a>`:`<span class="contact-unavailable" aria-label="${label} not available" title="${label} not available">${icon(i)}</span>`).join('')}<a href="${esc(p.profile_url)}" target="_blank" rel="noreferrer" class="luma-profile">Luma ${icon('out')}</a></div></div></div><p class="person-summary">${esc(short(p.summary,210))}</p><div class="chips">${topics.map(t=>`<span class="chip">${esc(short(t.value,47))}</span>`).join('')}</div>${p.why.length?`<div class="match-reason"><span class="eyebrow">WHY YOU MIGHT CONNECT</span><p>${esc(short(p.why[0],245))}</p></div>`:'<div class="match-reason"><p class="muted">More professional context would help establish relevance.</p></div>'}<details class="profile-details"><summary>Conversation starter & sources <span>+</span></summary><div class="details-content"><div class="conversation">${icon('spark')}<p>${esc(p.conversation_starter)}</p></div>${p.uncertainties.length?`<p class="hint">Still worth checking: ${esc(short(p.uncertainties.join(' '),400))}</p>`:''}${evidence(p)}<div class="hint">${p.score.known_criteria}/${p.score.total_criteria} criteria have conclusive evidence.</div></div></details>${actions}${view!=='discover'&&!exported?`<div class="collection-actions"><button data-feedback="none" data-person="${esc(p.profile_url)}" class="text-button">Return to Discover</button>${view==='meet'&&p.feedback.status!=='met'?`<button data-feedback="met" data-person="${esc(p.profile_url)}" class="text-button">Mark as met ✓</button>`:''}</div>`:''}</article>`;
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
    bind('collect-agent','click',()=>agentModal().catch(e=>toast(e.message)));
    bind('analyze','click',analysisModal);bind('export-guide','click',exportModal);bind('stop-agent','click',async()=>{await api('/api/agent',{action:'stop'});toast('Stopping… Progress will be saved.');});
    bind('search','input',e=>{query=e.target.value;visibleLimit=20;stackOffset=0;redrawResults();});
    document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;render();}));
    document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;stackOffset=0;render();}));
    bind('save-criteria','click',async()=>{try{await api('/api/criteria',{markdown:document.getElementById('criteria-editor').value});await refresh();toast('Preferences saved. Refresh analysis to apply them.');}catch(e){toast(e.message);}});
    bind('agent-action-needed','click',()=>agentModal().catch(e=>toast(e.message)));bindCards();bindGraph();
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
    if(!guide)return '<div class="empty">Add an event to explore connections.</div>';
    const linked=new Set(guide.graph.edges.flatMap(e=>[e.source,e.target]));
    const nodes=guide.graph.nodes.filter(n=>linked.has(n.id)).sort((a,b)=>a.label.localeCompare(b.label));
    return `<div class="page-heading graph-heading"><div class="eyebrow">FOLLOW THE THREAD</div><h1>Find your <em>common ground.</em></h1><p>Explore the interests, projects, and people that connect the room.</p></div>${!nodes.length?'<div class="empty"><h2>A connection starts with context.</h2><p>Prepare or import an event guide to explore its graph.</p></div>':`<section class="context-panel"><div class="graph-toolbar"><label class="sr-only" for="graph-jump">Find a person or topic</label><select id="graph-jump"><option value="">Find a person or topic…</option>${nodes.map(n=>`<option value="${esc(n.id)}">${esc(n.label.replace(' (demo)',''))}</option>`).join('')}</select><div class="graph-controls"><button id="graph-zoom-out" aria-label="Zoom out">−</button><button id="graph-zoom-in" aria-label="Zoom in">+</button><button id="graph-fit" aria-label="Fit graph">↔</button></div></div><div class="graph-filters" aria-label="Graph categories">${[['all','Everything'],['topic','Interests'],['organization','Companies'],['project','Projects']].map(([id,label])=>`<button data-graph-filter="${id}" class="${id==='all'?'active':''}">${label}</button>`).join('')}</div><div id="context-canvas" role="img" aria-label="Interactive professional context graph. Drag to pan, scroll to zoom, or use the controls above."></div><div class="graph-caption"><div class="graph-legend"><span><i class="person-key"></i>People</span><span><i class="topic-key"></i>Interests</span><span><i class="company-key"></i>Companies</span><span><i class="project-key"></i>Projects</span></div><span>Drag to explore · Scroll to zoom</span></div></section><section id="graph-selection" class="graph-inspector" aria-live="polite"><span class="eyebrow">PICK A THREAD</span><p>Select a person or topic to see what connects them.</p></section><p class="graph-note">Shared context is a conversation starter, not proof that people know each other.</p>`}`;
  }
  function bindGraph(){
    const container=document.getElementById('context-canvas');if(!container)return;
    function revealNode(id){graphController.filter('all');document.querySelectorAll('[data-graph-filter]').forEach(b=>b.classList.toggle('active',b.dataset.graphFilter==='all'));graphController.focus(id);}
    try{graphController=window.PeopleContext.mount(container,guide.graph,guide.people,(node,edges)=>{
      const graph=guide.graph,related=[...new Set(edges.map(e=>e.source===node.id?e.target:e.source))];
      const refs=edges.flatMap(e=>e.evidence||[]).filter(e=>e.source_url);
      const unique=[...new Map(refs.map(e=>[e.source_url+'|'+e.quote,e])).values()];
      document.getElementById('graph-selection').innerHTML=`<div class="inspector-title"><div><span class="eyebrow">${esc(node.type==='user'?'YOUR PROFILE':node.type.toUpperCase())}</span><h2>${esc(node.name||node.label)}</h2></div>${node.type==='person'?`<button class="secondary" id="graph-view-person">View card ${icon('arrow')}</button>`:''}</div><div class="related-nodes">${related.map(id=>`<button data-related="${esc(id)}">${esc(graph.nodes.find(n=>n.id===id)?.label.replace(' (demo)','')||'')} ${icon('out')}</button>`).join('')}</div>${unique.length?`<details class="graph-sources"><summary>${unique.length} supporting source${unique.length===1?'':'s'}</summary>${unique.slice(0,8).map(ref=>`<blockquote>${esc(ref.quote)}<a href="${esc(ref.source_url)}" target="_blank" rel="noreferrer">Open source ↗</a></blockquote>`).join('')}</details>`:'<p class="hint">From your onboarding profile.</p>'}`;
      document.querySelectorAll('[data-related]').forEach(b=>b.addEventListener('click',()=>revealNode(b.dataset.related)));
      bind('graph-view-person','click',()=>{const p=guide.people.find(p=>p.profile_url===node.id);view=p?.feedback.status==='saved'?'saved':['meet','met'].includes(p?.feedback.status)?'meet':'discover';filter='all';query=p?.name||node.label;stackOffset=0;render();});
    });}catch(e){container.innerHTML=`<p class="notice">${esc(e.message)}</p>`;return;}
    bind('graph-jump','change',e=>{if(e.target.value)revealNode(e.target.value);});
    bind('graph-zoom-in','click',()=>graphController.zoom(1.3));bind('graph-zoom-out','click',()=>graphController.zoom(1/1.3));bind('graph-fit','click',()=>graphController.fit());
    document.querySelectorAll('[data-graph-filter]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-graph-filter]').forEach(x=>x.classList.toggle('active',x===b));graphController.filter(b.dataset.graphFilter);}));
  }
  function modal(content,label='Connections') {
    document.querySelector('.modal-backdrop')?.remove();const lastFocus=document.activeElement;
    const bg=document.createElement('div');bg.className='modal-backdrop';bg.innerHTML=`<section class="modal" role="dialog" aria-modal="true" aria-label="${esc(label)}"><button class="close icon-button" aria-label="Close dialog">${icon('close')}</button>${content}</section>`;
    document.body.append(bg);const close=()=>{bg.remove();lastFocus?.focus();};bg.querySelector('.close').addEventListener('click',close);
    bg.addEventListener('click',e=>{if(e.target===bg)close();});
    bg.addEventListener('keydown',e=>{if(e.key==='Escape')close();if(e.key==='Tab'){const focusable=[...bg.querySelectorAll('button,a,input,select,textarea,summary')].filter(el=>!el.disabled&&el.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
    bg.querySelector('.close').focus();return bg;
  }
  function connectionFields(){
    const current=hosted?'agent':state.settings?.backend==='agent'?'codex':state.settings?.backend||'codex';
    return `<label for="backend">Run with</label><select id="backend">${(hosted?[['agent','Built-in desktop agent']]:[['codex','Codex CLI · saved login'],['claude','Claude Code · analysis only'],['ollama','Ollama · analysis only'],['openai','OpenAI API · API key'],['anthropic','Anthropic API · API key']]).map(([id,label])=>`<option value="${id}" ${current===id?'selected':''}>${label}</option>`).join('')}</select><div id="connection-options"></div>`;
  }
  function bindConnectionFields(){bind('backend','change',connectionOptions);connectionOptions();}
  function connectionOptions(){
    const b=document.getElementById('backend')?.value,box=document.getElementById('connection-options');if(!box)return;
    if(b==='agent'){box.innerHTML='<p class="connection-note">Codex handles collection and matching in the desktop workspace.</p><button id="agent-setup" class="text-button">Open desktop workspace ↗</button>';bind('agent-setup','click',()=>agentModal().catch(e=>toast(e.message)));return;}
    if(b==='codex'){box.innerHTML='<p class="connection-note">Connect your Codex subscription. Research, progress, and results stay in this app.</p><button id="agent-setup" class="text-button">Connect Codex & Luma ↗</button>';bind('agent-setup','click',()=>agentModal().catch(e=>toast(e.message)));return;}
    const saved=b===state.settings?.backend?state.settings?.model||'':'';
    box.innerHTML=`<label for="model">Model ${['codex','claude'].includes(b)?'<span class="muted">optional</span>':''}</label><input id="model" value="${esc(saved)}" placeholder="${b==='ollama'?'Installed model name':['openai','anthropic'].includes(b)?'Model ID from your provider':'Use the CLI default'}">${['openai','anthropic'].includes(b)?`<label for="api-key">API key</label><input id="api-key" type="password" autocomplete="off" spellcheck="false" placeholder="${state.connections?.[b]?.key_present?'Key available · leave blank to keep':'Paste your API key'}"><p class="hint">Session only. Never written to disk or sent to the browser again. API usage is billed separately.</p>${state.connections?.[b]?.key_present?'<button id="clear-key" class="text-button">Forget session key</button>':''}`:`<p class="connection-note">${b==='ollama'?'Runs on your local Ollama server.':`Uses ${b==='codex'?'Codex':'Claude Code'}’s saved login and normal account limits.`}</p><button id="check-connection" class="text-button">Check ${b==='ollama'?'server':'login'}</button><div id="check-result" class="hint" role="status"></div>`}`;
    bind('clear-key','click',async()=>{try{Object.assign(state,await api('/api/settings',{backend:b,clear_key:true}));connectionOptions();toast('Session key removed. Environment credentials, if set, still apply.');}catch(e){toast(e.message);}});
    bind('check-connection','click',async e=>{e.target.disabled=true;document.getElementById('check-result').textContent='Checking…';try{const result=await api('/api/check',{backend:b});document.getElementById('check-result').textContent=result.available?'Ready'+(result.models?.length?' · '+result.models.slice(0,4).join(', '):''):(result.note||'Sign in with the official CLI first.');}catch(error){document.getElementById('check-result').textContent=error.message;}finally{e.target.disabled=false;}});
  }
  async function saveConnection(){const data={backend:document.getElementById('backend').value,model:document.getElementById('model')?.value.trim()||''};const key=document.getElementById('api-key')?.value.trim();if(['openai','anthropic','ollama'].includes(data.backend)&&!data.model)throw new Error('Enter a model ID first.');if(['openai','anthropic'].includes(data.backend)&&!key&&!state.connections?.[data.backend]?.key_present)throw new Error('Add an API key for this session.');if(key)data.api_key=key;Object.assign(state,await api('/api/settings',data));document.getElementById('api-key')&&(document.getElementById('api-key').value='');}
  function connectionModal(){
    modal(`<div class="eyebrow">YOUR CONNECTIONS</div><h2>Keep setup light.</h2><div class="luma-connection"><span class="luma-symbol">${icon('event')}</span><div><strong>Luma</strong><p>Sign in once in the app’s research browser</p></div><button id="open-research-browser" class="secondary">Connect</button></div>${connectionFields()}<button id="save-connections" class="primary full">Save connection</button>`);
    bind('open-research-browser','click',()=>agentModal().catch(e=>toast(e.message)));bindConnectionFields();bind('save-connections','click',async()=>{try{await saveConnection();document.querySelector('.modal-backdrop').remove();toast('Connection saved.');}catch(e){toast(e.message);}});
  }
  function desktopLink(){
    const session={brief:state.brief,event:guide?.event,criteria_markdown:state.criteria_markdown};
    const encoded=btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(session))));
    return 'http://127.0.0.1:8765/#session='+encodeURIComponent(encoded);
  }
  async function agentModal(){
    if(hosted){
      modal(`<div class="eyebrow">YOUR AGENT, BUILT IN</div><h2>Let Codex take it from here.</h2><p>Continue in the desktop workspace to connect your Codex subscription, sign in to Luma, and prepare your guide.</p><a class="primary full" href="${esc(desktopLink())}" target="_blank" rel="noreferrer">Continue in desktop app ${icon('out')}</a><p class="hint">Your profile and event come with you. Results appear automatically in the desktop workspace.</p><details class="setup-detail"><summary>First time on this computer?</summary><p>Install Codex CLI, then launch the local app once:</p><pre>${esc(companionCommand())}</pre><p>Keep it running and select Continue above. The first Luma connection installs the app’s research browser.</p></details>`,'Desktop workspace');return;
    }
    const dialog=modal(`<div class="eyebrow">YOUR AGENT, BUILT IN</div><h2>Your guide. Handled.</h2><p>Connect once. Codex researches the room and brings the results here.</p><div id="agent-status" role="status"></div><div class="agent-connect-row"><button id="connect-codex" class="secondary">Connect Codex</button><button id="login-codex" class="secondary">Sign in with ChatGPT</button></div><div id="codex-login-link"></div><div id="agent-model-area"></div><div class="agent-connect-row"><button id="connect-luma" class="secondary">Connect Luma</button><button id="check-luma" class="secondary">Check Luma</button></div><p class="hint">Enter Luma verification codes only in the research browser. Keep that browser open while Codex works.</p>${eventId?`<label for="agent-budget">Profiles in this batch</label><select id="agent-budget"><option value="10">10 · quick first guide</option><option value="30">30 · a wider view</option><option value="100">100 · deeper research</option></select><button id="prepare-agent" class="primary full">Prepare my guide ${icon('spark')}</button>`:''}<p class="hint">Uses your Codex subscription and its limits. Professional sources are sent to that model. You can stop at any time.</p>`,'Your agent');
    async function sync(){
      if(!dialog.isConnected){clearInterval(timer);return;}
      try{const value=await api('/api/agent');state.agent=value;
        dialog.querySelector('#agent-status').innerHTML=`<div class="agent-status-grid"><span>${value.connected?'✓':'○'} Codex ${value.connected?'connected':'not connected'}</span><span>${value.luma_connected?'✓':'○'} Luma ${value.luma_connected?'connected':'not connected'}</span></div><p class="hint">${esc(value.error||value.needs_action||value.message||'')}</p>`;
        for(const id of ['connect-codex','login-codex','connect-luma','check-luma','prepare-agent'])if(dialog.querySelector('#'+id))dialog.querySelector('#'+id).disabled=!!value.busy;
        dialog.querySelector('#login-codex').hidden=!!value.connected;
        if(value.models?.length&&!dialog.querySelector('#agent-model'))dialog.querySelector('#agent-model-area').innerHTML=`<label for="agent-model">Model</label><select id="agent-model">${value.models.map(m=>`<option value="${esc(m.id)}" ${(state.settings.model?m.id===state.settings.model:m.default)?'selected':''}>${esc(m.name)}</option>`).join('')}</select>`;
        dialog.querySelector('#codex-login-link').innerHTML=value.auth_url?`<a class="primary full" href="${esc(value.auth_url)}" target="_blank" rel="noreferrer">Complete OpenAI sign-in ↗</a>`:'';
      }catch(error){dialog.querySelector('#agent-status').textContent=error.message;}
    }
    const timer=setInterval(sync,1500);
    async function action(name){try{await api('/api/agent',{action:name});await sync();}catch(error){toast(error.message);}}
    dialog.querySelector('#connect-codex').addEventListener('click',()=>action('connect'));
    dialog.querySelector('#login-codex').addEventListener('click',()=>action('login'));
    dialog.querySelector('#connect-luma').addEventListener('click',()=>action('luma'));
    dialog.querySelector('#check-luma').addEventListener('click',()=>action('check_luma'));
    dialog.querySelector('#prepare-agent')?.addEventListener('click',async()=>{try{await api('/api/settings',{backend:'codex',model:dialog.querySelector('#agent-model')?.value||''});await api('/api/agent',{action:'prepare',event_id:eventId,limit:Number(dialog.querySelector('#agent-budget').value)});dialog.remove();clearInterval(timer);view='discover';await refresh();}catch(error){toast(error.message);}});
    await sync();
    if(!state.agent?.connected&&!state.agent?.busy)await action('connect');
  }
  function analysisModal(){
    if(hosted||['agent','codex'].includes(state.settings?.backend)||!guide?.counts.captured){agentModal().catch(e=>toast(e.message));return;}
    const dialog=modal(`<div class="eyebrow">REFRESH YOUR GUIDE</div><h2>Find the overlap.</h2>${connectionFields()}<p class="hint">Reanalyze collected professional excerpts. Use Prepare with Codex to collect more people.</p><button id="start-analysis" class="primary full">Prepare guide</button>`,'Analysis');bindConnectionFields();
    bind('start-analysis','click',async e=>{e.target.disabled=true;try{await saveConnection();if(['agent','codex'].includes(state.settings.backend)){dialog.remove();await agentModal();return;}await api('/api/analyze',{event_id:eventId,backend:state.settings.backend,model:state.settings.model||null});dialog.remove();await refresh();}catch(error){toast(error.message);e.target.disabled=false;}});
  }
  function companionCommand(){return "uvx --python 3.13 --from 'luma-profile-review[app] @ git+https://github.com/EmaRimoldi/luma-profile-review.git@feature/personal-event-guide' luma-review serve --port 8765";}
  function download(value,name){const href=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=href;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(href),1000);}
  function exportModal(){
    const dialog=modal(`<div class="eyebrow">TAKE IT WITH YOU</div><h2>Your people. <em>Your guide.</em></h2><button id="download-json" class="primary full">Download reviewed guide JSON</button>${!hosted?`<a class="secondary full" href="/api/export?event=${encodeURIComponent(eventId)}" style="margin-top:12px">Download standalone HTML</a>`:''}<p class="hint">The file includes your profile, reviewed people, and source excerpts.</p>`,'Export guide');
    bind('download-json','click',async()=>{try{download(hosted?await api('/api/guide?event='+encodeURIComponent(eventId)):await api('/api/export?format=json&event='+encodeURIComponent(eventId)),'my-event-guide.json');dialog.remove();}catch(e){toast(e.message);}});
  }
  async function boot(){
    await refresh();
    const encoded=new URLSearchParams(location.hash.slice(1)).get('session');
    if(hosted||!encoded)return;
    history.replaceState(null,'',location.pathname);
    try{
      if(encoded.length>120000)throw new Error('That profile is too large.');
      const session=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))));
      if(!session.brief)throw new Error('Create your profile first.');
      const dialog=modal(`<div class="eyebrow">PICK UP WHERE YOU LEFT OFF</div><h2>Your profile. Already here.</h2><p>${esc(session.brief.work)}</p><p class="hint">${esc(session.event?.name||'Add your event next.')}</p><button id="accept-handoff" class="primary full">Use this profile & continue</button><p class="hint">This replaces the active profile in this local workspace. Existing event evidence is retained.</p>`,'Continue setup');
      dialog.querySelector('#accept-handoff').addEventListener('click',async()=>{try{const result=await api('/api/handoff',session);eventId=result.event_id||eventId;dialog.remove();view='discover';await api('/api/settings',{backend:'codex',setup_complete:true});await refresh();await agentModal();}catch(error){toast(error.message);}});
    }catch(error){toast(error.message);}
  }
  boot().catch(error=>{app.innerHTML=`<main class="empty"><h2>Could not load your guide.</h2><p>${esc(error.message)}</p><button onclick="location.reload()">Reload</button></main>`;});
})();
