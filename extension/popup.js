'use strict';
const toggle=document.getElementById('auto'),status=document.getElementById('status');
toggle.disabled=true;
chrome.storage.local.get('autoGenerate').then(v=>{toggle.checked=v.autoGenerate===true;toggle.disabled=false}).catch(()=>{status.textContent='无法读取开关状态，请重新打开此面板。'});
toggle.addEventListener('change',async()=>{toggle.disabled=true;try{await chrome.storage.local.set({autoGenerate:toggle.checked});status.textContent=toggle.checked?'已开启，仅在前台帖子详情页生成。':'已关闭自动生成。'}catch{toggle.checked=!toggle.checked;status.textContent='保存失败，请重试。'}finally{toggle.disabled=false}});
