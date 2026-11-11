'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const postTools=require('../src/post.js');
const {DraftController}=require('../src/controller.js');
const source=fs.readFileSync(path.join(__dirname,'../src/content.js'),'utf8');
function events(target={}) {
  const listeners=new Map();
  target.addEventListener=(name,fn,options)=>{const list=listeners.get(name)||[];list.push({fn,once:!!options?.once});listeners.set(name,list);};
  target.removeEventListener=(name,fn)=>listeners.set(name,(listeners.get(name)||[]).filter(item=>item.fn!==fn));
  target.emit=(name,event={})=>{for(const item of [...listeners.get(name)||[]]){if(item.once)target.removeEventListener(name,item.fn);item.fn(event);}};
  return target;
}
function setup({focused=true}={}) {
  const sent=[],ports=[],copied=[],feedback=[];let core,actions;let focus=focused;
  const current={id:'123',url:'https://x.com/signal/status/123',author:'@signal',text:'当前原帖正文，不是评论或引用内容。'};
  const document=events({visibilityState:'visible',hasFocus:()=>focus,documentElement:{}});
  const context=events({document,location:{href:current.url},navigator:{clipboard:{writeText:async text=>copied.push(text)}},URL,console,crypto:require('node:crypto').webcrypto,
    setTimeout:()=>1,clearTimeout:()=>{},setInterval:()=>2,clearInterval:()=>{},MutationObserver:class{observe(){}disconnect(){}},
    Suishou:{post:{...postTools,extractCurrentPost:()=>({post:{...current},reason:''})},DraftController:class extends DraftController{constructor(...args){super(...args);core=this;}},createPanel:callbacks=>{actions=callbacks;return {render:()=>{},show:()=>{},destroy:()=>{},feedback:text=>feedback.push(text)};}},
    chrome:{runtime:{connect(){const messages=[],disconnects=[];const port={postMessage:m=>sent.push(m),onMessage:{addListener:fn=>messages.push(fn)},onDisconnect:{addListener:fn=>disconnects.push(fn)},disconnect(){port.closed=true;for(const fn of disconnects)fn();},receive(message){for(const fn of messages)fn(message);}};ports.push(port);return port;}}},
  });
  context.window=context;context.top=context;vm.runInNewContext(source,context);
  return {context,document,current,sent,ports,copied,feedback,get core(){return core;},get actions(){return actions;},setFocused:value=>{focus=value;}};
}
test('a visible but unfocused window never starts automatic generation',()=>{const run=setup({focused:false});run.ports[0].receive({type:'settings',auto:true});assert.equal(run.sent.filter(m=>m.type==='generate').length,0);run.setFocused(true);run.context.emit('focus');assert.equal(run.sent.filter(m=>m.type==='generate').length,1);});
test('window blur cancels request and focusing does not automatically retry it',()=>{const run=setup();run.ports[0].receive({type:'settings',auto:true});run.setFocused(false);run.context.emit('blur');assert.ok(run.sent.some(m=>m.type==='cancel'));run.setFocused(true);run.context.emit('focus');assert.equal(run.sent.filter(m=>m.type==='generate').length,1);});
test('back-forward cache restoration reconnects while preserving edited draft',()=>{const run=setup();run.core.editDraft('在浏览器返回后保留');run.context.emit('pagehide',{persisted:true});assert.equal(run.ports[0].closed,true);run.context.emit('pageshow',{persisted:true});assert.equal(run.ports.length,2);assert.equal(run.core.state.draft,'在浏览器返回后保留');assert.equal(run.core.state.connected,true);assert.equal(run.sent.filter(m=>m.type==='generate').length,0);});
test('full page exit disconnects and stops all generation',()=>{const run=setup();run.ports[0].receive({type:'settings',auto:true});run.context.emit('pagehide',{persisted:false});assert.equal(run.ports[0].closed,true);const count=run.sent.length;run.core.generate(true);assert.equal(run.sent.length,count);});
test('copy includes edited draft but rejects an overlong draft without clipping',async()=>{const run=setup();run.core.editDraft('已编辑的简短回复');await run.actions.onManualFill();assert.deepEqual(run.copied,['已编辑的简短回复']);assert.match(run.feedback.at(-1),/Ctrl\+V/);const long='中'.repeat(141);run.core.editDraft(long);await run.actions.onCopy();assert.equal(run.copied.length,1);assert.equal(run.core.state.draft,long);assert.match(run.feedback.at(-1),/280/);});
test('after idle service worker disconnect, explicit Generate reconnects exactly once',()=>{const run=setup();run.ports[0].disconnect();assert.equal(run.core.state.connected,false);run.actions.onGenerate();assert.equal(run.ports.length,2);assert.equal(run.sent.filter(m=>m.type==='generate').length,1);run.ports[1].receive({type:'settings',auto:false});assert.equal(run.sent.filter(m=>m.type==='generate').length,1);});
test('disconnected content reconnects once on user navigation to a different detail post',()=>{const run=setup();run.ports[0].receive({type:'settings',auto:true});run.ports[0].disconnect();run.context.emit('focus');assert.equal(run.ports.length,1);Object.assign(run.current,{id:'456',url:'https://x.com/signal/status/456',text:'这是另一条主动打开的帖子。'});run.context.location.href=run.current.url;run.context.emit('popstate');assert.equal(run.ports.length,2);assert.equal(run.sent.filter(m=>m.type==='generate').length,1);run.ports[1].receive({type:'settings',auto:true});assert.equal(run.sent.filter(m=>m.type==='generate').length,2);assert.equal(run.sent.filter(m=>m.type==='generate')[1].post.id,'456');run.context.emit('popstate');assert.equal(run.ports.length,2);});
test('manual regeneration reconnects without auto racing and replacing explicit style',()=>{const run=setup();run.ports[0].receive({type:'settings',auto:true});run.core.setStyle('幽默');run.core.editDraft('用户编辑的幽默草稿');run.ports[0].disconnect();run.actions.onRegenerate();assert.equal(run.ports.length,2);const req=run.sent.filter(m=>m.type==='generate').at(-1);assert.equal(req.force,true);assert.equal(req.style,'幽默');assert.equal(req.previous,'用户编辑的幽默草稿');run.ports[1].receive({type:'settings',auto:true});assert.equal(run.sent.filter(m=>m.type==='generate').length,2);});
test('reconnection waits for authoritative off preference instead of using stale automatic state',()=>{const run=setup();run.ports[0].receive({type:'settings',auto:true});run.ports[0].disconnect();Object.assign(run.current,{id:'456',url:'https://x.com/signal/status/456',text:'另一条帖子'});run.context.location.href=run.current.url;run.context.emit('popstate');assert.equal(run.sent.filter(m=>m.type==='generate').length,1);run.ports[1].receive({type:'settings',auto:false});assert.equal(run.sent.filter(m=>m.type==='generate').length,1);assert.equal(run.core.state.auto,false);});
test('a pending explicit off choice cannot be reversed by stale initial settings',()=>{const run=setup();run.actions.onAuto(false);run.ports[0].receive({type:'settings',auto:true});assert.equal(run.sent.filter(m=>m.type==='generate').length,0);assert.equal(run.core.state.auto,false);run.ports[0].receive({type:'settings',auto:false});assert.equal(run.core.state.auto,false);});
test('preference storage failure is visible and leaves this page automatic mode off',()=>{const run=setup();run.actions.onAuto(true);run.ports[0].receive({type:'error',id:'settings',code:'storage',message:'无法保存开关状态，请重试。'});assert.equal(run.core.state.auto,false);assert.match(run.feedback.at(-1),/保存/);assert.equal(run.sent.filter(m=>m.type==='generate').length,0);});
