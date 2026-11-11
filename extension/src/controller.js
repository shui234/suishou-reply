/* Per-page draft state. No browser or DOM dependency, so races can be tested directly. */
(function (root) {
  'use strict';
  const styles = ['自然','犀利','幽默'];
  const boundedSet = (map,key,value,limit=60) => {
    map.delete(key); map.set(key,value);
    while (map.size > limit) map.delete(map.keys().next().value);
  };
  const identity = post => post ? `${post.url}\n${post.text}` : '';

  class DraftController {
    constructor({send,onChange=()=>{},newId=()=>crypto.randomUUID()}) {
      this.send = send; this.onChange = onChange; this.newId = newId;
      this.post = null; this.style = '自然'; this.auto = false; this.autoCopy = false; this.visible = true;
      this.connected = true; this.disposed = false; this.reason = '';
      this.entries = new Map(); this.attempted = new Map(); this.lastStyles = new Map();
      this.dirtyDrafts = new Map(); this.dirtyStyles = new Map(); this.active = null;
    }
    _key(style=this.style) { return this.post ? `${identity(this.post)}\n${style}` : ''; }
    _entry() {
      const key = this._key();
      if (!key) return {draft:'',dirty:false,error:'',usage:{},revision:0,cached:false,status:''};
      if (!this.entries.has(key)) boundedSet(this.entries,key,{draft:'',dirty:false,error:'',usage:{},revision:0,cached:false,status:''});
      return this.entries.get(key);
    }
    get state() {
      const entry = this._entry();
      return {post:this.post ? {...this.post} : null,style:this.style,auto:this.auto,autoCopy:this.autoCopy,visible:this.visible,
        connected:this.connected,loading:!!this.active,reason:this.reason,...entry};
    }
    _emit() { if (!this.disposed) this.onChange(this.state); }
    _rememberDirty() {
      const entry=this._entry();
      if(!this.post || !entry.dirty)return;
      boundedSet(this.dirtyDrafts,`${this.post.url}\n${this.style}`,{text:this.post.text,entry:{...entry}});
      boundedSet(this.dirtyStyles,this.post.url,this.style);
    }
    _cancel(status='') {
      const active = this.active; this.active = null;
      if (active) {
        try { this.send({type:'cancel',id:active.id}); } catch {}
        const entry = this.entries.get(active.key); if (entry && status) entry.status = status;
      }
    }
    setPost(post,reason='',allowAutomatic=true) {
      if (this.disposed) return;
      if (identity(post) === identity(this.post)) { this.reason = reason; this._emit(); return; }
      const oldPost = this.post, oldStyle = this.style;
      if (oldPost) boundedSet(this.lastStyles,identity(oldPost),oldStyle);
      this._rememberDirty();
      this._cancel(); this.post = post ? {id:post.id,url:post.url,author:post.author,text:post.text} : null;
      this.reason = reason;
      const rememberedStyle = this.lastStyles.get(identity(this.post));
      const rememberedEntry = rememberedStyle ? this.entries.get(this._key(rememberedStyle)) : null;
      const stableStyle=post ? this.dirtyStyles.get(post.url) : null;
      const stableDraft=stableStyle ? this.dirtyDrafts.get(`${post.url}\n${stableStyle}`) : null;
      if (rememberedEntry?.dirty) this.style = rememberedStyle;
      else if (stableDraft) {
        this.style=stableStyle;
        const restored={...stableDraft.entry};
        if(stableDraft.text!==post.text){restored.status='原帖正文有变化，已保留手工草稿；使用前请重新核对。';restored.error='';restored.retry=null;restored.cached=false;}
        boundedSet(this.entries,this._key(),restored);
      }
      else if (this.auto) this.style = '自然';
      this._emit(); if(allowAutomatic)this._maybeAuto();
    }
    setVisible(value,allowAutomatic=true) {
      if (this.disposed || this.visible === !!value) return;
      this.visible = !!value;
      if (!this.visible) this._cancel('已暂停等待；再次生成需主动点击。');
      this._emit(); if (this.visible && allowAutomatic) this._maybeAuto();
    }
    setAuto(value) {
      if (this.disposed) return;
      this.auto = !!value;
      if (!this.auto && this.active?.automatic) this._cancel('自动生成已关闭。');
      this._emit(); if (this.auto) this._maybeAuto();
    }
    setStyle(style) {
      if (this.disposed || !styles.includes(style) || style === this.style) return;
      this._cancel(); this.style = style;
      if(this.post)boundedSet(this.lastStyles,identity(this.post),style);
      this._emit();
    }
    setAutoCopy(value) {
      if (this.disposed) return;
      this.autoCopy = value === true;
      this._emit();
    }
    _maybeAuto() {
      if (this.disposed || !this.auto || !this.post || !this.visible || !this.connected || this.active) return;
      if (this._entry().dirty) return;
      const naturalKey = this._key('自然');
      if (this.attempted.has(naturalKey)) return;
      this.style = '自然';
      if (this._entry().draft || this._entry().dirty) { this._emit(); return; }
      boundedSet(this.attempted,naturalKey,true,100);
      this._request(false,true);
    }
    generate(force=false) {
      if (this.disposed || !this.post || !this.visible || this.active) return;
      if (!this.connected) { this._entry().error = '扩展连接已断开，请刷新此页后重试。'; this._emit(); return; }
      const entry = this._entry();
      if(!force && entry.retry) {
        this._request(entry.retry.force,false,entry.retry.previous);return;
      }
      if (!force && (entry.dirty || entry.draft)) { entry.status = '已保留现有草稿；需要替换时请点“重新生成”。'; this._emit(); return; }
      this._request(!!force,false);
    }
    _request(force,automatic,previousOverride) {
      const entry = this._entry(), key = this._key(), id = this.newId();
      const previous=typeof previousOverride==='string' ? previousOverride : force ? entry.draft.slice(0,500) : '';
      entry.error = ''; entry.status = automatic ? '正在自动生成自然回复…' : '正在生成回复…';
      entry.retry=null;
      this.active = {id,key,automatic,revision:entry.revision,force,previous};
      boundedSet(this.attempted,key,true,100);
      this._emit();
      try {
        this.send({type:'generate',id,post:{...this.post},style:this.style,force,
          previous});
      } catch { this.disconnect(); }
    }
    editDraft(text) {
      if (this.disposed || !this.post) return;
      this._cancel(); const entry = this._entry();
      entry.draft = String(text).slice(0,500); entry.dirty = true; entry.revision++;
      entry.error = ''; entry.retry=null; entry.cached = false; entry.status = '已编辑，自动生成不会覆盖这份草稿。';
      this._rememberDirty();this._emit();
    }
    handle(message) {
      if (this.disposed || !message || typeof message !== 'object') return;
      if (message.type === 'settings') { this.setAutoCopy(message.autoCopy); this.setAuto(message.auto); return; }
      const active = this.active;
      if (!active || message.id !== active.id || active.key !== this._key()) return;
      if (!['result','error','cancelled'].includes(message.type)) return;
      this.active = null;
      const entry = this._entry();
      if (entry.revision !== active.revision) return;
      let accepted = false;
      if (message.type === 'result' && typeof message.text === 'string' && message.text.trim() && message.text.length <= 500) {
        accepted = true;
        entry.draft = message.text; entry.dirty = false; entry.error = '';
        entry.usage = message.usage && typeof message.usage === 'object' ? {...message.usage} : {};
        entry.cached = !!message.cached; entry.status = message.cached ? '已复用本次会话草稿，请审阅后使用。' : '已生成，请审阅后使用。';
        this.dirtyDrafts.delete(`${this.post.url}\n${this.style}`);
        if(this.dirtyStyles.get(this.post.url)===this.style)this.dirtyStyles.delete(this.post.url);
      } else if (message.type === 'cancelled') entry.status = '请求已取消；需要时请主动重试。';
      else {
        entry.error = message.type === 'error' && typeof message.message === 'string' ? message.message.slice(0,300) : '返回的回复格式异常，请重试。';
        entry.retry={force:active.force,previous:active.previous};
      }
      this._emit();
      // Only a newly accepted response may produce clipboard side effects.
      // Rerenders, restored drafts, errors and replayed messages return nothing/false.
      return accepted;
    }
    disconnect() {
      if (this.disposed) return;
      if(this.active){const entry=this.entries.get(this.active.key);if(entry)entry.retry={force:this.active.force,previous:this.active.previous};}
      this.active = null; this.connected = false;
      this._entry().error = '本地连接已断开；请检查安装，刷新此页后重试。'; this._emit();
    }
    reconnect() {
      // Explicit action/new detail navigation or BFCache restore; never a retry timer.
      if(this.disposed)return;
      this.connected=true;this._entry().error='';this._emit();
    }
    dispose() { if (this.disposed) return; this._cancel(); this.disposed = true; this.entries.clear(); this.attempted.clear(); this.lastStyles.clear(); this.dirtyDrafts.clear();this.dirtyStyles.clear(); }
  }
  root.Suishou = root.Suishou || {}; root.Suishou.DraftController = DraftController;
  if (typeof module !== 'undefined' && module.exports) module.exports = {DraftController};
})(globalThis);
