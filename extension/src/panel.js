/* All page/AI strings are textContent or textarea values, never markup. */
(function (root) {
  'use strict';
  function chooseDock(viewportWidth,mainRect,panelWidth=330) {
    if(!mainRect || !Number.isFinite(mainRect.left) || !Number.isFinite(mainRect.right)
        || !(mainRect.width>0))return {left:12,collapsed:true};
    if(viewportWidth-mainRect.right>=panelWidth+24)return {left:mainRect.right+12,collapsed:false};
    if(mainRect.left>=panelWidth+24)return {left:mainRect.left-panelWidth-12,collapsed:false};
    return {left:12,collapsed:true};
  }
  function createPanel(actions, document=root.document) {
    const host = document.createElement('div');
    host.id = 'suishou-reply-extension';
    host.setAttribute('data-suishou-version','1.2.0');
    host.style.cssText = 'all:initial;position:fixed;left:18px;bottom:20px;z-index:2147483646;display:block;max-width:calc(100vw - 24px);color-scheme:dark;';
    const shadow = host.attachShadow({mode:'closed'});
    const style = document.createElement('style');
    style.textContent = `
      :host{font-family:Inter,"Segoe UI","Microsoft YaHei UI",sans-serif;font-size:13px;color:#e8edf1;line-height:1.55}
      *,*::before,*::after{box-sizing:border-box}button,input,textarea,select{font:inherit}button{cursor:pointer}
      .shell{width:330px;max-width:calc(100vw - 28px);border:1px solid #34424b;border-radius:18px;background:#111a21;box-shadow:0 14px 48px #0007;overflow:hidden}
      .head{display:flex;align-items:center;gap:9px;padding:12px 14px;border-bottom:1px solid #26323a;cursor:move;touch-action:none;user-select:none}
      .mark{width:28px;height:28px;display:grid;place-items:center;background:#78dfbd;color:#08251b;border-radius:9px;font-weight:800;font-size:16px}
      .brand{font-size:14px;font-weight:650;letter-spacing:.04em;flex:1}.version{font-size:10px;color:#8a9ba8;margin-left:6px;font-weight:400;letter-spacing:0}
      button{border:1px solid #35434e;border-radius:9px;background:#202c36;color:#e8edf1;padding:7px 11px;line-height:1.35}button:hover:enabled{background:#2c3c47}button:focus-visible,textarea:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid #7ce3c2;outline-offset:2px}
      button:disabled{opacity:.42;cursor:default}.collapse{background:transparent;border:0;padding:4px 7px;color:#9aabb6;font-size:17px}
      .body{padding:13px 14px 14px;max-height:min(650px,calc(100dvh - 114px));overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:#40515e transparent}
      .toggle{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:600}.toggle input{width:15px;height:15px;accent-color:#70ddb8;margin:0}
      .hint{font-size:11px;color:#8d9fab;margin:7px 0 12px;line-height:1.6}.identity{display:flex;align-items:center;gap:6px;margin:8px 0 4px;min-height:20px}.author{font-weight:600;color:#b7c8d4}.link{color:#89d9c1;font-size:11px;text-decoration:none;margin-left:auto}.link:hover{text-decoration:underline}
      .source{font-size:12px;color:#9eb0bd;white-space:pre-wrap;overflow-wrap:anywhere;max-height:64px;overflow:auto;margin:0 0 12px;padding-left:9px;border-left:2px solid #38564f}
      .row{display:flex;align-items:center;gap:7px;margin:9px 0}.label{font-size:11px;color:#91a3b0;margin-right:2px}.styles{display:flex;gap:5px}.styles button{font-size:12px;padding:5px 10px;background:transparent}.styles button.selected{background:#24483e;border-color:#599b86;color:#bdf3df}
      .draft-label{font-size:11px;color:#8da49e;margin-top:13px;margin-bottom:6px;display:flex;justify-content:space-between}.dirty{color:#c8bd8d}
      textarea{display:block;resize:vertical;width:100%;min-height:106px;max-height:260px;border:1px solid #364750;border-radius:11px;background:#0c141a;color:#edf6f4;padding:11px 12px;line-height:1.75;overflow-wrap:anywhere;font-size:13px}textarea:disabled{opacity:.6}
      .state{min-height:34px;font-size:11px;color:#a5b6c1;margin:8px 0;overflow-wrap:anywhere;line-height:1.55}.state.error{color:#ffb2a9}.state.busy{color:#82dec0}
      .usage{font-size:10px;color:#7f929e;min-height:15px}.actions{display:flex;gap:7px;flex-wrap:wrap}.primary{background:#79dfbd;color:#0d2a20;border-color:#79dfbd;font-weight:650;flex:1}.primary:hover:enabled{background:#9aebcf}.quiet{background:transparent;font-size:12px}.generate{flex:1}.fill{flex:1;background:#263a44}
      .manual{border-top:1px solid #29363e;margin-top:12px;padding-top:9px;font-size:11px;color:#96aab8}.manual summary{cursor:pointer}.manual textarea{margin-top:8px;min-height:74px;font-size:12px}.manual button{margin-top:8px;width:100%}.foot{margin:10px 0 0;font-size:10px;color:#8295a2}
      .toast{font-size:11px;min-height:0;color:#a6e8d2;margin-top:7px;overflow-wrap:anywhere}
      .mini{display:none;align-items:center;gap:7px;padding:10px 13px;border-radius:13px;background:#14251f;border:1px solid #4b8b75;box-shadow:0 8px 26px #0005;color:#c6f3e1;font-weight:650}.mini span{font-size:10px;color:#8cbfae;font-weight:400}
      [hidden]{display:none!important}.shell.collapsed{display:none}.mini.expanded{display:flex}
      @media(max-width:700px){.shell{width:310px}.body{max-height:calc(100dvh - 140px)}textarea{min-height:90px}}
      @media(prefers-reduced-motion:no-preference){button{transition:background .12s ease}}
    `;
    shadow.appendChild(style);
    function el(tag,className,text) {const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
    function button(label,className,click) {const node=el('button',className,label);node.type='button';node.addEventListener('click',click);return node;}
    const shell=el('section','shell');shell.setAttribute('aria-label','随手回回复草稿助手');
    const head=el('div','head');const brand=el('div','brand','随手回');brand.appendChild(el('span','version','EDGE · 1.2'));
    let collapsed=true,userPlaced=false,geometryReady=false,narrowCollapsed=false,lastWidth=root.innerWidth;
    const mini=button('随手回','mini',()=>setCollapsed(false));mini.setAttribute('aria-label','展开随手回');const miniState=el('span','','回复助手');mini.appendChild(miniState);
    const collapse=button('−','collapse',()=>setCollapsed(true));collapse.title='收起面板，不重新生成';collapse.setAttribute('aria-label','收起随手回');
    head.append(el('span','mark','回'),brand,collapse);shell.appendChild(head);
    const body=el('div','body');shell.appendChild(body);
    const toggleLabel=el('label','toggle');const toggle=el('input');toggle.type='checkbox';toggle.addEventListener('change',()=>actions.onAuto(toggle.checked));
    toggleLabel.append(toggle,document.createTextNode('自动生成自然回复'));body.appendChild(toggleLabel);
    body.appendChild(el('p','hint','开启后，主动打开的当前帖文字会发送到 DeepSeek，可能产生 API 费用。不会自动填入或发送。'));
    const identity=el('div','identity'),author=el('span','author','等待帖子'),link=el('a','link','查看原帖');link.target='_blank';link.rel='noopener noreferrer';link.hidden=true;
    identity.append(author,link);body.appendChild(identity);const source=el('div','source','请打开一条 X 帖子。');body.appendChild(source);
    const styleRow=el('div','row');styleRow.appendChild(el('span','label','语气'));const styles=el('div','styles');const styleButtons=new Map();
    for(const name of ['自然','犀利','幽默']) {const control=button(name,'',()=>actions.onStyle(name));control.setAttribute('aria-pressed','false');styles.appendChild(control);styleButtons.set(name,control);}styleRow.appendChild(styles);body.appendChild(styleRow);
    const draftLabel=el('div','draft-label');draftLabel.appendChild(el('span','','回复草稿 · 可直接编辑'));const editState=el('span','dirty');draftLabel.appendChild(editState);body.appendChild(draftLabel);
    const draft=el('textarea');draft.maxLength=500;draft.setAttribute('aria-label','编辑回复草稿');draft.placeholder='生成后先看一眼，让观点更像你。';draft.addEventListener('input',()=>actions.onEdit(draft.value));body.appendChild(draft);
    const state=el('div','state');state.setAttribute('role','status');state.setAttribute('aria-live','polite');body.appendChild(state);
    const usage=el('div','usage');body.appendChild(usage);
    const first=el('div','actions');const generate=button('生成','generate',actions.onGenerate),regenerate=button('重新生成','quiet',actions.onRegenerate);first.append(generate,regenerate);body.appendChild(first);
    const second=el('div','actions');second.style.marginTop='8px';const copy=button('复制草稿','primary',actions.onCopy),fill=button('手动填充','fill',actions.onManualFill);fill.title='复制后由你在 X 回复框按 Ctrl+V；不会操作网页输入框';second.append(copy,fill);body.appendChild(second);
    const toast=el('div','toast');toast.setAttribute('role','status');body.appendChild(toast);
    const manual=el('details','manual');manual.appendChild(el('summary','','没识别到？手动提供原文'));const manualText=el('textarea');manualText.maxLength=3000;manualText.setAttribute('aria-label','手动提供原帖正文');manualText.placeholder='仅粘贴你正在查看的原帖正文';manual.appendChild(manualText);
    manual.appendChild(button('使用这段原文','quiet',()=>actions.onManualSource(manualText.value)));body.appendChild(manual);
    body.appendChild(el('p','foot','发布前请核对原帖和观点。X 输入框需你自行粘贴，最终由你发送。'));
    shadow.append(shell,mini);document.documentElement.appendChild(host);
    function setCollapsed(value,userAction=true) {if(userAction)userPlaced=true;collapsed=!!value;shell.classList.toggle('collapsed',collapsed);mini.classList.toggle('expanded',collapsed);clamp();}
    function clamp() {
      const bounds=host.getBoundingClientRect();
      host.style.left=Math.max(8,Math.min(parseFloat(host.style.left)||8,root.innerWidth-bounds.width-8))+'px';
      if(host.style.top)host.style.top=Math.max(8,Math.min(parseFloat(host.style.top)||8,root.innerHeight-bounds.height-8))+'px';
    }
    function autoLayout(isResize=false) {
      const column=document.querySelector('main [data-testid="primaryColumn"]') || document.querySelector('main');
      const rect=column?.getBoundingClientRect();
      const width=Math.min(root.innerWidth-28,root.innerWidth<=700?310:330);
      const placement=chooseDock(root.innerWidth,rect,width);
      if(rect?.width>0)geometryReady=true;
      if(!userPlaced) {
        host.style.left=placement.left+'px';host.style.top='';host.style.bottom='20px';
        setCollapsed(placement.collapsed,false);narrowCollapsed=placement.collapsed;
      } else if(isResize && root.innerWidth<lastWidth && placement.collapsed && !narrowCollapsed) {
        setCollapsed(true,false);narrowCollapsed=true;
      }
      if(!placement.collapsed)narrowCollapsed=false;
      lastWidth=root.innerWidth;clamp();
    }
    const resize=()=>autoLayout(true);
    let drag=null;
    head.addEventListener('pointerdown',event=>{if(event.button!==0||event.target.closest('button'))return;userPlaced=true;const rect=host.getBoundingClientRect();drag={x:event.clientX,y:event.clientY,left:rect.left,top:rect.top};head.setPointerCapture(event.pointerId);});
    head.addEventListener('pointermove',event=>{if(!drag)return;host.style.bottom='auto';host.style.left=drag.left+event.clientX-drag.x+'px';host.style.top=drag.top+event.clientY-drag.y+'px';clamp();});
    head.addEventListener('pointerup',()=>{drag=null;});head.addEventListener('pointercancel',()=>{drag=null;});root.addEventListener('resize',resize);
    autoLayout();
    return {
      host,
      render(current) {
        if(current.post && !geometryReady && !userPlaced)autoLayout();
        const checked=root.Suishou.post.validateDraft(current.draft);
        toggle.checked=current.auto;
        author.textContent=current.post?.author || '等待当前原帖';
        link.hidden=!current.post;
        if(current.post)link.href=current.post.url;else link.removeAttribute('href');
        source.textContent=current.post ? current.post.text : current.reason || '请主动打开一条 X 帖子的详情页。';
        for(const [name,control] of styleButtons){const selected=name===current.style;control.classList.toggle('selected',selected);control.setAttribute('aria-pressed',String(selected));}
        if(draft.value!==current.draft)draft.value=current.draft;
        draft.disabled=!current.post;editState.textContent=`${current.dirty?'已编辑 · ':''}${checked.length}/280`;
        const lengthError=current.draft&&!checked.valid?checked.message:'';
        state.className='state'+(current.error||lengthError?' error':current.loading?' busy':'');
        state.textContent=lengthError || current.error || current.status || (current.post?'点击生成，或开启自动生成。':'仅读取当前帖；无法确认时请手动提供原文。');
        const tokens=current.usage?.total_tokens;usage.textContent=Number.isFinite(tokens)?`${current.cached?'会话缓存 · ':''}本次用量 ${tokens} tokens`:'';
        generate.textContent=current.loading?'生成中…':current.error?'重试':'生成';
        generate.disabled=!current.post||current.loading;regenerate.disabled=!current.post||current.loading;
        copy.disabled=!checked.valid;fill.disabled=!checked.valid;
        miniState.textContent=current.loading?'生成中…':current.error?'查看提示':current.draft?'草稿已就绪':current.auto?'自动已开启':'回复助手';
        clamp();
      },
      feedback(message) {toast.textContent=message;},
      show(value) {host.hidden=!value;},
      destroy() {root.removeEventListener('resize',resize);host.remove();},
    };
  }
  root.Suishou = root.Suishou || {};root.Suishou.createPanel=createPanel;
  if(typeof module!=='undefined'&&module.exports)module.exports={createPanel,chooseDock};
})(globalThis);
