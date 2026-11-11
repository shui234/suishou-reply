/* Native transport and session-only cache. No X/DeepSeek HTTP requests here. */
(function (root) {
  'use strict';
  const HOST = 'com.suishou.reply';
  const weightedLength = root.Suishou?.post?.weightedLength || (typeof require==='function' ? require('./post.js').weightedLength : null);
  const BAD_TEXT = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ud800-\udfff]/u;
  const STYLES = new Set(['自然', '犀利', '幽默']);
  const ownObject = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  function keys(value, allowed, required=allowed) {
    return ownObject(value) && Object.keys(value).every(k=>allowed.includes(k)) && required.every(k=>Object.hasOwn(value,k));
  }
  function text(value, max) {return typeof value==='string' && value.length<=max && !BAD_TEXT.test(value);}
  function xUrl(value) {
    try {const u=new URL(value);return u.protocol==='https:' && ['x.com','twitter.com'].includes(u.hostname) && !u.port && !u.username && !u.password ? u : null;} catch {return null;}
  }
  function postUrl(value) {
    const u=xUrl(value);if(!u)return null;
    const m=u.pathname.match(/^\/([A-Za-z0-9_]{1,15})\/status\/([0-9]{1,25})\/?$/);
    return m ? {id:m[2],author:'@'+m[1],url:`https://x.com/${m[1]}/status/${m[2]}`} : null;
  }
  function trustedSender(sender, extensionId) {
    return !!(sender && sender.id===extensionId && sender.frameId===0 && sender.tab && Number.isInteger(sender.tab.id) && sender.tab.id>=0 && xUrl(sender.url));
  }
  function validId(id) {return typeof id==='string' && /^[A-Za-z0-9_-]{1,80}$/.test(id);}
  function validateGenerate(m) {
    if(!keys(m,['type','id','post','style','force','previous']) || m.type!=='generate' || !validId(m.id) || !STYLES.has(m.style) || typeof m.force!=='boolean' || !text(m.previous,500))throw Error('请求格式无效。');
    const p=m.post;
    if(!keys(p,['id','url','author','text']) || !text(p.text,3000) || !p.text.trim())throw Error('原帖正文为空、过长或含不支持的字符。');
    const parsed=postUrl(p.url);
    if(!parsed || parsed.url!==p.url || parsed.id!==p.id || typeof p.author!=='string' || parsed.author.toLowerCase()!==p.author.toLowerCase())throw Error('无法确认当前原帖，请重新打开帖子详情页。');
    if(new TextEncoder().encode(JSON.stringify(m)).length>30000)throw Error('请求过大。');
    return {id:m.id,post:{id:p.id,url:parsed.url,author:parsed.author,text:p.text.trim()},style:m.style,force:m.force,previous:m.previous};
  }
  function safeResult(value) {
    if(!text(value,500) || !value.trim())return false;
    return weightedLength(value)<=280;
  }
  function usage(value) {
    const out={};if(!ownObject(value))return out;
    for(const key of ['prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens'])if(typeof value[key]==='number' && Number.isFinite(value[key]) && value[key]>=0 && value[key]<=2**53)out[key]=value[key];
    return out;
  }
  class BridgeWorker {
    constructor(deps) {
      this.d=deps;this.ports=new Map();this.cache=new Map();this.native=null;this.active=null;this.auto=false;this.dead=false;this.persist=Promise.resolve();this.preferenceWrites=Promise.resolve();this.preferenceRevision=0;
      this.ready=Promise.all([deps.local.get('autoGenerate'),deps.session.get('replyCache')]).then(([settings,session])=>{
        this.auto=settings.autoGenerate===true;
        for(const pair of Array.isArray(session.replyCache)?session.replyCache.slice(-64):[])if(Array.isArray(pair)&&/^[a-f0-9]{64}$/.test(pair[0])&&ownObject(pair[1])&&safeResult(pair[1].text))this.cache.set(pair[0],{text:pair[1].text,usage:usage(pair[1].usage)});
      }).catch(()=>{});
    }
    send(port,value) {if(!this.ports.has(port))return;try{port.postMessage(value)}catch{this.detach(port)}}
    error(port,id,message,code='invalid') {this.send(port,{type:'error',id:validId(id)?id:'request',code,message});}
    attach(port) {
      if(this.dead || port.name!=='suishou-page' || !trustedSender(port.sender,this.d.extensionId)){try{port.disconnect()}catch{};return false;}
      this.ports.set(port,{revision:0,tabId:port.sender.tab.id,windowId:port.sender.tab.windowId});
      port.onMessage.addListener(m=>{this.handle(port,m).catch(()=>this.error(port,m?.id,'本机连接未能完成，请重试。','connection'));});
      port.onDisconnect.addListener(()=>this.detach(port));
      this.ready.then(()=>this.send(port,{type:'settings',auto:this.auto}));return true;
    }
    async context(port,p) {
      const s=this.ports.get(port);if(!s)return false;
      try{const tab=await this.d.getTab(s.tabId);const window=await this.d.getWindow(tab?.windowId);const current=postUrl(tab?.url);return !!(tab?.active && window?.focused && current && current.id===p.id && current.author.toLowerCase()===p.author.toLowerCase());}catch{return false;}
    }
    async settingsChanged(enabled) {
      const revision=++this.preferenceRevision;
      await this.ready;
      if(revision!==this.preferenceRevision)return;
      this.auto=enabled===true;
      for(const p of this.ports.keys())this.send(p,{type:'settings',auto:this.auto});
    }
    async handle(port,m) {
      if(!this.ports.has(port)||!ownObject(m))return;
      if(m.type==='set-auto') {
        if(!keys(m,['type','enabled'])||typeof m.enabled!=='boolean')return;
        this.preferenceWrites=this.preferenceWrites.then(async()=>{
          await this.ready;
          try{await this.d.local.set({autoGenerate:m.enabled});const latest=await this.d.local.get('autoGenerate');await this.settingsChanged(latest.autoGenerate);}
          catch{this.error(port,'settings','无法保存开关状态，请重试。','storage');}
        });
        await this.preferenceWrites;
        return;
      }
      if(m.type==='cancel') {
        if(!keys(m,['type','id'])||!validId(m.id))return;
        this.ports.get(port).revision++;
        if(this.active?.port===port && this.active.id===m.id)this.cancelActive();
        return;
      }
      let req;try{req=validateGenerate(m)}catch(e){this.error(port,m.id,e.message);return;}
      const state=this.ports.get(port), revision=++state.revision;
      const alive=()=>!this.dead && this.ports.get(port)===state && state.revision===revision;
      await this.ready;if(!alive())return;
      if(!await this.context(port,req.post)){if(alive())this.error(port,req.id,'请在前台打开对应的 X 帖子详情页再生成。','context');return;}
      if(!alive())return;
      const material=JSON.stringify([req.post.url.toLowerCase(),req.post.text,req.style]);
      const hash=await this.d.crypto.subtle.digest('SHA-256',new TextEncoder().encode(material));
      const key=Array.from(new Uint8Array(hash),n=>n.toString(16).padStart(2,'0')).join('');
      if(!alive())return;
      if(this.active?.port===port && this.active.key===key){this.error(port,req.id,'正在生成，请稍候或先取消。','busy');return;}
      this.cancelActive();
      if(!req.force && this.cache.has(key)) {
        const cached=this.cache.get(key);this.cache.delete(key);this.cache.set(key,cached);
        this.send(port,{type:'result',id:req.id,...cached,cached:true});return;
      }
      const nativeId=this.d.crypto.randomUUID();
      const active={port,id:req.id,key,nativeId,post:req.post,timer:null};this.active=active;
      try {
        const native=this.ensureNative();
        active.timer=this.d.setTimeout(()=>{if(this.active===active){this.cancelActive(false);this.error(port,req.id,'本机请求超时，请检查连接后手动重试。','timeout');}},this.d.timeoutMs||40000);
        native.postMessage({v:1,type:'generate',id:nativeId,post:req.post,style:req.style,previous:req.force?req.previous:''});
      }catch{if(this.active===active)this.cancelActive(false);this.dropNative();this.error(port,req.id,'未连接随手回本机组件。请先运行安装包中的 Install.cmd，再手动重试。','host');}
    }
    ensureNative() {
      if(this.native)return this.native;
      const port=this.d.connectNative(HOST);this.native=port;
      port.onMessage.addListener(m=>{this.nativeMessage(port,m).catch(()=>{const a=this.active;if(a){this.cancelActive(false);this.error(a.port,a.id,'本机响应无效，请重试。','protocol');}})});
      port.onDisconnect.addListener(()=>{
        if(this.native!==port)return;this.native=null;
        const a=this.active;if(a){this.clearActive();this.error(a.port,a.id,'本机连接已断开。请检查组件安装后手动重试。','host');}
      });return port;
    }
    async nativeMessage(native,m) {
      const a=this.active;if(native!==this.native || !a || !ownObject(m) || m.id!==a.nativeId)return;
      if(m.v!==1){this.cancelActive(false);this.error(a.port,a.id,'本机协议版本不兼容，请更新本机组件。','protocol');return;}
      if(m.type==='result') {
        if(!safeResult(m.text)){this.cancelActive(false);this.error(a.port,a.id,'回复为空、超长或格式异常，请重新生成。','output');return;}
        const valid=await this.context(a.port,a.post);
        if(this.active!==a)return;
        this.clearActive();if(!valid){this.error(a.port,a.id,'当前帖子已改变，本次回复已丢弃。','context');return;}
        const value={text:m.text.trim(),usage:usage(m.usage)};
        this.cache.delete(a.key);this.cache.set(a.key,value);while(this.cache.size>64)this.cache.delete(this.cache.keys().next().value);
        this.persist=this.persist.then(()=>this.d.session.set({replyCache:Array.from(this.cache)})).catch(()=>{});
        this.send(a.port,{type:'result',id:a.id,...value,cached:false});
      }else if(m.type==='error'){
        this.clearActive();this.error(a.port,a.id,text(m.message,240)&&m.message?m.message:'本机请求失败，请重试。',typeof m.code==='string'&&/^[a-z_]{1,32}$/.test(m.code)?m.code:'api');
      }else if(m.type==='cancelled'){this.clearActive();this.send(a.port,{type:'cancelled',id:a.id});}
      else{this.cancelActive(false);this.error(a.port,a.id,'本机响应格式不兼容，请更新本机组件。','protocol');}
    }
    clearActive() {const a=this.active;this.active=null;if(a?.timer)this.d.clearTimeout(a.timer);return a;}
    cancelActive(notify=true) {
      const a=this.clearActive();if(!a)return;
      try{this.native?.postMessage({v:1,type:'cancel',id:a.nativeId})}catch{}
      if(notify)this.send(a.port,{type:'cancelled',id:a.id});
    }
    navigationChanged(tabId,url) {
      for(const s of this.ports.values())if(s.tabId===tabId)s.revision++;
      if(this.active && this.ports.get(this.active.port)?.tabId===tabId){const target=postUrl(url);if(!target || target.id!==this.active.post.id || target.author.toLowerCase()!==this.active.post.author.toLowerCase())this.cancelActive();}
    }
    activated(tabId) {
      for(const s of this.ports.values())if(s.tabId!==tabId)s.revision++;
      if(this.active && this.ports.get(this.active.port)?.tabId!==tabId)this.cancelActive();
    }
    focused(windowId) {
      for(const s of this.ports.values())if(s.windowId!==windowId)s.revision++;
      if(this.active && this.ports.get(this.active.port)?.windowId!==windowId)this.cancelActive();
    }
    detach(port) {
      if(this.active?.port===port)this.cancelActive(false);
      this.ports.delete(port);if(!this.ports.size)this.dropNative();
    }
    removed(tabId) {for(const [p,s] of this.ports)if(s.tabId===tabId)this.detach(p);}
    dropNative() {const n=this.native;this.native=null;try{n?.disconnect()}catch{}}
    suspend() {
      // Chrome may cancel suspension when a new event arrives. Remain usable then.
      for(const s of this.ports.values())s.revision++;
      this.cancelActive();this.dropNative();
    }
    dispose() {this.dead=true;this.cancelActive(false);this.ports.clear();this.dropNative();}
  }
  root.Suishou=root.Suishou||{};Object.assign(root.Suishou,{BridgeWorker,validateGenerate,trustedSender});
  if(typeof module!=='undefined'&&module.exports)module.exports={BridgeWorker,validateGenerate,trustedSender};
})(globalThis);
