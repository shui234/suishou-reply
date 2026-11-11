'use strict';
importScripts('post.js','worker.js');
const bridge=new Suishou.BridgeWorker({
  extensionId:chrome.runtime.id,crypto,
  local:chrome.storage.local,session:chrome.storage.session,
  getTab:id=>chrome.tabs.get(id),
  getWindow:id=>chrome.windows.get(id),
  connectNative:name=>{const p=chrome.runtime.connectNative(name);p.onDisconnect.addListener(()=>{void chrome.runtime.lastError});return p;},
  setTimeout:(fn,ms)=>setTimeout(fn,ms),clearTimeout:timer=>clearTimeout(timer)
});
// Keep page scripts from directly reading storage; content scripts use validated ports.
chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'}).catch(()=>{});
chrome.storage.session.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'}).catch(()=>{});
chrome.runtime.onConnect.addListener(port=>bridge.attach(port));
chrome.tabs.onUpdated.addListener((id,change)=>{if(change.url)bridge.navigationChanged(id,change.url)});
chrome.tabs.onActivated.addListener(info=>bridge.activated(info.tabId));
chrome.tabs.onRemoved.addListener(id=>bridge.removed(id));
chrome.windows.onFocusChanged.addListener(id=>bridge.focused(id));
chrome.runtime.onSuspend.addListener(()=>bridge.suspend());
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&changes.autoGenerate)bridge.settingsChanged(changes.autoGenerate.newValue)});
