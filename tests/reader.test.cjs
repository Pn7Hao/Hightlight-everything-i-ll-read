'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {TextEncoder} = require('node:util');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '../readings/hamel-evals-faq');
const kitPath = process.env.READING_KIT || path.join(root, 'hamel-evals-reading-kit.html');
const annotatorPath = process.env.READING_ANNOTATOR || path.join(root, 'tools/annotator.js');
function kit() {
  return new JSDOM(fs.readFileSync(kitPath, 'utf8'), {
    runScripts: 'dangerously', url: 'https://reader.example.test/',
    beforeParse(w) {w.TextEncoder = TextEncoder;}
  });
}
function article(html) {
  const dom = new JSDOM(html, {runScripts:'dangerously',url:'https://reader.example.test/'});
  dom.window.TextEncoder = TextEncoder;
  dom.window.eval(fs.readFileSync(annotatorPath,'utf8'));
  return dom;
}
const manifest = {sourceUrl:'https://publisher.example.test/article/',sections:[],readingRoute:[{id:'target',label:'Target'}]};

test('sanitization removes normalized executable URLs and SVG URL attributes', () => {
  const dom=kit(), w=dom.window;
  try {
    const payloads=[' javascript:parent.__proof=1','\tjavascript:parent.__proof=1','java\nscript:parent.__proof=1','&#106;avascript:parent.__proof=1'];
    for (const value of payloads) {
      const clean=new JSDOM(w.cleanHTML(`<a id="attack" href="${value}">click</a><svg><a id="svg-attack" xlink:href="${value}">SVG</a></svg>`));
      for (const id of ['attack','svg-attack']) {
        const a=clean.window.document.getElementById(id);
        assert.equal(a?.getAttribute('href') || a?.getAttribute('xlink:href') || null, null, value);
      }
      clean.window.close();
    }
  } finally {w.close();}
});

test('sanitization keeps formatting/HTTP assets but removes active imported markup', () => {
  const dom=kit();
  try {
    const out=new JSDOM(dom.window.cleanHTML(`<html><head><link rel="stylesheet" href="style.css"><style>p{color:red}</style><meta http-equiv="refresh" content="0;url=https://bad.test"></head><body><h2 id="target">Title</h2><p onclick="alert(1)">Text</p><img src="image.png" onerror="alert(1)"><script>window.__bad=1</script><iframe src=" javascript:alert(1)"></iframe><svg><set attributeName="href" to="javascript:alert(1)"></set></svg><a href="#target">go</a></body></html>`));
    const d=out.window.document;
    assert.equal(d.querySelectorAll('script,iframe,object,embed,form,meta[http-equiv],svg set').length,0);
    assert.equal(d.querySelector('[onclick],[onerror]'),null);
    assert.equal(d.querySelector('meta[charset]').getAttribute('charset'),'utf-8');
    assert.equal(d.querySelector('link[rel=stylesheet]').getAttribute('href'),'style.css');
    assert.equal(d.querySelector('img').getAttribute('src'),'image.png');
    assert.equal(d.querySelector('style').textContent,'p{color:red}');
    assert.equal(d.querySelector('a[href="#target"]').getAttribute('href'),'#target');
    out.window.close();
  } finally {dom.window.close();}
});

test('complete-webpage companion assets fail clearly before preview', () => {
  const dom=kit();
  try {
    for(const fixture of ['<link rel="stylesheet" href="FAQ_files/main.css">','<img src="./FAQ%20page_files/a.png">','<style>body{background:url(FAQ_files/a.png)}</style>'])
      assert.throws(()=>dom.window.cleanHTML(fixture),/Webpage, Complete.*curl/);
    assert.doesNotThrow(()=>dom.window.cleanHTML('<img src="images/normal.png">'));
  } finally {dom.window.close();}
});

test('preview route and article fragments scroll locally despite remote base', async () => {
  const dom=article('<base href="https://publisher.example.test/article/"><a id="contents" href="#target">Contents</a><p id="target">Target</p>');
  try {
    const w=dom.window; let scrolled=0;
    w.document.getElementById('target').scrollIntoView=()=>scrolled++;
    await w.applyReadingHighlights(manifest,{});
    for(const selector of ['.reader-route a','#contents']) {
      const event=new w.MouseEvent('click',{bubbles:true,cancelable:true});
      assert.equal(w.document.querySelector(selector).dispatchEvent(event),false);
      assert.equal(event.defaultPrevented,true);
    }
    assert.equal(scrolled,2);
    assert.ok(w.document.getElementById('evals-reader-toolbar'));
    assert.equal(w.location.href,'https://reader.example.test/');
  } finally {dom.window.close();}
});

test('saved page toggles announce both states and keeps fragment handling', async () => {
  const dom=article('<meta charset="utf-8"><base href="https://publisher.example.test/article/"><p id="target">Target</p>');
  let saved;
  try {
    await dom.window.applyReadingHighlights(manifest,{});
    dom.window.document.getElementById('reader-toggle-highlights').click();
    const result=await dom.window.EvalsReading.buildOfflineHTML();
    saved=new JSDOM(result.html,{runScripts:'dangerously',url:'https://reader.example.test/saved.html'});
    assert.equal(saved.window.document.querySelector('meta[charset]').getAttribute('charset'),'utf-8');
    for(const [id,cls] of [['reader-toggle-highlights','reader-highlights-hidden'],['reader-toggle-notes','reader-notes-hidden']]) {
      const button=saved.window.document.getElementById(id);
      for(let i=0;i<2;i++) {
        button.click();
        assert.equal(button.getAttribute('aria-pressed'),String(saved.window.document.documentElement.classList.contains(cls)));
      }
    }
    let scrolled=0;saved.window.document.getElementById('target').scrollIntoView=()=>scrolled++;
    const event=new saved.window.MouseEvent('click',{bubbles:true,cancelable:true});
    saved.window.document.querySelector('.reader-route a').dispatchEvent(event);
    assert.equal(event.defaultPrevented,true);assert.equal(scrolled,1);
  } finally {dom.window.close();saved?.window.close();}
});
