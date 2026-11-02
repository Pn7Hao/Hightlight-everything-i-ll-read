/* Reading overlay. Contains annotation coordinates, never the source article.
 * Manifest offsets: UTF-16 indices into normalizedSectionText(section).
 * Hash: SHA-256 over UTF-8 normalized text. Whitespace: JS /\s+/ collapsed.
 */
(function readingOverlay(global) {
  'use strict';
  const EXCLUDED = 'script,style,noscript,template,.anchorjs-link,.anchor-section,.quarto-appendix-citeas,.reader-owned';
  const PRIORITIES = Object.freeze({deep: 'Đọc kỹ', skim: 'Đọc lướt', reference: 'Tra cứu'});
  const STATE = {manifest: null, options: {}, report: null};

  function collectText(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        return node.parentElement && node.parentElement.closest(EXCLUDED)
          ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    const chars = [], positions = [];
    let pendingStart = null, pendingEnd = null;
    for (const node of nodes) {
      const value = node.nodeValue;
      for (let offset = 0; offset < value.length; offset++) {
        const point = {node, offset};
        const after = {node, offset: offset + 1};
        if (/\s/.test(value[offset])) {
          if (!pendingStart) pendingStart = point;
          pendingEnd = after;
          continue;
        }
        if (pendingStart && chars.length) {
          chars.push(' ');
          positions.push({start: pendingStart, end: pendingEnd});
        }
        pendingStart = pendingEnd = null;
        chars.push(value[offset]);
        positions.push({start: point, end: after});
      }
    }
    return {text: chars.join(''), positions, nodes};
  }

  function normalizedSectionText(element) { return collectText(element).text; }

  // The small fallback also supports a local file opened in an opaque iframe.
  async function sha256(text) {
    const input = new TextEncoder().encode(text);
    if (global.crypto && global.crypto.subtle) {
      const bytes = new Uint8Array(await global.crypto.subtle.digest('SHA-256', input));
      return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
    }
    const constants = [], initial = [];
    for (let number = 2; constants.length < 64; number++) {
      let prime = true;
      for (let divisor = 2; divisor * divisor <= number; divisor++) {
        if (number % divisor === 0) { prime = false; break; }
      }
      if (prime) {
        if (initial.length < 8) initial.push((Math.sqrt(number) % 1 * 0x100000000) >>> 0);
        constants.push((Math.cbrt(number) % 1 * 0x100000000) >>> 0);
      }
    }
    const length = Math.ceil((input.length + 9) / 64) * 64;
    const bytes = new Uint8Array(length);
    bytes.set(input); bytes[input.length] = 0x80;
    const view = new DataView(bytes.buffer);
    const bitLength = input.length * 8;
    view.setUint32(length - 8, Math.floor(bitLength / 0x100000000));
    view.setUint32(length - 4, bitLength >>> 0);
    const rotate = (value, amount) => (value >>> amount) | (value << (32 - amount));
    const hash = initial.slice(), words = new Uint32Array(64);
    for (let block = 0; block < length; block += 64) {
      for (let i = 0; i < 16; i++) words[i] = view.getUint32(block + i * 4);
      for (let i = 16; i < 64; i++) {
        const x = words[i - 15], y = words[i - 2];
        const small0 = rotate(x, 7) ^ rotate(x, 18) ^ (x >>> 3);
        const small1 = rotate(y, 17) ^ rotate(y, 19) ^ (y >>> 10);
        words[i] = (words[i - 16] + small0 + words[i - 7] + small1) >>> 0;
      }
      let [a, b, c, d, e, f, g, h] = hash;
      for (let i = 0; i < 64; i++) {
        const sum1 = rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25);
        const choose = (e & f) ^ (~e & g);
        const temp1 = (h + sum1 + choose + constants[i] + words[i]) >>> 0;
        const sum0 = rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22);
        const majority = (a & b) ^ (a & c) ^ (b & c);
        const temp2 = (sum0 + majority) >>> 0;
        h = g; g = f; f = e; e = (d + temp1) >>> 0;
        d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
      }
      [a,b,c,d,e,f,g,h].forEach((value, index) => { hash[index] = (hash[index] + value) >>> 0; });
    }
    return hash.map(value => value.toString(16).padStart(8, '0')).join('');
  }

  function clearOverlay() {
    document.querySelectorAll('mark.reader-highlight').forEach(mark => mark.replaceWith(...mark.childNodes));
    document.querySelectorAll('.reader-owned').forEach(element => element.remove());
    document.querySelectorAll('[data-reader-priority]').forEach(element => element.removeAttribute('data-reader-priority'));
    document.documentElement.classList.remove('reader-highlights-hidden', 'reader-notes-hidden');
  }

  function highlightRanges(index, ranges, priority) {
    const byNode = new Map();
    const nodeOrder = new Map(index.nodes.map((node, i) => [node, i]));
    for (const range of ranges) {
      const start = index.positions[range.start].start;
      const end = index.positions[range.end - 1].end;
      const first = nodeOrder.get(start.node), last = nodeOrder.get(end.node);
      for (let i = first; i <= last; i++) {
        const node = index.nodes[i];
        const left = i === first ? start.offset : 0;
        const right = i === last ? end.offset : node.nodeValue.length;
        if (right <= left || !node.nodeValue.slice(left, right).trim()) continue;
        if (!byNode.has(node)) byNode.set(node, []);
        byNode.get(node).push([left, right]);
      }
    }
    let fragments = 0;
    for (const [node, intervals] of byNode) {
      intervals.sort((a, b) => a[0] - b[0]);
      const merged = [];
      for (const interval of intervals) {
        const previous = merged[merged.length - 1];
        if (previous && interval[0] <= previous[1]) previous[1] = Math.max(previous[1], interval[1]);
        else merged.push(interval.slice());
      }
      for (const [left, right] of merged.reverse()) {
        node.splitText(right);
        const selected = node.splitText(left);
        const mark = document.createElement('mark');
        mark.className = `reader-highlight reader-highlight-${priority}`;
        selected.replaceWith(mark);
        mark.appendChild(selected);
        fragments++;
      }
    }
    return fragments;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function button(id, label, handler) {
    const node = element('button', 'reader-button', label);
    node.id = id; node.type = 'button';
    if (id.startsWith('reader-toggle-')) node.setAttribute('aria-pressed', 'false');
    node.addEventListener('click', handler);
    return node;
  }

  // A publisher <base> is needed for assets, but fragment clicks stay here.
  function keepLocalFragments(event) {
    const link = event.target.closest?.('a[href]');
    const href = link?.getAttribute('href');
    if (!href || !href.startsWith('#')) return;
    event.preventDefault();
    let id;
    try { id = decodeURIComponent(href.slice(1)); } catch (_) { return; }
    const target = document.getElementById(id) || document.getElementsByName(id)[0];
    if (target) target.scrollIntoView({block: 'start'});
    else if (!id) window.scrollTo(0, 0);
  }
  document.addEventListener('click', keepLocalFragments);

  function makeToolbar(manifest, report) {
    const toolbar = element('aside', 'reader-owned reader-toolbar');
    toolbar.id = 'evals-reader-toolbar';
    toolbar.setAttribute('aria-label', 'Công cụ đọc và highlight');
    const title = element('div', 'reader-toolbar-title', 'Ghi chú đọc · Evals FAQ');
    const legend = element('div', 'reader-legend');
    Object.entries(PRIORITIES).forEach(([priority, label]) => {
      legend.appendChild(element('span', `reader-chip reader-chip-${priority}`, label));
    });
    title.appendChild(legend); toolbar.appendChild(title);
    const route = manifest.readingRoute || manifest.reading_route || (manifest.quickRoute || []).map(ordinal => {
      const section = manifest.sections.find(item => item.ordinal === ordinal);
      return section ? {id: section.id, label: '#' + String(ordinal).padStart(2, '0')} : null;
    }).filter(Boolean);
    if (route.length) {
      const nav = element('nav', 'reader-route');
      nav.setAttribute('aria-label', 'Lộ trình đọc');
      nav.appendChild(element('span', '', 'Đọc nhanh: '));
      for (const item of route) {
        const link = element('a', '', item.label || item.id);
        link.href = '#' + item.id;
        nav.appendChild(link);
      }
      toolbar.appendChild(nav);
    }
    const controls = element('div', 'reader-controls');
    controls.appendChild(button('reader-toggle-highlights', 'Ẩn highlight', event => {
      const hidden = document.documentElement.classList.toggle('reader-highlights-hidden');
      event.currentTarget.textContent = hidden ? 'Hiện highlight' : 'Ẩn highlight';
      event.currentTarget.setAttribute('aria-pressed', String(hidden));
    }));
    controls.appendChild(button('reader-toggle-notes', 'Ẩn nhãn ưu tiên', event => {
      const hidden = document.documentElement.classList.toggle('reader-notes-hidden');
      event.currentTarget.textContent = hidden ? 'Hiện nhãn ưu tiên' : 'Ẩn nhãn ưu tiên';
      event.currentTarget.setAttribute('aria-pressed', String(hidden));
    }));
    controls.appendChild(button('reader-print', 'In / lưu PDF', () => global.print()));
    controls.appendChild(button('reader-save-html', 'Lưu HTML', async event => {
      const control = event.currentTarget;
      control.disabled = true;
      setStatus('Đang gom hình, font và CSS để lưu HTML…');
      try {
        const result = await downloadHTML();
        setStatus(result.failed.length
          ? `Đã lưu HTML; ${result.failed.length} tài nguyên vẫn cần mạng. Giữ kết nối khi mở hoặc in.`
          : 'Đã lưu HTML tự chứa. Có thể mở và in khi không có mạng.');
      } catch (error) { setStatus('Chưa lưu được HTML: ' + error.message, true); }
      finally { control.disabled = false; }
    }));
    toolbar.appendChild(controls);
    const status = element('p', 'reader-status');
    status.id = 'reader-status'; status.setAttribute('role', 'status');
    const skipped = report.missing.length + report.changed.length + report.invalid.length;
    status.textContent = `${report.matched}/${report.total} mục đã đối chiếu; ${report.highlights} đoạn highlight.`
      + (skipped ? ` ${skipped} mục đã đổi hoặc không khớp: chưa áp highlight.` : ' Văn bản nguồn được giữ nguyên.');
    if (skipped) status.classList.add('reader-warning');
    toolbar.appendChild(status);
    document.body.prepend(toolbar);
  }

  function setStatus(message, warning) {
    const status = document.getElementById('reader-status');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('reader-warning', Boolean(warning));
  }

  async function applyReadingHighlights(manifest, options) {
    if (!manifest || !Array.isArray(manifest.sections)) throw new TypeError('Manifest thiếu danh sách sections.');
    clearOverlay();
    STATE.manifest = manifest; STATE.options = options || {};
    if (STATE.options.cssText) {
      document.getElementById('evals-reader-css')?.remove();
      const style = element('style');
      style.id = 'evals-reader-css'; style.textContent = STATE.options.cssText;
      document.head.appendChild(style);
    }
    const report = {total: manifest.sections.length, matched: 0, highlights: 0, fragments: 0, missing: [], changed: [], invalid: []};
    for (const section of manifest.sections) {
      const root = document.getElementById(section.id);
      if (!root) { report.missing.push(section.id); continue; }
      const index = collectText(root);
      if (!section.sha256 || await sha256(index.text) !== section.sha256.toLowerCase()) {
        report.changed.push(section.id); continue;
      }
      const ranges = section.ranges || [];
      if (!PRIORITIES[section.priority] || ranges.some(range =>
        !Number.isInteger(range.start) || !Number.isInteger(range.end)
        || range.start < 0 || range.end <= range.start || range.end > index.text.length)) {
        report.invalid.push(section.id); continue;
      }
      report.fragments += highlightRanges(index, ranges, section.priority);
      if (normalizedSectionText(root) !== index.text) throw new Error('Văn bản thay đổi trong khi áp highlight: ' + section.id);
      const heading = root.querySelector('h1,h2,h3,h4,h5,h6');
      if (heading) {
        const badge = element('span', `reader-owned reader-priority-badge reader-chip-${section.priority}`,
          `#${String(section.ordinal).padStart(2, '0')} · ${PRIORITIES[section.priority]}`);
        heading.prepend(badge);
      }
      root.dataset.readerPriority = section.priority;
      report.matched++; report.highlights += ranges.length;
    }
    makeToolbar(manifest, report);
    STATE.report = report;
    return report;
  }

  function blobDataURL(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('Không đọc được tài nguyên.'));
      reader.readAsDataURL(blob);
    });
  }

  async function buildOfflineHTML() {
    const base = STATE.options.sourceUrl || STATE.manifest?.sourceUrl || STATE.manifest?.source_url || document.baseURI;
    const copy = document.documentElement.cloneNode(true);
    const failed = new Set(), cache = new Map();
    const absolute = (value, parent = base) => {
      try { return new URL(value, parent).href; } catch (_) { return value; }
    };
    async function resource(url) {
      if (/^(data:|blob:|#)/i.test(url)) return url;
      const resolved = absolute(url);
      if (!cache.has(resolved)) cache.set(resolved, (async () => {
        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 15000);
          let response;
          try { response = await fetch(resolved, {credentials: 'omit', signal: controller.signal}); }
          finally { clearTimeout(timeout); }
          if (!response.ok) throw new Error(String(response.status));
          const blob = await response.blob();
          if (blob.size > 20 * 1024 * 1024) throw new Error('Tài nguyên quá lớn.');
          return await blobDataURL(blob);
        } catch (_) { failed.add(resolved); return resolved; }
      })());
      return cache.get(resolved);
    }
    async function inlineCSS(css, cssBase, depth = 0) {
      if (depth < 3) {
        const imports = [...css.matchAll(/@import\s+(?:url\(\s*)?["']([^"']+)["']\s*\)?\s*([^;]*);/gi)];
        for (const match of imports) {
          const importedURL = absolute(match[1], cssBase);
          try {
            const response = await fetch(importedURL, {credentials: 'omit'});
            if (!response.ok) throw new Error(String(response.status));
            let imported = await inlineCSS(await response.text(), importedURL, depth + 1);
            if (match[2].trim()) imported = `@media ${match[2]}{${imported}}`;
            css = css.replace(match[0], imported);
          } catch (_) { failed.add(importedURL); css = css.replace(match[1], importedURL); }
        }
      }
      const matches = [...css.matchAll(/url\(\s*(['"]?)([^)'"\s]+)\1\s*\)/gi)];
      for (const match of matches) {
        if (/^(data:|#)/i.test(match[2])) continue;
        const embedded = await resource(absolute(match[2], cssBase));
        css = css.replace(match[0], `url("${embedded}")`);
      }
      return css;
    }
    copy.querySelectorAll('script,noscript,link[rel="preload"],link[rel="preconnect"],link[rel="dns-prefetch"],meta[http-equiv="refresh"]').forEach(node => node.remove());
    copy.querySelectorAll('*').forEach(node => {
      for (const attribute of [...node.attributes]) {
        if (/^on/i.test(attribute.name)) node.removeAttribute(attribute.name);
      }
    });
    const originalLinks = [...document.querySelectorAll('link[rel="stylesheet"]')];
    const copiedLinks = [...copy.querySelectorAll('link[rel="stylesheet"]')];
    for (let i = 0; i < copiedLinks.length; i++) {
      const link = copiedLinks[i];
      if (originalLinks[i]?.disabled) { link.remove(); continue; }
      const url = absolute(link.getAttribute('href'));
      try {
        const response = await fetch(url, {credentials: 'omit'});
        if (!response.ok) throw new Error(String(response.status));
        const style = element('style');
        if (link.media) style.media = link.media;
        style.textContent = await inlineCSS(await response.text(), url);
        link.replaceWith(style);
      } catch (_) { failed.add(url); link.setAttribute('href', url); }
    }
    for (const style of copy.querySelectorAll('style')) {
      style.textContent = await inlineCSS(style.textContent, base);
    }
    const originalImages = [...document.querySelectorAll('img')];
    const images = [...copy.querySelectorAll('img')];
    for (let offset = 0; offset < images.length; offset += 4) {
      await Promise.all(images.slice(offset, offset + 4).map(async (image, index) => {
        const original = originalImages[offset + index];
        const src = original?.currentSrc || image.getAttribute('src');
        if (src) image.setAttribute('src', await resource(absolute(src)));
        image.removeAttribute('srcset'); image.removeAttribute('loading');
      }));
    }
    copy.querySelectorAll('picture source').forEach(node => node.remove());
    for (const node of copy.querySelectorAll('[style]')) {
      node.setAttribute('style', await inlineCSS(node.getAttribute('style'), base));
    }
    for (const node of copy.querySelectorAll('link[rel~="icon"][href]')) {
      node.setAttribute('href', await resource(absolute(node.getAttribute('href'))));
    }
    for (const node of copy.querySelectorAll('video[src],audio[src],source[src],video[poster],input[type="image"][src],svg image[href],svg image[xlink\\:href]')) {
      for (const attribute of ['src','poster','href','xlink:href']) {
        const value = node.getAttribute(attribute);
        if (value) node.setAttribute(attribute, await resource(absolute(value)));
      }
    }
    for (const node of copy.querySelectorAll('a[href],link[href]')) {
      const href = node.getAttribute('href');
      if (href && !/^(#|data:|mailto:|tel:)/i.test(href)) node.setAttribute('href', absolute(href));
    }
    copy.querySelectorAll('base').forEach(node => node.remove());
    copy.querySelectorAll('iframe').forEach(frame => {
      const url = frame.getAttribute('src');
      if (!url || /googletagmanager|google-analytics/i.test(url)) { frame.remove(); return; }
      const link = element('a', '', 'Mở nội dung nhúng trên trang gốc');
      link.href = absolute(url); frame.replaceWith(link);
    });
    copy.querySelector('#reader-save-html')?.remove();
    const status = copy.querySelector('#reader-status');
    if (status) status.textContent = failed.size
      ? `Bản đã lưu; ${failed.size} tài nguyên vẫn cần mạng.`
      : 'Bản đã lưu để đọc offline. Highlight và nhãn ưu tiên là ghi chú biên tập.';
    const script = element('script');
    script.textContent = `document.addEventListener('click', ${keepLocalFragments.toString()});\ndocument.getElementById('reader-print')?.addEventListener('click',()=>window.print());
document.getElementById('reader-toggle-highlights')?.addEventListener('click',e=>{const h=document.documentElement.classList.toggle('reader-highlights-hidden');e.currentTarget.textContent=h?'Hiện highlight':'Ẩn highlight';e.currentTarget.setAttribute('aria-pressed',String(h));});
document.getElementById('reader-toggle-notes')?.addEventListener('click',e=>{const h=document.documentElement.classList.toggle('reader-notes-hidden');e.currentTarget.textContent=h?'Hiện nhãn ưu tiên':'Ẩn nhãn ưu tiên';e.currentTarget.setAttribute('aria-pressed',String(h));});`;
    copy.querySelector('body').appendChild(script);
    return {html: '<!DOCTYPE html>\n' + copy.outerHTML, failed: [...failed]};
  }

  async function downloadHTML() {
    const result = await buildOfflineHTML();
    const blob = new Blob([result.html], {type: 'text/html;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = element('a');
    link.href = url;
    link.download = STATE.options.filename || 'hamel-evals-faq-highlighted.html';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    return {failed: result.failed};
  }

  global.EvalsReading = Object.freeze({
    EXCLUDED, normalizedSectionText, sha256, applyReadingHighlights, buildOfflineHTML, downloadHTML,
    get report() { return STATE.report; }
  });
  global.applyReadingHighlights = applyReadingHighlights;
})(window);
