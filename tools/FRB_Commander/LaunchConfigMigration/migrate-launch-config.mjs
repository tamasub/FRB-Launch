import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

const defaults = {enabled:true,page_id:'system',files_item_id:'folders',bookmarks_item_id:'__browser_bookmarks_root'};
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
function index(rows,key) {
  if (!Array.isArray(rows)) throw Error(`${key}: 配列が必要です`);
  const map = new Map();
  for (const r of rows) {
    if (!object(r) || typeof r[key] !== 'string' || !r[key].trim() || map.has(r[key])) throw Error(`${key}: ID不正・重複`);
    map.set(r[key],r);
  }
  return map;
}
function safeNumbers(x) {
  if (typeof x === 'number' && (!Number.isFinite(x) || (Number.isInteger(x) && !Number.isSafeInteger(x)))) throw Error('精度を維持できない数値が含まれています。変換を中止します。');
  if (x && typeof x === 'object') Object.values(x).forEach(safeNumbers);
}
export function migrate(input, options = {}) {
  if (!object(input) || !object(options)) throw Error('JSONルートが不正です');
  safeNumbers(input);
  const o = {...defaults,...options};
  for (const k of ['page_id','files_item_id','bookmarks_item_id']) if (typeof o[k] !== 'string' || !o[k].trim()) throw Error(`expanded_view.${k}: 不正`);
  if (o.enabled !== true || o.files_item_id === o.bookmarks_item_id) throw Error('Expanded設定が無効または不正です。config/expanded_view_options.json を確認してください。');
  const data = structuredClone(input), changes = [];
  const pages = index(data.pages,'page_id'), items = index(data.items,'item_id');
  // Reject structural ambiguity; no silent deletion or guesswork.
  for (const row of items.values()) {
    if (!pages.has(row.page_id)) throw Error(`不明なPage: ${row.item_id}`);
    const seen = new Set([row.item_id]); let parent = row.parent_item_id;
    while (parent) {
      if (seen.has(parent) || !items.has(parent)) throw Error(`親階層不正: ${row.item_id}`);
      seen.add(parent); const p = items.get(parent);
      if (p.item_kind !== 'category') throw Error(`親がカテゴリーではありません: ${row.item_id}`);
      parent = p.parent_item_id;
    }
  }
  const set = (r,k,v,id) => {if (r[k] !== v) {changes.push(`${id}.${k}: ${JSON.stringify(r[k])} → ${JSON.stringify(v)}`);r[k]=v;}};
  if (!pages.has(o.page_id)) {
    const row = {page_id:o.page_id,title:'System',icon_key:'⚙️',sort_order:50,enabled:true};data.pages.push(row);pages.set(o.page_id,row);changes.push(`Page追加: ${o.page_id}`);
  }
  set(pages.get(o.page_id),'enabled',true,o.page_id);
  const bookmarkCandidates = data.items.filter(r=>r.launch_source==='browser_bookmarks' && r.item_kind==='category');
  if (bookmarkCandidates.some(r=>r.item_id!==o.bookmarks_item_id)) throw Error('別IDのブックマークカテゴリーがあります。自動でIDを変更せず中止します。');
  function root(id, bookmark) {
    let r=items.get(id);
    if (!r) {
      r={item_id:id,page_id:o.page_id,parent_item_id:'',title:bookmark?'ブックマーク':'Files（Files Expエリア ルート）',description:bookmark?'Chrome / Edge のブックマークを自動取得':'実フォルダー・ファイルを展開',item_kind:'category',icon_key:'category.blue',sort_order:bookmark?40:20,enabled:true,keywords:[],launch_actions:[]};
      if(bookmark) r.launch_source='browser_bookmarks';
      data.items.push(r);items.set(id,r);changes.push(`ルート追加: ${id}`);
    }
    if(r.item_kind!=='category' || (r.launch_source && r.launch_source !== (bookmark?'browser_bookmarks':''))) throw Error(`専用ルートIDが別用途です: ${id}`);
    set(r,'parent_item_id','',id);
    set(r,'page_id',o.page_id,id);
    // Files may intentionally be disabled in Compact; Expanded ignores that flag.
    if(bookmark) {set(r,'enabled',true,id);set(r,'launch_source','browser_bookmarks',id);}
    const pending=[id], seen=new Set([id]);
    while(pending.length) {const parent=pending.shift();for(const child of items.values()) if(child.parent_item_id===parent && !seen.has(child.item_id)) {
      if(child.item_id===o.files_item_id || child.item_id===o.bookmarks_item_id) continue;
      seen.add(child.item_id);pending.push(child.item_id);set(child,'page_id',o.page_id,child.item_id);
    }}
  }
  root(o.files_item_id,false);root(o.bookmarks_item_id,true);
  set(data,'bookmark_category_initialized',true,'JSON');
  // Check runtime core constraints for the relevant existing data, not just anchors.
  index(data.launch_variables === undefined ? [] : data.launch_variables,'variable_id'); index(data.launch_choices === undefined ? [] : data.launch_choices,'choice_id');
  for(const r of data.items) {
    if(!['category','directory','command','selection'].includes(r.item_kind)) throw Error(`未対応の項目種類: ${r.item_id}`);
    if(r.parent_item_id && items.get(r.parent_item_id).page_id!==r.page_id) throw Error(`親とPageが不一致: ${r.item_id}`);
    const actions=r.launch_actions === undefined ? [] : r.launch_actions;
    if(!Array.isArray(actions)) throw Error(`launch_actions不正: ${r.item_id}`);
    for(const a of actions) if(!object(a)||!['SendKey','ClipboardCopy','Open','Run'].includes(a.launch_action_type)||!Array.isArray(a.launch_arguments === undefined ? [] : a.launch_arguments)||(a.launch_result_format === undefined ? 'none' : a.launch_result_format)!=='none') throw Error(`未対応のアクション: ${r.item_id}`);
  }
  return {data,changes};
}
function readJson(filename) {return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(fs.readFileSync(filename)));}
export function run(mode, input, optionsFile) {
  if(!['Preview','Convert'].includes(mode)) throw Error('Mode不正');
  if(path.extname(input).toLowerCase()!=='.json') throw Error('JSONファイルを選択してください');
  const opts=optionsFile && fs.existsSync(optionsFile)?readJson(optionsFile):{};
  const {data,changes}=migrate(readJson(input),opts);
  console.log(`入力: ${input}\n変更件数: ${changes.length}`);
  changes.forEach(c=>console.log(c));
  console.log('Expanded起動用の専用Page・ルート条件: OK');
  if(mode==='Convert') {
    const out=path.join(path.dirname(input),`${path.basename(input,path.extname(input))}_migrated_${randomUUID().slice(0,8)}.json`);
    const fd=fs.openSync(out,'wx');
    try {fs.writeFileSync(fd,JSON.stringify(data,null,2)+'\n','utf8');fs.fsyncSync(fd);} catch(e){fs.closeSync(fd);fs.unlinkSync(out);throw e;} fs.closeSync(fd);
    console.log(`出力: ${out}\n原本は変更していません。`);
  } else console.log('診断のみ：ファイルは作成・変更していません。');
  console.log('反映時はLaunch/Studioを終了し、現行UserDataをバックアップして差し替えてください。state.iniのview_mode=expandedも確認してください。');
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {run(...process.argv.slice(2));} catch(e) {console.error(`移行中止: ${e.message}`);process.exitCode=1;}
}
