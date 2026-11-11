const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync(require.resolve('../popup.js'),'utf8');
function setup(seed={},failWrite=false){
 const fields=Object.fromEntries(['auto','auto-copy','status'].map(id=>[id,{checked:false,disabled:false,textContent:'',listeners:{},addEventListener(type,fn){this.listeners[type]=fn}}]));
 const data={...seed},writes=[];
 vm.runInNewContext(code,{document:{getElementById:id=>fields[id]},chrome:{storage:{local:{async get(){return {...data}},async set(value){writes.push(value);if(failWrite)throw Error('storage unavailable');Object.assign(data,value)}}}}});
 return {fields,data,writes,flush:()=>new Promise(resolve=>setImmediate(resolve))};
}
test('popup initializes both opt-in controls off without writes',async()=>{
 const h=setup();assert.equal(h.fields.auto.disabled,true);assert.equal(h.fields['auto-copy'].disabled,true);await h.flush();assert.equal(h.fields.auto.checked,false);assert.equal(h.fields['auto-copy'].checked,false);assert.equal(h.fields['auto-copy'].disabled,false);assert.equal(h.writes.length,0);
});
test('popup restores and changes copy setting independently',async()=>{
 const h=setup({autoGenerate:true,autoCopy:true});await h.flush();assert.equal(h.fields['auto-copy'].checked,true);h.fields['auto-copy'].checked=false;await h.fields['auto-copy'].listeners.change();assert.equal(h.data.autoCopy,false);assert.equal(h.data.autoGenerate,true);assert.equal(h.fields.auto.checked,true);assert.match(h.fields.status.textContent,/关闭.*复制/);
});
test('popup rolls back rejected copy writes and permits retry',async()=>{
 const h=setup({},true);await h.flush();h.fields['auto-copy'].checked=true;await h.fields['auto-copy'].listeners.change();assert.equal(h.fields['auto-copy'].checked,false);assert.equal(h.fields['auto-copy'].disabled,false);assert.match(h.fields.status.textContent,/保存失败/);assert.equal(h.data.autoCopy,undefined);
});
test('popup automatic generation control keeps copy preference unchanged',async()=>{
 const h=setup({autoCopy:true});await h.flush();h.fields.auto.checked=true;await h.fields.auto.listeners.change();assert.equal(h.data.autoGenerate,true);assert.equal(h.data.autoCopy,true);assert.match(h.fields.status.textContent,/前台/);
});
