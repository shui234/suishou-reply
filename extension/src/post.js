/* Read the foreground detail article only. No requests, account actions or DOM writes. */
(function (root) {
  'use strict';
  const invalidText = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]|[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/u;

  function parsePostUrl(value) {
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || !['x.com', 'twitter.com'].includes(url.hostname)
          || url.username || url.password || url.port) return null;
      const match = /^\/([A-Za-z0-9_]{1,15})\/status\/([0-9]{1,25})\/?$/.exec(url.pathname);
      if (!match) return null;
      const handle = match[1].toLowerCase();
      return {id:match[2],author:`@${handle}`,url:`https://x.com/${handle}/status/${match[2]}`};
    } catch { return null; }
  }

  function selectCandidate(candidates, pageUrl) {
    const route = parsePostUrl(pageUrl);
    if (!route) return {post:null,reason:'请主动打开一条 X 帖子的详情页。'};
    const matching = candidates.filter(candidate => {
      const link = parsePostUrl(candidate.url);
      return link && link.url === route.url && !candidate.quoted;
    });
    if (matching.length !== 1) return {post:null,reason:'尚未确认当前原帖，等待加载或手动提供原文。'};
    const found = matching[0];
    const text = typeof found.text === 'string' ? found.text.trim() : '';
    if (found.ownTextCount !== 1 || found.author?.toLowerCase() !== route.author
        || !text || text.length > 3000 || invalidText.test(text)) {
      return {post:null,reason:'原帖正文不完整、过长或结构不明确，请手动提供原文。'};
    }
    return {post:{...route,text},reason:''};
  }

  function belongsToArticle(element, article) {
    if (element.closest('article[data-testid="tweet"]') !== article) return false;
    for (let ancestor = element.parentElement; ancestor && ancestor !== article; ancestor = ancestor.parentElement) {
      if (ancestor.matches('[data-testid="quoteTweet"], [data-testid="card.wrapper"], [data-testid="tweetDetail"], [role="link"]')) return false;
    }
    return true;
  }

  function readText(element) {
    // Emoji images are meaningful text; never use aria labels for hidden page data.
    function visit(node) {
      if (node.nodeType === 3) return node.nodeValue || '';
      if (node.nodeType !== 1) return '';
      if (node.matches('script,style,[hidden],[aria-hidden="true"]')) return '';
      if (node.tagName === 'IMG') return node.getAttribute('alt') || '';
      if (node.tagName === 'BR') return '\n';
      return Array.from(node.childNodes, visit).join('');
    }
    return visit(element).trim();
  }

  function extractCurrentPost(document, pageUrl) {
    const route = parsePostUrl(pageUrl);
    if (!route) return {post:null,reason:'请主动打开一条 X 帖子的详情页。'};
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
    const candidates = [];
    for (const article of articles) {
      if (article.closest('[role="dialog"]') || article.closest('[hidden],[aria-hidden="true"]')) continue;
      const ownTimes = Array.from(article.querySelectorAll('a[href]')).filter(link =>
        link.querySelector('time') && belongsToArticle(link, article));
      const matchingLinks = ownTimes.filter(link => parsePostUrl(link.href)?.url === route.url);
      if (matchingLinks.length !== 1) continue;
      const texts = Array.from(article.querySelectorAll('[data-testid="tweetText"]')).filter(node => belongsToArticle(node, article));
      const ownName = Array.from(article.querySelectorAll('[data-testid="User-Name"]')).find(node => belongsToArticle(node, article));
      const profileLinks = ownName ? Array.from(ownName.querySelectorAll('a[href]')) : [];
      const hasAuthor = profileLinks.some(link => {
        try { const url = new URL(link.href); return ['x.com','twitter.com'].includes(url.hostname)
          && url.pathname.toLowerCase().replace(/\/$/,'') === '/' + route.author.slice(1); }
        catch { return false; }
      });
      // A timestamp permalink identifies the post; an explicit author block must agree.
      candidates.push({url:matchingLinks[0].href,author:hasAuthor || !ownName ? route.author : '',
        ownTextCount:texts.length,text:texts.length === 1 ? readText(texts[0]) : ''});
    }
    return selectCandidate(candidates, pageUrl);
  }

  function weightedLength(text) {
    // Conservative rather than a full twitter-text parser: URLs cost at least 23,
    // long URLs retain their full weight, and ambiguous Unicode domains get extra reserve.
    const value=String(text),plain=part=>Array.from(part).reduce((sum,char)=>sum+(char.codePointAt(0)<128?1:2),0);
    const urls=/https?:\/\/[^\s<>"\u0080-\uffff]*|(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?:[/?#][^\s<>"\u0080-\uffff]*)?|(?:[\p{L}\p{N}-]+\.)+[\p{L}]{2,63}/giu;
    let total=0,cursor=0;
    for(const match of value.matchAll(urls)) {
      total+=plain(value.slice(cursor,match.index));
      const link=match[0].replace(/[.,!?:;\)\]\}\u3001\u3002\uff0c\uff01\uff1f\uff1a\uff1b\u2026\uff09\u3011\u300b\u3009\u300d\u300f]+$/u,'');
      const tail=match[0].slice(link.length);
      total+=(/[^\x00-\x7f]/u.test(link)?23+plain(link):Math.max(23,plain(link)))+plain(tail);
      cursor=match.index+match[0].length;
    }
    return total+plain(value.slice(cursor));
  }
  function validateDraft(text) {
    const length=weightedLength(text);
    if(typeof text!=='string'||!text.trim())return {valid:false,length,message:'请先生成或编辑回复草稿。'};
    if(invalidText.test(text))return {valid:false,length,message:'草稿含隐藏或不支持的字符，请清理后复制。'};
    if(length>280)return {valid:false,length,message:'草稿超过 280 加权字符，请编辑缩短后再复制。'};
    return {valid:true,length,message:''};
  }
  const api = {parsePostUrl,selectCandidate,extractCurrentPost,readText,weightedLength,validateDraft};
  root.Suishou = root.Suishou || {};
  root.Suishou.post = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
