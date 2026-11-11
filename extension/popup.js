'use strict';
const status=document.getElementById('status');
const preferences=[
  {key:'autoGenerate',toggle:document.getElementById('auto'),on:'已开启，仅在前台帖子详情页生成。',off:'已关闭自动生成。'},
  {key:'autoCopy',toggle:document.getElementById('auto-copy'),on:'已开启生成后自动复制，会替换当前剪贴板内容。',off:'已关闭生成后自动复制。'},
];
for(const preference of preferences){
  const {key,toggle}=preference;
  toggle.disabled=true;
  toggle.addEventListener('change',async()=>{
    const enabled=toggle.checked;
    toggle.disabled=true;
    try{await chrome.storage.local.set({[key]:enabled});status.textContent=enabled?preference.on:preference.off;}
    catch{toggle.checked=!enabled;status.textContent='保存失败，请重试。';}
    finally{toggle.disabled=false;}
  });
}
chrome.storage.local.get(preferences.map(preference=>preference.key)).then(values=>{
  for(const {key,toggle} of preferences){toggle.checked=values[key]===true;toggle.disabled=false;}
}).catch(()=>{status.textContent='无法读取开关状态，请重新打开此面板。'});
