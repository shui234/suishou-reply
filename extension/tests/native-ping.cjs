/* Requires Install.cmd registration. Sends ping only: no credential access or model call. */
'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),{spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'../..'),ID='pibjjmjbipbifeddoahjagcinihkcgnf';
const OUT=path.resolve(process.argv[2]||path.join(os.tmpdir(),'suishou-native-ping-'+Date.now()));
const EDGE=process.env.SUISHOU_TEST_EDGE||path.join(process.env['ProgramFiles(x86)']||'C:/Program Files (x86)','Microsoft/Edge/Application/msedge.exe');
let browser,ws,seq=0;const pending=new Map();
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){let last;for(let i=0;i<200;i++){try{const v=await fn();if(v)return v}catch(e){last=e}await delay(50)}throw last||Error('Browser timeout')}
function call(method,params={},sessionId){return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method))},10000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
(async()=>{const result={mode:'real Edge Native Messaging ping',paid_api_calls:0,credential_access:false};try{
 await fs.mkdir(OUT,{recursive:true});const profile=path.join(OUT,'profile');
 browser=spawn(EDGE,['--headless=new','--no-first-run','--disable-background-networking','--disable-sync',`--user-data-dir=${profile}`,'--remote-debugging-port=0',`--disable-extensions-except=${path.join(ROOT,'extension')}`,`--load-extension=${path.join(ROOT,'extension')}`,'about:blank'],{windowsHide:true,stdio:'ignore'});
 const lines=await wait(async()=>String(await fs.readFile(path.join(profile,'DevToolsActivePort'))).trim().split(/\r?\n/));
 ws=new WebSocket(`ws://127.0.0.1:${lines[0]}${lines[1]}`);await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true})});
 ws.addEventListener('message',event=>{const m=JSON.parse(String(event.data));const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}});
 result.browser=(await call('Browser.getVersion')).product;
 const {targetId}=await call('Target.createTarget',{url:`chrome-extension://${ID}/popup.html`});
 const {sessionId}=await call('Target.attachToTarget',{targetId,flatten:true});
 await wait(async()=>{const r=await call('Runtime.evaluate',{expression:'typeof chrome.runtime.sendNativeMessage',returnByValue:true},sessionId);return r.result.value==='function'});
 const answer=await call('Runtime.evaluate',{expression:'new Promise(resolve=>chrome.runtime.sendNativeMessage("com.suishou.reply",{v:1,type:"ping",id:"edge_native_ping"},reply=>resolve({reply,error:chrome.runtime.lastError?.message||null})))',awaitPromise:true,returnByValue:true},sessionId);
 if(answer.exceptionDetails)throw Error(answer.exceptionDetails.text);
 result.response=answer.result.value;
 result.passed=result.response?.reply?.type==='ready'&&result.response.reply.version==='1.2.1'&&!result.response.error;
 if(!result.passed)process.exitCode=1;
 }catch(e){result.passed=false;result.error=e.message;process.exitCode=1}finally{
 try{await call('Browser.close')}catch{};for(const p of pending.values())clearTimeout(p.timer);pending.clear();try{ws?.close()}catch{};
 if(browser&&browser.exitCode===null)browser.kill();await fs.mkdir(OUT,{recursive:true});await fs.writeFile(path.join(OUT,'edge-native-ping.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }})();
