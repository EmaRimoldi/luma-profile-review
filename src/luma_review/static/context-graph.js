/* Cytoscape presentation only. A shared context never becomes a personal relationship. */
(function(root){
  'use strict';
  function elements(graph,people=[]){
    const connected=new Set(graph.edges.flatMap(e=>[e.source,e.target]));
    const portraits=new Map(people.map(p=>[p.profile_url,p.photo_url]));
    return [...graph.nodes.filter(n=>connected.has(n.id)).map(n=>({data:{...n,name:n.label.replace(' (demo)',''),photo:portraits.get(n.id)||''}})),
      ...graph.edges.map(e=>({data:{...e}}))];
  }
  function mount(container,graph,people,onSelect){
    if(typeof root.cytoscape!=='function')throw new Error('The graph library could not load. Reload to try again.');
    const reduced=root.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const cy=root.cytoscape({container,elements:elements(graph,people),minZoom:.15,maxZoom:3,wheelSensitivity:.2,
      layout:{name:'cose',animate:false,randomize:true,padding:45,nodeRepulsion:14500,idealEdgeLength:110,componentSpacing:100,numIter:650},
      style:[
        {selector:'node',style:{label:'data(name)','font-family':'DM Sans, sans-serif','font-size':12,'font-weight':450,color:'#5d5567','text-valign':'bottom','text-margin-y':8,'text-wrap':'ellipsis','text-max-width':112,'background-color':'#d7c9e5','border-width':2,'border-color':'#ffffff',width:30,height:30,'overlay-opacity':0,'text-background-color':'#faf8fd','text-background-opacity':.78,'text-background-padding':3}},
        {selector:'node[type="person"]',style:{'background-color':'#a995bb',width:38,height:38}},
        {selector:'node[photo != ""]',style:{'background-image':'data(photo)','background-fit':'cover','background-clip':'node'}},
        {selector:'node[type="user"]',style:{'background-color':'#5f4b79','border-width':4,'border-color':'#e3d9ee',width:43,height:43,'font-weight':650}},
        {selector:'node[type="topic"]',style:{'background-color':'#ccbce1',width:22,height:22}},
        {selector:'node[type="organization"]',style:{'background-color':'#a8beb0',shape:'round-rectangle',width:27,height:27}},
        {selector:'node[type="project"]',style:{'background-color':'#d8c49e',shape:'diamond',width:25,height:25}},
        {selector:'edge',style:{width:1.2,'line-color':'#ddd4e6','curve-style':'bezier','overlay-opacity':0}},
        {selector:'.muted',style:{opacity:.12,'text-opacity':.15}},
        {selector:'.focus',style:{'border-color':'#8c74a3','border-width':3,'z-index':10}},
        {selector:'edge.focus',style:{'line-color':'#aa93be',width:2,opacity:1}},
        {selector:':selected',style:{'border-color':'#6e5287','border-width':4}},
        {selector:'.filtered',style:{display:'none'}}
      ]});
    // Start close enough to read; Fit graph gives the full-room overview.
    if(cy.zoom()<.6){cy.zoom(.6);const you=cy.nodes('[type="user"]');cy.center(you.length?you:cy.nodes().first());}
    function focus(id){
      const node=cy.getElementById(id);if(!node.length)return;
      cy.elements().removeClass('muted focus');const neighborhood=node.closedNeighborhood();
      cy.elements().not(neighborhood).addClass('muted');neighborhood.addClass('focus');
      cy.nodes().unselect();node.select();
      if(reduced)cy.center(node);else cy.animate({center:{eles:node},duration:280});
      onSelect(node.data(),graph.edges.filter(e=>e.source===id||e.target===id));
    }
    cy.on('tap','node',e=>focus(e.target.id()));
    cy.on('tap',e=>{if(e.target===cy){cy.elements().removeClass('muted focus');cy.nodes().unselect();}});
    return {
      focus,
      fit(){cy.elements().removeClass('muted focus');cy.nodes().unselect();cy.fit(cy.elements(':visible'),42);},
      zoom(factor){cy.zoom({level:Math.max(.15,Math.min(3,cy.zoom()*factor)),renderedPosition:{x:cy.width()/2,y:cy.height()/2}});},
      filter(type){
        cy.elements().removeClass('filtered muted focus');
        if(type!=='all'){
          const contexts=cy.nodes().filter(n=>n.data('type')===type);
          const allowed=contexts.closedNeighborhood();cy.elements().not(allowed).addClass('filtered');
        }
        cy.fit(cy.elements(':visible'),45);
      },
      destroy(){cy.destroy();}
    };
  }
  const api={elements,mount};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PeopleContext=api;
})(typeof window==='undefined'?this:window);
