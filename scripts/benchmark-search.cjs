/* Reproducible synthetic latency check; says nothing about recommendation utility. */
const {performance} = require('node:perf_hooks');
const ProfileSearch = require('../src/luma_review/static/search.js');
for (const size of [1000,10000]) {
  const people=Array.from({length:size},(_,i)=>({name:`Person ${i}`,summary:i%3?'GPU infrastructure inference benchmarks':'Robotics motion planning',why:['Open source collaboration'],professional:{facts:[{value:`Company ${i%100}`} ]}}));
  const start=performance.now(),index=new ProfileSearch(people),build=performance.now()-start;
  const samples=[];for(let i=0;i<120;i++){const t=performance.now();index.search(['person 12','gpu infer','robotics','company 4'][i%4]);if(i>=20)samples.push(performance.now()-t);}
  samples.sort((a,b)=>a-b);
  console.log(JSON.stringify({profiles:size,index_build_ms:+build.toFixed(2),query_p50_ms:+samples[50].toFixed(2),query_p95_ms:+samples[95].toFixed(2),fixture:'synthetic; relevance unmeasured'}));
}
