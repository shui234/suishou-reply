/* Isolated-world entry point. Only our own panel is mutated; X is read-only. */
(function () {
  'use strict';
  if (globalThis.__suishouInstalled || !globalThis.Suishou || window.top !== window) return;
  globalThis.__suishouInstalled = true;
  const {post:postTools,DraftController,createPanel}=globalThis.Suishou;
  let port=null,core=null,manual=null,disposed=false,suspended=false,timer=null,interval=null;
  let portRoute=null,disconnectedRoute=null,settingsReady=false,pendingAuto=null;
  const foreground=()=>document.visibilityState==='visible' && document.hasFocus();
  const panel=createPanel({
    onAuto:enabled=>{pendingAuto=enabled;if(!enabled)core.setAuto(false);if(!ensureConnection())return;try{port.postMessage({type:'set-auto',enabled});}catch{core.disconnect();}},
    onStyle:style=>core.setStyle(style),
    onGenerate:()=>{if(!ensureConnection())return;scan(false);core.generate();},
    onRegenerate:()=>{if(!ensureConnection())return;scan(false);core.generate(true);},
    onEdit:text=>core.editDraft(text),
    onCopy:()=>copyDraft(false),
    onManualFill:()=>copyDraft(true),
    onManualSource:text=>{
      const route=postTools.parsePostUrl(location.href);
      const selected=route&&postTools.selectCandidate([{...route,text,ownTextCount:1}],location.href);
      if(!selected?.post){panel.feedback('请先打开帖子详情页，并提供 1～3000 字的有效原文。');return;}
      manual={url:route.url,post:selected.post};core.setPost(selected.post,'使用你手动提供的原文。');
      panel.feedback('已使用你提供的原文，请确认与当前帖子一致。');
    },
  });
  core=new DraftController({send:message=>{if(!port)throw new Error('Disconnected');port.postMessage(message);},onChange:state=>panel.render(state)});
  core.setVisible(foreground());
  function connectPort() {
    settingsReady=false;
    try {
      const connection=chrome.runtime.connect({name:'suishou-page'});port=connection;
      portRoute=postTools.parsePostUrl(location.href)?.url || null;
      connection.onMessage.addListener(message=>{
        if(connection!==port)return;
        if(message.type==='error' && message.id==='settings') {
          pendingAuto=false;settingsReady=false;core.setAuto(false);
          panel.feedback('开关状态未能保存，本页自动生成已暂停；请重新操作开关。');return;
        }
        if(message.type==='settings') {
          scan(false);
          if(typeof message.auto!=='boolean' || pendingAuto!==null && message.auto!==pendingAuto)return;
          pendingAuto=null;settingsReady=true;
        } else scan();
        core.handle(message);
      });
      connection.onDisconnect.addListener(()=>{
        void chrome.runtime.lastError;if(connection!==port)return;
        disconnectedRoute=portRoute;settingsReady=false;port=null;core.disconnect();
      });
      core.reconnect();return true;
    } catch {port=null;disconnectedRoute=postTools.parsePostUrl(location.href)?.url || null;core.disconnect();return false;}
  }
  function ensureConnection(){return !!port || connectPort();}
  connectPort();

  function scan(allowAutomatic=true) {
    if(disposed||suspended)return;
    const route=postTools.parsePostUrl(location.href);
    panel.show(!!route);
    if(!route){manual=null;core.setPost(null);return;}
    if(manual && manual.url!==route.url)manual=null;
    if(!foreground()){core.setVisible(false);return;}
    // A new foreground detail navigation is an explicit opportunity to reconnect;
    // rerenders of a disconnected current post never cause a retry loop.
    if(!port && route.url!==disconnectedRoute)connectPort();
    if(port)portRoute=route.url;
    // Reconcile identity before unpausing: never generate the previous page after tab activation.
    const found=manual?.url===route.url?{post:manual.post,reason:'使用你手动提供的原文。'}:postTools.extractCurrentPost(document,location.href);
    const mayAuto=allowAutomatic!==false && settingsReady;
    core.setPost(found.post,found.reason,mayAuto);
    core.setVisible(true,mayAuto);
  }
  function schedule() {
    if(disposed||suspended||timer!==null)return;
    timer=setTimeout(()=>{timer=null;scan();},160);
  }
  async function copyDraft(manualFill) {
    scan();const draft=core.state.draft;
    if(!core.state.post || !draft.trim()){panel.feedback('请先确认当前帖子并生成或编辑草稿。');return;}
    const checked=postTools.validateDraft(draft);
    if(!checked.valid){panel.feedback(checked.message);return;}
    try {
      await navigator.clipboard.writeText(draft);
      panel.feedback(manualFill?'已复制。请自行点击当前帖的 X 回复框，按 Ctrl+V 粘贴，检查后再发送。':'草稿已复制，请核对后手动粘贴发布。');
    } catch {panel.feedback('浏览器未允许复制；请在上方草稿框中全选并手动复制。');}
  }
  const observer=new MutationObserver(schedule);
  // X uses same-document navigation. A low-frequency route check needs no history monkey patch.
  let lastUrl=location.href;
  function startWatching() {
    observer.observe(document.documentElement,{childList:true,subtree:true,characterData:true});
    interval=setInterval(()=>{if(location.href!==lastUrl){lastUrl=location.href;scan();}},500);
  }
  function stopWatching(){observer.disconnect();clearInterval(interval);interval=null;clearTimeout(timer);timer=null;}
  startWatching();
  function visibility(){if(!foreground())core.setVisible(false);else scan();}
  function blur(){core.setVisible(false);}
  document.addEventListener('visibilitychange',visibility);
  window.addEventListener('focus',visibility);window.addEventListener('blur',blur);
  window.addEventListener('popstate',scan);
  function closePort() {const connection=port;port=null;try{connection?.disconnect();}catch{}}
  function pagehide(event) {
    if(!event.persisted){dispose();return;}
    core.setVisible(false);suspended=true;stopWatching();closePort();core.disconnect();panel.show(false);
  }
  function pageshow(event) {
    if(!event.persisted || !suspended || disposed)return;
    suspended=false;connectPort();startWatching();scan();
  }
  function dispose() {
    if(disposed)return;disposed=true;stopWatching();
    document.removeEventListener('visibilitychange',visibility);window.removeEventListener('popstate',scan);
    window.removeEventListener('focus',visibility);window.removeEventListener('blur',blur);
    window.removeEventListener('pagehide',pagehide);window.removeEventListener('pageshow',pageshow);
    core.dispose();closePort();panel.destroy();
  }
  window.addEventListener('pagehide',pagehide);window.addEventListener('pageshow',pageshow);
  scan();
})();
