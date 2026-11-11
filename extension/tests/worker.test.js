const {test} = require('node:test');
const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
const {BridgeWorker, validateGenerate, trustedSender} = require('../src/worker.js');

const ID='pibjjmjbipbifeddoahjagcinihkcgnf';
const post=(id='123')=>({id,url:`https://x.com/tester/status/${id}`,author:'@tester',text:'AI 工具越多，越需要先想清楚具体的问题。'});
function event(){const listeners=[];return {addListener(fn){listeners.push(fn)},fire(...args){for(const fn of listeners)fn(...args)}};}
function storage(seed={}){const data={...seed};return {async get(){return {...data}},async set(value){Object.assign(data,value)},data};}
function harness(seed={}){
 const native=[];const tabs=new Map([[1,{id:1,active:true,url:post().url}]]);
 const local=storage(seed), session=storage();
 const worker=new BridgeWorker({extensionId:ID,crypto:webcrypto,local,session,getTab:async id=>tabs.get(id),getWindow:async()=>({focused:true}),
  connectNative:()=>{const p={onMessage:event(),onDisconnect:event(),sent:[],postMessage(m){this.sent.push(m)},disconnect(){this.closed=true}};native.push(p);return p;},
  setTimeout,clearTimeout,timeoutMs:1000});
 function port(tabId=1,url='https://x.com/home'){
  const p={name:'suishou-page',sender:{id:ID,frameId:0,tab:{id:tabId,windowId:1},url},onMessage:event(),onDisconnect:event(),sent:[],postMessage(m){this.sent.push(m)},disconnect(){this.closed=true}};
  worker.attach(p);return p;
 }
 return {worker,native,tabs,local,session,port,async flush(){await new Promise(r=>setTimeout(r,15))},close(){worker.dispose()}};
}
const generate=(id='r1',p=post(),extra={})=>({type:'generate',id,post:p,style:'自然',force:false,previous:'',...extra});

test('only trusted top-level extension ports on exact X hosts are accepted',()=>{
 const sender={id:ID,frameId:0,tab:{id:1},url:'https://x.com/home'};
 assert.equal(trustedSender(sender,ID),true);
 for(const bad of [{url:'https://x.com.evil.test/a'},{url:'http://x.com/home'},{id:'other'},{frameId:2},{tab:null}])assert.equal(trustedSender({...sender,...bad},ID),false);
});
test('request validator bounds inputs and rejects extra fields and identity mismatch',()=>{
 assert.ok(validateGenerate(generate()));
 for(const bad of [{endpoint:'https://evil.test'},{key:'secret'},{post:{...post(),id:'999'}},{post:{...post(),author:['@tester']}},{style:'热点'},{force:'yes'},{previous:'a'.repeat(501)},{post:{...post(),text:'a'.repeat(3001)}}]) assert.throws(()=>validateGenerate({...generate(),...bad}));
});
test('attach has automatic mode off and does not start native or model',async()=>{
 const h=harness();try{const p=h.port();await h.flush();assert.deepEqual(p.sent[0],{type:'settings',auto:false,autoCopy:false});assert.equal(h.native.length,0)}finally{h.close()}
});
test('automatic opt-in persists and is broadcast to already-open pages',async()=>{
 const h=harness();try{const a=h.port(),b=h.port();await h.flush();a.onMessage.fire({type:'set-auto',enabled:true});await h.flush();assert.equal(h.local.data.autoGenerate,true);assert.equal(a.sent.at(-1).auto,true);assert.equal(b.sent.at(-1).auto,true);assert.equal(h.native.length,0)}finally{h.close()}
});
test('same post and style reuses session cache; only force regenerates',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();assert.equal(h.native.length,1);const req=h.native[0].sent[0];assert.equal(req.type,'generate');assert.equal(req.style,'自然');
 h.native[0].onMessage.fire({v:1,type:'result',id:req.id,text:'工具越多越要看清需求，省下多少实际工作才是判断标准。',usage:{total_tokens:80}});await h.flush();
 p.onMessage.fire(generate('r2'));await h.flush();assert.equal(h.native[0].sent.filter(x=>x.type==='generate').length,1);assert.equal(p.sent.at(-1).cached,true);
 p.onMessage.fire(generate('r3',post(),{force:true}));await h.flush();assert.equal(h.native[0].sent.filter(x=>x.type==='generate').length,2);
 }finally{h.close()}
});
test('rapid duplicate requests do not create concurrent paid calls',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();p.onMessage.fire(generate('r2',post(),{force:true}));await h.flush();assert.equal(h.native[0].sent.filter(x=>x.type==='generate').length,1);assert.equal(p.sent.at(-1).code,'busy')}finally{h.close()}
});
test('navigation cancels old native request and ignores stale success',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();const old=h.native[0].sent[0];h.tabs.set(1,{id:1,active:true,url:post('456').url});h.worker.navigationChanged(1,post('456').url);p.onMessage.fire(generate('r2',post('456')));await h.flush();
 assert.ok(h.native[0].sent.some(x=>x.type==='cancel'&&x.id===old.id));h.native[0].onMessage.fire({v:1,type:'result',id:old.id,text:'old wrong draft',usage:{}});await h.flush();assert.equal(p.sent.some(x=>x.text==='old wrong draft'),false);
 }finally{h.close()}
});
test('body edits and style changes invalidate cache identity',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();const n=h.native[0];n.onMessage.fire({v:1,type:'result',id:n.sent[0].id,text:'先把需求写清楚，比不断换工具更容易看到效果。',usage:{}});await h.flush();p.onMessage.fire(generate('r2',{...post(),text:'更新后的原帖正文，和之前的内容不同。'}));await h.flush();assert.equal(n.sent.filter(x=>x.type==='generate').length,2)}finally{h.close()}
});
test('background tab and mismatched current URL are rejected before native connection',async()=>{
 const h=harness();try{const p=h.port();await h.flush();h.tabs.set(1,{id:1,active:false,url:post().url});p.onMessage.fire(generate());await h.flush();assert.equal(h.native.length,0);h.tabs.set(1,{id:1,active:true,url:post('456').url});p.onMessage.fire(generate('r2'));await h.flush();assert.equal(h.native.length,0);assert.equal(p.sent.at(-1).type,'error')}finally{h.close()}
});
test('page disconnect cancels and closes native process without reconnect',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();p.onDisconnect.fire();await h.flush();assert.equal(h.native[0].closed,true);assert.equal(h.native.length,1)}finally{h.close()}
});
test('native error is displayed once and never automatically retried',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();const n=h.native[0];n.onMessage.fire({v:1,type:'error',id:n.sent[0].id,code:'api',message:'DeepSeek 账户余额不足，请充值后重试。'});await h.flush();assert.match(p.sent.at(-1).message,/余额/);assert.equal(n.sent.filter(x=>x.type==='generate').length,1)}finally{h.close()}
});
test('malformed native messages fail safely and never render arbitrary payloads',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();const n=h.native[0];n.onMessage.fire({v:1,type:'result',id:n.sent[0].id,text:{private:'bad'},usage:{}});await h.flush();assert.equal(p.sent.at(-1).type,'error');assert.equal(JSON.stringify(p.sent).includes('private'),false)}finally{h.close()}
});
test('toolbar popup preference updates reach already connected pages',async()=>{
 const h=harness();try{const p=h.port();await h.flush();await h.worker.settingsChanged(true);assert.equal(p.sent.at(-1).auto,true);await h.worker.settingsChanged(false);assert.equal(p.sent.at(-1).auto,false)}finally{h.close()}
});
test('cancel while tab validation is pending prevents any native request',async()=>{
 const h=harness();try{let finish;h.worker.d.getTab=()=>new Promise(r=>{finish=r});const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();p.onMessage.fire({type:'cancel',id:'r1'});finish({id:1,active:true,url:post().url});await h.flush();assert.equal(h.native.length,0)}finally{h.close()}
});
test('deadline aborts once without automatic reconnect or retry',async()=>{
 const h=harness();try{h.worker.d.timeoutMs=10;const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();await h.flush();const n=h.native[0];assert.equal(n.sent.filter(x=>x.type==='generate').length,1);assert.equal(n.sent.filter(x=>x.type==='cancel').length,1);assert.equal(p.sent.at(-1).code,'timeout')}finally{h.close()}
});
test('visible tab in unfocused Edge window cannot start paid work',async()=>{
 const h=harness();try{h.worker.d.getWindow=async()=>({focused:false});const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();assert.equal(h.native.length,0);assert.equal(p.sent.at(-1).code,'context')}finally{h.close()}
});
test('switching windows cancels active request',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();h.worker.focused(2);assert.equal(h.native[0].sent.at(-1).type,'cancel');assert.equal(p.sent.at(-1).type,'cancelled')}finally{h.close()}
});
test('rapid preference changes are serialized and final off state wins',async()=>{
 const h=harness();try{const p=h.port();await h.flush();const write=h.local.set;h.local.set=async v=>{await new Promise(r=>setTimeout(r,v.autoGenerate?15:1));await write(v)};p.onMessage.fire({type:'set-auto',enabled:true});p.onMessage.fire({type:'set-auto',enabled:false});await h.worker.preferenceWrites;assert.equal(h.local.data.autoGenerate,false);assert.equal(h.worker.auto,false);assert.equal(p.sent.at(-1).auto,false)}finally{h.close()}
});
test('cancelled worker suspension still accepts next explicit request',async()=>{
 const h=harness();try{const p=h.port();await h.flush();p.onMessage.fire(generate());await h.flush();h.worker.suspend();assert.equal(h.native[0].closed,true);assert.equal(h.worker.dead,false);p.onMessage.fire(generate('r2'));await h.flush();assert.equal(h.native.length,2);assert.equal(h.native[1].sent[0].type,'generate');const another=h.port();await h.flush();assert.equal(another.closed,undefined)}finally{h.close()}
});

test('copy opt-in loads independently from generation and starts no native work',async()=>{
 const h=harness({autoCopy:true});try{const p=h.port();await h.flush();assert.deepEqual(p.sent[0],{type:'settings',auto:false,autoCopy:true});assert.equal(h.native.length,0)}finally{h.close()}
});
test('copy opt-in persists and broadcasts without changing automatic generation',async()=>{
 const h=harness({autoGenerate:true});try{const a=h.port(),b=h.port();await h.flush();a.onMessage.fire({type:'set-auto-copy',enabled:true});await h.worker.preferenceWrites;assert.equal(h.local.data.autoCopy,true);assert.equal(h.local.data.autoGenerate,true);assert.deepEqual(a.sent.at(-1),{type:'settings',auto:true,autoCopy:true});assert.deepEqual(b.sent.at(-1),a.sent.at(-1));assert.equal(h.native.length,0)}finally{h.close()}
});
test('copy setting rejects unexpected fields and non-boolean values',async()=>{
 const h=harness();try{const p=h.port();await h.flush();for(const message of [{type:'set-auto-copy',enabled:'true'},{type:'set-auto-copy',enabled:true,extra:true}])p.onMessage.fire(message);await h.flush();assert.equal(h.local.data.autoCopy,undefined);assert.equal(h.worker.autoCopy,false);assert.equal(h.native.length,0)}finally{h.close()}
});
test('copy storage failures use their own error identity and preserve generation setting',async()=>{
 const h=harness({autoGenerate:true});try{const p=h.port();await h.flush();h.local.set=async()=>{throw Error('unavailable')};p.onMessage.fire({type:'set-auto-copy',enabled:true});await h.worker.preferenceWrites;assert.equal(p.sent.at(-1).id,'copy-settings');assert.equal(p.sent.at(-1).code,'storage');assert.equal(h.worker.auto,true);assert.equal(h.worker.autoCopy,false)}finally{h.close()}
});
test('interleaved preference writes serialize independently and final copy off wins',async()=>{
 const h=harness();try{const p=h.port();await h.flush();const write=h.local.set;h.local.set=async v=>{await new Promise(r=>setTimeout(r,v.autoCopy?15:1));await write(v)};p.onMessage.fire({type:'set-auto-copy',enabled:true});p.onMessage.fire({type:'set-auto',enabled:true});p.onMessage.fire({type:'set-auto-copy',enabled:false});await h.worker.preferenceWrites;assert.equal(h.local.data.autoGenerate,true);assert.equal(h.local.data.autoCopy,false);assert.deepEqual(p.sent.at(-1),{type:'settings',auto:true,autoCopy:false});assert.equal(h.native.length,0)}finally{h.close()}
});
test('toolbar copy preference changes broadcast alongside automatic generation',async()=>{
 const h=harness();try{const p=h.port();await h.flush();await Promise.all([h.worker.settingsChanged(true),h.worker.copySettingsChanged(true)]);assert.deepEqual(p.sent.at(-1),{type:'settings',auto:true,autoCopy:true});await h.worker.copySettingsChanged(false);assert.deepEqual(p.sent.at(-1),{type:'settings',auto:true,autoCopy:false})}finally{h.close()}
});
test('delayed startup cannot restore stale copy state or discard a different preference update',async()=>{
 let finish;
 const worker=new BridgeWorker({local:{get:()=>new Promise(resolve=>{finish=resolve})},session:storage()});
 try{
  const pending=[worker.settingsChanged(true),worker.copySettingsChanged(true),worker.copySettingsChanged(false)];
  finish({autoGenerate:false,autoCopy:true});await Promise.all(pending);
  assert.equal(worker.auto,true);assert.equal(worker.autoCopy,false);
 }finally{worker.dispose()}
});
