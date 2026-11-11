/* Real Edge engine + MV3 scripts, synthetic webpage and compiled synthetic host.
 * Never opens a real X session, writes the registry, or calls a paid model.
 * Run from project: node extension/tests/browser-smoke.cjs [artifact-directory]
 */
'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'../..'),ID='pibjjmjbipbifeddoahjagcinihkcgnf';
const EXTENSION=path.resolve(process.env.SUISHOU_TEST_EXTENSION_DIR||path.join(ROOT,'extension'));
const OUT=path.resolve(process.argv[2]||path.join(os.tmpdir(),'suishou-edge-check-'+Date.now()));
const EDGE=process.env.SUISHOU_TEST_EDGE||path.join(process.env['ProgramFiles(x86)']||'C:/Program Files (x86)','Microsoft/Edge/Application/msedge.exe');
const HOST=path.join(ROOT,'dist-edge-v1.2.1/SuishouReplyBridge.exe');
const checks={};let browser,client,native,pageSession,report={mode:'Edge MV3 + intercepted synthetic DOM + compiled --synthetic host',real_x_tested:false,paid_api_calls:0};
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function until(fn,label,ms=20000){const deadline=Date.now()+ms;let lastError;while(Date.now()<deadline){try{const r=await fn();if(r)return r}catch(e){lastError=e}await delay(60)}throw Error('Timed out: '+label+(lastError?' ('+lastError.message+')':''))}
class CDP {
 constructor(ws){this.ws=ws;this.seq=0;this.pending=new Map();this.listeners=[];ws.addEventListener('message',e=>{const m=JSON.parse(String(e.data));if(m.id){const p=this.pending.get(m.id);if(p){this.pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}}else for(const f of this.listeners)f(m)});}
 static async connect(url){const ws=new WebSocket(url);await new Promise((res,rej)=>{ws.addEventListener('open',res,{once:true});ws.addEventListener('error',rej,{once:true})});return new CDP(ws)}
 call(method,params={},sessionId){return new Promise((resolve,reject)=>{const id=++this.seq;const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout '+method))},15000);this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
 async evaluate(expression,sessionId){const r=await this.call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.text+' '+r.exceptionDetails.exception?.description);return r.result.value}
 close(){for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('closed'))}this.pending.clear();this.ws.close()}
}
function descendants(node){return [node,...(node.children||[]).flatMap(descendants),...(node.shadowRoots||[]).flatMap(descendants)]}
async function main(){
 await fs.mkdir(OUT,{recursive:true});
 const profile=path.join(OUT,'isolated-profile');
 browser=spawn(EDGE,['--headless=new','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-breakpad',`--user-data-dir=${profile}`,'--remote-debugging-port=0',`--disable-extensions-except=${EXTENSION}`,`--load-extension=${EXTENSION}`,'about:blank'],{windowsHide:true,stdio:'ignore'});
 browser.on('error',e=>{report.launch_error=e.message});
 const lines=await until(async()=>String(await fs.readFile(path.join(profile,'DevToolsActivePort'))).trim().split(/\r?\n/),'Edge debug port');
 client=await CDP.connect(`ws://127.0.0.1:${lines[0]}${lines[1]}`);
 report.browser=(await client.call('Browser.getVersion')).product;
 const target=await client.call('Target.createTarget',{url:'about:blank'});
 const {sessionId:page}=await client.call('Target.attachToTarget',{targetId:target.targetId,flatten:true});
 pageSession=page;
 const fixture=await fs.readFile(path.join(__dirname,'fixtures/current-post.html'),'utf8');
 client.listeners.push(m=>{if(m.method==='Fetch.requestPaused'&&m.sessionId===page){const {requestId,request}=m.params;const valid=/^https:\/\/x\.com\/signal\/status\/[0-9]+$/.test(request.url);client.call(valid?'Fetch.fulfillRequest':'Fetch.failRequest',valid?{requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'text/html; charset=utf-8'}],body:Buffer.from(fixture).toString('base64')}:{requestId,errorReason:'BlockedByClient'},page).catch(()=>{})}});
 await client.call('Fetch.enable',{patterns:[{urlPattern:'*'}]},page);
 await client.call('Page.enable',{},page);await client.call('Runtime.enable',{},page);await client.call('DOM.enable',{},page);
 await client.call('Emulation.setDeviceMetricsOverride',{width:1365,height:900,deviceScaleFactor:1,mobile:false},page);
 await client.call('Emulation.setFocusEmulationEnabled',{enabled:true},page);
 await client.call('Page.navigate',{url:'https://x.com/signal/status/123'},page);
 await client.call('Page.bringToFront',{},page);
 const workerInfo=await until(async()=>{const t=await client.call('Target.getTargets');return t.targetInfos.find(t=>t.type==='service_worker'&&t.url===`chrome-extension://${ID}/src/background.js`)},'loaded MV3 worker');
 const {sessionId:worker}=await client.call('Target.attachToTarget',{targetId:workerInfo.targetId,flatten:true});
 await client.call('Runtime.enable',{},worker);
 checks.mv3_loaded_with_fixed_id=true;
 // Focus is emulated only in this isolated headless test, not claimed as Windows UI acceptance.
 await client.evaluate('bridge.d.getWindow=async()=>({focused:true});',worker);
 await client.call('Runtime.addBinding',{name:'suishouTestPipe'},worker);
 await client.evaluate('globalThis.__timerError="";const testTimer=bridge.d.setTimeout;bridge.d.setTimeout=function(...args){try{return testTimer.apply(this,args)}catch(e){globalThis.__timerError=String(e);throw e}};',worker);
 const requests=[],cancelled=[],queued=[];let hold=false,nativeBuffer=Buffer.alloc(0);
 function startNative(){
  if(native&&!native.killed&&native.exitCode===null)return;
  native=spawn(HOST,['--synthetic',`chrome-extension://${ID}/`],{windowsHide:true,stdio:['pipe','pipe','ignore']});
  native.stdout.on('data',b=>{nativeBuffer=Buffer.concat([nativeBuffer,b]);while(nativeBuffer.length>=4){const n=nativeBuffer.readUInt32LE();if(nativeBuffer.length<n+4)break;const message=JSON.parse(nativeBuffer.subarray(4,n+4));nativeBuffer=nativeBuffer.subarray(n+4);if(hold)queued.push(message);else deliver(message)}});
 }
 async function deliver(m){await client.evaluate(`globalThis.__nativeTestPort?.emit(${JSON.stringify(m)})`,worker).catch(()=>{})}
 client.listeners.push(m=>{if(m.method==='Runtime.bindingCalled'&&m.sessionId===worker&&m.params.name==='suishouTestPipe'){
   const message=JSON.parse(m.params.payload);if(message.type==='__disconnect'){native?.stdin.end();return}if(message.type==='generate')requests.push(message);if(message.type==='cancel')cancelled.push(message);
   startNative();const data=Buffer.from(JSON.stringify(message));const header=Buffer.alloc(4);header.writeUInt32LE(data.length);native.stdin.write(Buffer.concat([header,data]));
 }});
 await client.evaluate(`bridge.d.connectNative=()=>{const listeners=[],disconnects=[];const p={onMessage:{addListener:f=>listeners.push(f)},onDisconnect:{addListener:f=>disconnects.push(f)},postMessage:m=>suishouTestPipe(JSON.stringify(m)),disconnect:()=>suishouTestPipe(JSON.stringify({type:'__disconnect'})),emit:m=>listeners.forEach(f=>f(m))};globalThis.__nativeTestPort=p;return p;}`,worker);
 async function shadow(){const doc=await client.call('DOM.getDocument',{depth:-1,pierce:true},page);const host=descendants(doc.root).find(n=>n.attributes?.includes('suishou-reply-extension'));if(!host?.shadowRoots?.[0])return null;return (await client.call('DOM.resolveNode',{backendNodeId:host.shadowRoots[0].backendNodeId},page)).object.objectId}
 async function panel(fn,args=[]){const objectId=await until(shadow,'closed panel shadow root');const r=await client.call('Runtime.callFunctionOn',{objectId,functionDeclaration:fn,arguments:args.map(value=>({value})),returnByValue:true,awaitPromise:true},page);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value}
 async function state(){const s=await panel('function(){return {source:this.querySelector(".source").textContent,draft:this.querySelector("textarea").value,status:this.querySelector(".state").textContent,auto:this.querySelectorAll("input[type=checkbox]")[0].checked,autoCopy:this.querySelectorAll("input[type=checkbox]")[1].checked,toast:this.querySelector(".toast").textContent}}');report.last_panel=s;return s;}
 async function click(label){return panel('function(label){const b=Array.from(this.querySelectorAll("button")).find(b=>b.textContent===label);if(!b||b.disabled)throw Error("button missing/disabled "+label);b.click()}',[label])}
 await until(async()=>{const s=await state();report.last_panel=s;return s.source.includes('AI 工具越来越多')},'post extraction');await delay(300);
 checks.auto_off_no_model=requests.length===0;assert.equal(checks.auto_off_no_model,true);
 const first=await state();checks.excludes_quote_reply_recommendation=!/引用内容|推荐帖，|一条评论/.test(first.source);assert.equal(checks.excludes_quote_reply_recommendation,true);
 report.tabs=await client.evaluate('Promise.all(Array.from(bridge.ports.values(),p=>chrome.tabs.get(p.tabId))).then(ts=>ts.map(t=>({id:t.id,active:t.active,url:t.url})))',worker);
 // Capture clipboard writes only in the isolated test world, never the user's clipboard.
 const worlds=[];client.listeners.push(m=>{if(m.method==='Runtime.executionContextCreated'&&m.sessionId===page)worlds.push(m.params.context)});
 await client.call('Runtime.disable',{},page);await client.call('Runtime.enable',{},page);
 const contentWorld=await until(async()=>worlds.find(w=>w.name===`chrome-extension://${ID}`||w.origin===`chrome-extension://${ID}`||w.name.includes(ID)),'extension isolated world');
 await client.call('Runtime.evaluate',{expression:'globalThis.__copiedTest="";globalThis.__copyCount=0;Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async value=>{globalThis.__copiedTest=value;globalThis.__copyCount++}}});',contextId:contentWorld.id},page);
 async function clipboard(){const r=await client.call('Runtime.evaluate',{expression:'({text:globalThis.__copiedTest,count:globalThis.__copyCount})',contextId:contentWorld.id,returnByValue:true},page);return r.result.value;}
 assert.equal((await state()).autoCopy,false);assert.equal((await clipboard()).count,0);checks.auto_copy_default_off=true;
 await panel('function(){const toggle=this.querySelectorAll("input[type=checkbox]")[1];toggle.checked=true;toggle.dispatchEvent(new Event("change",{bubbles:true}))}');
 await until(async()=>(await state()).autoCopy===true,'auto copy preference saved');assert.equal(await client.evaluate('chrome.storage.local.get("autoCopy").then(v=>v.autoCopy)',worker),true);assert.equal(requests.length,0);checks.auto_copy_persisted_without_generation=true;
 await client.evaluate("chrome.storage.local.set({autoGenerate:true})",worker);
 await until(async()=>{const s=await state();return s.draft||s.status.includes('本机')},'automatic native reply');
 report.runtime_probe=await client.evaluate('({binding:typeof suishouTestPipe,timerError:globalThis.__timerError,native:!!globalThis.__nativeTestPort})',worker);
 assert.match((await state()).draft,/工具多不代表效率高/);
 checks.auto_on_natural_once=requests.length===1&&requests[0].style==='自然';assert.equal(checks.auto_on_natural_once,true);
 checks.compiled_host_roundtrip=true;checks.correct_post_sent=requests[0].post.id==='123'&&!requests[0].post.text.includes('引用内容');assert.equal(checks.correct_post_sent,true);
 await until(async()=>(await state()).toast.includes('已自动复制'),'automatic copy feedback');assert.equal((await clipboard()).text,(await state()).draft);assert.equal((await clipboard()).count,1);checks.accepted_reply_auto_copied=true;
 const generatedShot=await client.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},page);await fs.writeFile(path.join(OUT,'edge-fixture-generated.png'),Buffer.from(generatedShot.data,'base64'));
 await panel('function(){this.querySelector(".collapse").click();this.querySelector(".mini").click()}');await delay(200);assert.equal(requests.length,1);checks.collapse_no_request=true;
 await client.evaluate('document.querySelector("#current-post").append(document.createTextNode(" "))',page);await delay(500);assert.equal(requests.length,1);checks.rerender_no_request=true;
 assert.equal((await clipboard()).count,1);checks.rerender_no_clipboard_write=true;
 await client.evaluate('document.querySelector("#native-send").onclick=()=>{window.__sent=true};',page);
 await panel('function(){const e=this.querySelector("textarea");e.value="先把实际需求说清楚，工具才能帮忙减少重复劳动。";e.dispatchEvent(new Event("input",{bubbles:true}))}');
 assert.equal((await clipboard()).count,1);checks.edit_does_not_overwrite_clipboard=true;
 await click('手动填充');
 const copied=await client.call('Runtime.evaluate',{expression:'globalThis.__copiedTest',contextId:contentWorld.id,returnByValue:true},page);
 assert.equal(copied.result.value,'先把实际需求说清楚，工具才能帮忙减少重复劳动。');checks.edited_copy_exact=true;
 const original=await client.evaluate('({text:document.querySelector("#native-composer [contenteditable]").textContent,sent:!!window.__sent})',page);assert.equal(original.text,'用户在原生回复框已有草稿');assert.equal(original.sent,false);checks.no_composer_mutation_or_send=true;
 await client.evaluate('document.querySelector("#current-post > [data-testid=tweetText]").textContent="原帖更新：仍要先确认需求，再选择适合的 AI 工具。"',page);await delay(400);assert.equal(requests.length,1);assert.equal((await state()).draft,copied.result.value);checks.dirty_preserved_after_source_update=true;
 // Current route changes first while React still shows the old article.
 hold=true;
 await client.evaluate('history.pushState({},"","/signal/status/456");',page);await delay(650);assert.equal(requests.length,1);checks.old_article_not_used_after_navigation=true;
 await client.evaluate('document.querySelector("#current-post > a").href="https://x.com/signal/status/456";document.querySelector("#current-post > [data-testid=tweetText]").textContent="新帖讨论 AI 编程：写代码快了，测试和代码审查更不能省。"',page);
 await until(()=>requests.length===2,'new post request');await until(()=>queued.some(m=>m.type==='result'),'held synthetic response');
 await client.evaluate('history.pushState({},"","/signal/status/789");document.querySelector("#current-post > a").href="https://x.com/signal/status/789";document.querySelector("#current-post > [data-testid=tweetText]").textContent="再一条帖子：Agent 的权限边界应该由使用者明确决定。"',page);
 await until(()=>requests.length===3,'third post request');hold=false;for(const m of queued.splice(0))await deliver(m);
 await until(async()=>(await state()).draft.length>0,'latest post reply');assert.ok(cancelled.some(c=>c.id===requests[1].id));checks.switch_cancels_old_request=true;checks.latest_post_identity=requests.at(-1).post.id==='789';assert.equal(checks.latest_post_identity,true);
 // Explicit style regeneration and safe failure injection.
 await click('幽默');await click('生成');await until(()=>requests.length===4,'manual humor');await until(async()=>(await state()).draft.length>0,'humor result');assert.equal(requests.at(-1).style,'幽默');checks.manual_style=true;
 hold=true;await click('重新生成');await until(()=>requests.length===5,'forced request');const errorId=requests.at(-1).id;await deliver({v:1,type:'error',id:errorId,code:'balance',message:'DeepSeek 账户余额不足，请充值后重试。'});await until(async()=>(await state()).status.includes('余额'),'balance feedback');await delay(350);assert.equal(requests.length,5);checks.balance_no_auto_retry=true;hold=false;queued.length=0;
 const shot=await client.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},page);await fs.writeFile(path.join(OUT,'edge-fixture-panel.png'),Buffer.from(shot.data,'base64'));
 await client.evaluate('chrome.storage.local.set({autoGenerate:false})',worker);await until(async()=>(await state()).auto===false,'switch off persisted');assert.equal(await client.evaluate('chrome.storage.local.get("autoGenerate").then(v=>v.autoGenerate)',worker),false);checks.auto_setting_persisted=true;
 await panel('function(){const toggle=this.querySelectorAll("input[type=checkbox]")[1];toggle.checked=false;toggle.dispatchEvent(new Event("change",{bubbles:true}))}');
 await until(async()=>(await state()).autoCopy===false,'auto copy disabled');const beforeRetry=(await clipboard()).count;
 // Fresh success then cached reuse from the worker, without a model call.
 await click('重试');await until(()=>requests.length===6,'manual retry');await until(async()=>(await state()).draft.length>0&&!(await state()).status.includes('余额'),'retry success');
 checks.retry_preserves_draft_and_requests=true;
 assert.equal((await clipboard()).count,beforeRetry);checks.auto_copy_off_preserves_clipboard=true;
 await client.call('Emulation.setDeviceMetricsOverride',{width:800,height:600,deviceScaleFactor:1,mobile:false},page);await delay(250);
 const bounds=await client.evaluate('(()=>{const r=document.querySelector("#suishou-reply-extension").getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}})()',page);assert.ok(bounds.left>=0&&bounds.right<=800&&bounds.top>=0&&bounds.bottom<=600);checks.small_viewport_layout=true;
 const smallShot=await client.call('Page.captureScreenshot',{format:'png'},page);await fs.writeFile(path.join(OUT,'edge-fixture-small.png'),Buffer.from(smallShot.data,'base64'));
 const active=await client.evaluate('bridge.ports.size',worker);assert.ok(active>0);
 await client.call('Target.closeTarget',{targetId:target.targetId});await until(async()=>(await client.evaluate('bridge.ports.size',worker))===0,'tab closed cleans ports');checks.tab_close_cleanup=true;
 await until(()=>native.exitCode!==null,'compiled host EOF exit');assert.equal(native.exitCode,0);checks.native_eof_exit=true;
 report.checks=checks;report.passed=Object.values(checks).every(Boolean);report.check_count=Object.keys(checks).length;
}
(async()=>{try{await main()}catch(e){report.passed=false;report.error=e.stack;report.checks=checks;process.exitCode=1;
 try{report.page=await client.evaluate('({url:location.href,focus:document.hasFocus(),visible:document.visibilityState,html:document.documentElement.outerHTML.slice(0,10000)})',pageSession);const shot=await client.call('Page.captureScreenshot',{format:'png'},pageSession);await fs.writeFile(path.join(OUT,'edge-failure.png'),Buffer.from(shot.data,'base64'));}catch{}
 }finally{
  try{native?.stdin.end()}catch{};try{await client?.call('Browser.close')}catch{};client?.close();
  if(browser && browser.exitCode===null)browser.kill();if(native && native.exitCode===null)native.kill();
  await fs.mkdir(OUT,{recursive:true});await fs.writeFile(path.join(OUT,'edge-browser-test.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}})();
