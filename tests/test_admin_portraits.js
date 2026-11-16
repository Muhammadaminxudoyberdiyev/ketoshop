// Admin «🧑‍🤝‍🧑 Mijozlar» (AI portreti): the real tab code from admin.html,
// run with only the network/DOM boundary replaced. Names are made up.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('webapp/admin.html','utf8');
const MARK='/* ===== mijozlar: AI portreti';
const section=MARK+html.split(MARK)[1].split('/* ===== blogerlar')[0];
const escSrc=/const esc=.*?;\r?\n/.exec(html)[0];

function node(){
  const cls=new Set();
  return {innerHTML:'',textContent:'',value:'',_h:{},
    classList:{add:c=>cls.add(c),remove:c=>cls.delete(c),contains:c=>cls.has(c),toggle:(c,on)=>on?cls.add(c):cls.delete(c)},
    addEventListener(type,fn){this._h[type]=fn;}};
}
const nodes={};
for(const id of ['#pmKpis','#pmGoals','#pmCount','#pmList','#pmPager','#pmSearch','#pmBody','#pmTitle','#pmSub','#pmModal'])nodes[id]=node();
const filterBtns=['all','portrait','no_portrait','orders'].map(v=>Object.assign(node(),{dataset:{v}}));

const LIST={
  stats:{talked:3,portraits:1,with_name:1,with_age:1,female:1,male:0,with_goals:1,opted_out:1,with_orders:1},
  goals:[{goal:'ozish',label:'ozish',n:1}],
  rows:[
    {user_id:5001,full_name:'Dilnoza <b>Test</b>',username:'dilnoza_t',opted_out:false,has_portrait:true,
     display_name:'Dilnoza',age:28,age_group:'25–34',gender:'f',gender_source:'name',gender_confidence:0.93,
     goals:['ozish'],goal_labels:['ozish'],first_ai_at:'2026-11-10T09:00:00',last_ai_at:'2026-11-16T08:30:00',
     conversations:3,messages:9,channels:['bot','site'],topics:[],orders:2,spent:350000,last_order_at:null},
    {user_id:5002,full_name:'Sardor Test',username:'',opted_out:true,has_portrait:false,display_name:null,age:null,
     gender:'unknown',goals:[],goal_labels:[],last_ai_at:'2026-11-15T10:00:00',conversations:1,orders:0,spent:0},
    {user_id:5003,full_name:'',username:'',opted_out:false,has_portrait:false,display_name:null,age:null,
     gender:'unknown',goals:[],goal_labels:[],last_ai_at:'2026-11-14T10:00:00',conversations:1,orders:0,spent:0},
  ],
  total:61,page:1,pages:3,per_page:30,filter:'all',q:'',
};
const CARD={...LIST.rows[0],language:'uz_cyr',joined_at:'2026-09-01T07:00:00',keto_balance:140,keto_lifetime:320,
  tg_link:'tg://user?id=5001',tme_link:'https://t.me/dilnoza_t',
  topics:[{key:'narx',title:'💰 Narx / mahsulot bormi',n:3}],
  notes:[{kind:'feedback',text:'Eritritol <yoqdi>',created_at:'2026-11-13T00:00:00'},
         {kind:'interest',text:'Bodom uni',created_at:'2026-11-10T00:00:00'}],
  recent_orders:[{id:100,created_at:'2026-11-15T10:00:00',status:'delivered',total:190000,delivery_method:'courier',
    items:[{name:'Bodom uni 500gr',quantity:2,unit:'dona',price:95000,gift:false},
           {name:'Eritritol 100gr',quantity:1,unit:'',price:0,gift:true}]}]};
// The server never sends notes for an opted-out customer; the page must not show them even if it did.
const GONE={...LIST.rows[1],tg_link:'tg://user?id=5002',tme_link:'',keto_balance:0,keto_lifetime:0,language:'ru',
  topics:[{key:'narx',title:'yashirin mavzu',n:1}],notes:[{kind:'note',text:'yashirin eslatma'}],recent_orders:[]};

const requests=[];
let hold=null;
const ctx=vm.createContext({console,Number,String,Math,Date,isNaN,Promise,URLSearchParams,setTimeout,clearTimeout,
  $:s=>nodes[s], $$:s=>s==='#pmFilter button'?filterBtns:[],
  toast(){},
  api:async path=>{
    requests.push(path);
    if(hold){const h=hold;hold=null;await h.wait;return h.body;}
    if(path==='/admin/api/portraits/5001')return CARD;
    if(path==='/admin/api/portraits/5002')return GONE;
    return JSON.parse(JSON.stringify(LIST));
  }});
ctx.window=ctx;
vm.runInContext(escSrc+section,ctx);

async function main(){
  await ctx.loadMijozlar();
  assert.equal(requests.at(-1),'/admin/api/portraits?q=&page=1&filter=all');
  const kpis=nodes['#pmKpis'].innerHTML;
  assert.match(kpis,/AI bilan gaplashgan<\/div><div class="val">3 ta/);
  assert.match(kpis,/👤 Ism<\/div><div class="val">1 · 33%/);
  assert.match(kpis,/🚻 Jins<\/div><div class="val">1 · 33%<\/div><div class="sub">👩 ayol 1 · 👨 erkak 0/);
  assert.match(kpis,/O'chirgan<\/div><div class="val">1 ta/);
  assert.match(nodes['#pmGoals'].innerHTML,/ozish · 1/);
  const list=nodes['#pmList'].innerHTML;
  assert.match(list,/data-uid="5001"/);
  assert.match(list,/<small>Dilnoza &lt;b&gt;Test&lt;\/b&gt; · @dilnoza_t<\/small>/, 'Telegram name is escaped');
  assert.match(list,/🎂 28 yosh/);
  assert.match(list,/<span class="pm-chip">ozish<\/span>/);
  assert.match(list,/class="pm-ava f" title="ayol \(ismdan taxmin, ishonch 93%\)">👩/);
  assert.match(list,/🛒 <b>2<\/b> · 350 000 so'm/);
  const gone=list.split('data-uid="5002"')[1].split('</button>')[0];
  assert.match(gone,/Ma'lumot o'chirilgan/);
  assert.match(gone,/🔐/);
  assert.doesNotMatch(gone,/pm-chip|yosh/);
  assert.match(list.split('data-uid="5003"')[1],/ID 5003[\s\S]*portret hali yo'q/);
  assert.match(nodes['#pmCount'].textContent,/61 ta mijoz · 1\/3-sahifa/);
  assert.match(nodes['#pmPager'].innerHTML,/data-page="0" disabled>← Oldingi/);
  assert.match(nodes['#pmPager'].innerHTML,/data-page="2">Keyingi/);
  assert.equal(nodes['#pmList'].classList.contains('busy'),false);

  // Filter, pager and search all go back to the server.
  filterBtns[1]._h.click();
  await new Promise(r=>setTimeout(r,0));
  assert.equal(requests.at(-1),'/admin/api/portraits?q=&page=1&filter=portrait');
  nodes['#pmPager']._h.click({target:{closest:()=>({dataset:{page:'2'},disabled:false})}});
  await new Promise(r=>setTimeout(r,0));
  assert.equal(requests.at(-1),'/admin/api/portraits?q=&page=2&filter=portrait');
  nodes['#pmSearch']._h.input({target:{value:'  @dil '}});
  nodes['#pmSearch']._h.input({target:{value:' dil '}});
  await new Promise(r=>setTimeout(r,350));
  assert.equal(requests.filter(p=>p.includes('q=')).at(-1),'/admin/api/portraits?q=dil&page=1&filter=portrait');
  assert.equal(requests.filter(p=>p.includes('dil')).length,1,'typing is debounced');

  // A slow older answer must not overwrite a newer one.
  let release;hold={wait:new Promise(r=>release=r),body:{...LIST,rows:[],total:0,pages:1}};
  const slow=ctx.loadMijozlar();
  await ctx.loadMijozlar();
  release();await slow;
  assert.match(nodes['#pmList'].innerHTML,/data-uid="5001"/);

  // Row → card.
  nodes['#pmList']._h.click({target:{closest:()=>({dataset:{uid:'5001'}})}});
  await new Promise(r=>setTimeout(r,0));
  assert.equal(requests.at(-1),'/admin/api/portraits/5001');
  assert.ok(nodes['#pmModal'].classList.contains('open'));
  assert.equal(nodes['#pmTitle'].textContent,'👩 Dilnoza');
  assert.equal(nodes['#pmSub'].textContent,'Telegram: Dilnoza <b>Test</b> · @dilnoza_t · ID 5001');
  const card=nodes['#pmBody'].innerHTML;
  assert.match(card,/href="tg:\/\/user\?id=5001"/);
  assert.match(card,/href="https:\/\/t\.me\/dilnoza_t"/);
  assert.match(card,/🧩 Portret/);
  assert.match(card,/28 <small>\(25–34\)<\/small>/);
  assert.match(card,/👩 ayol <small>\(ismdan taxmin, ishonch 93%\)<\/small>/);
  assert.match(card,/💰 Narx \/ mahsulot bormi · 3/);
  assert.match(card,/🤖 Bot, 🖥 Sayt/);
  assert.match(card,/140 <small>\(jami 320\)<\/small>/);
  assert.match(card,/Ўзбекча/);
  assert.match(card,/AI eslatmalari <small>\(2\)<\/small>/);
  assert.match(card,/💬 Fikr · [^<]*<\/span>Eritritol &lt;yoqdi&gt;/);
  assert.match(card,/#100/);
  assert.match(card,/✅ Yetkazildi/);
  assert.match(card,/Bodom uni 500gr ×2 dona, Eritritol 100gr ×1 🎁/);
  assert.match(card,/190 000 so'm/);

  await ctx.openPortrait(5002);
  const off=nodes['#pmBody'].innerHTML;
  assert.equal(nodes['#pmTitle'].textContent,'🔐 Sardor Test');
  assert.match(off,/Ma'lumot o'chirilgan/);
  assert.doesNotMatch(off,/🧩 Portret|AI eslatmalari <small>|pm-note|yashirin/);
  assert.doesNotMatch(off,/t\.me/);
  assert.match(off,/Buyurtma yo'q/);
  console.log('Admin Mijozlar: counters, escaped list, opted-out rows/cards, filter/search/pager, stale answers and the card passed');
}
main().catch(err=>{console.error(err);process.exitCode=1;});
