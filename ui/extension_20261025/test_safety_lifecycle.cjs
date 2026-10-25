/* DOM/HTTP substitutes exercise UI orchestration. These are not browser or CV tests. */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.listeners={};this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.className='';this.firstChild={textContent:''};this.classList={toggle(){},add(){}};this.duration=1;this.videoWidth=640;this.videoHeight=480;this.readyState=3;}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn)}
  async emit(name,event={}){for(const fn of this.listeners[name]||[])await fn(event)}
  append(...children){this.children.push(...children)}
  replaceChildren(...children){this.children=children;this.textContent=children.filter(c=>typeof c==='string').join('')}
  add(child){this.children.push(child)}
  setAttribute(key,val){this[key]=val}
  getAttribute(key){return this[key]??null}
  removeAttribute(key){delete this[key]}
  querySelectorAll(selector){return selector==='input'?(this.inputs||[]):selector==='button'?(this.buttons||[]):[]}
  pause(){} load(){} async play(){} remove(){} click(){}
}
async function setup({denyCamera=false,provideCamera=false}={}){
  const elements=new Map();for(const id of fs.readFileSync(path.join(root,'frontend/safety.html'),'utf8').matchAll(/id="([^"]+)"/g))elements.set('#'+id[1],new Element());
  const get=id=>elements.get(id), body=new Element();
  get('#ss-corners').inputs=[0,0,1,0,1,1,0,1].map(v=>Object.assign(new Element('input'),{value:String(v)}));
  get('#ss-review-form').buttons=[new Element('button'),new Element('button')];
  for(const id of ['#ss-consent','#ss-alignment'])get(id).checked=true;
  get('#ss-source').value='STILL_IMAGE';get('#ss-policy').value='agent';get('#ss-recipe').value='demo_panel_v1';
  const document={body,querySelector:s=>{assert(elements.has(s),s);return get(s)},createElement:tag=>{
    const e=new Element(tag);if(tag==='canvas'){e.getContext=()=>({drawImage(){}});e.toBlob=fn=>fn(new Blob([new Uint8Array([4,5,6])],{type:'image/jpeg'}))}return e;
  }};
  const recipe={recipe_id:'demo_panel_v1',name:'Test contract recipe',version:'1',scope:'software-test only',steps:[],slots:{}};
  const requests=[],saved=new Map(),timers=new Map();let timer=0,run;
  const fetch=async(url,options={})=>{
    const pathname=new URL(url,'http://127.0.0.1:42137').pathname;requests.push({path:pathname,options});
    if(pathname.endsWith('/recipes'))return Response.json({recipes:[recipe]});
    if(pathname.endsWith('/fixtures'))return Response.json({fixtures:[]});
    if(pathname==='/api/safety/sessions'){
      run={...JSON.parse(options.body),id:'a'.repeat(32),access_token:'test-only-key',state:'waiting_for_input',recipe,media:null,events:[],agent_trace:[],observations:[],acknowledgements:[],decision:{status:'HOLD_FOR_REVIEW',reason_codes:['NO_INPUT']},progress:{analyzed_frames:0,fraction:null}};
      return Response.json(run,{status:201});
    }
    assert.equal(options.headers.get('Authorization'),'Bearer test-only-key');
    if(pathname.endsWith('/frames')){assert(options.body instanceof FormData);run={...run,access_token:undefined,decision:{status:'HOLD_FOR_REVIEW',reason_codes:['PARTIAL_OBSERVATION']},progress:{analyzed_frames:1,fraction:null}};return Response.json(run)}
    if(pathname.endsWith('/finish')){run={...run,state:'completed'};return Response.json(run)}
    if(pathname.endsWith('/cancel')){run={...run,state:'cancelled'};return Response.json(run)}
    return Response.json(run);
  };
  const listeners={},tracks=[{stopped:false,onended:null,stop(){this.stopped=true}}];
  const context={document,fetch,Headers,Response,FormData,File,Blob,AbortController,URL,Option:function(label,value){return Object.assign(new Element('option'),{textContent:label,value})},console,performance,
    navigator:{mediaDevices:{getUserMedia:async constraints=>{assert.equal(constraints.audio,false);if(denyCamera){const e=new Error('denied');e.name='NotAllowedError';throw e}if(provideCamera)return{getTracks:()=>tracks,getVideoTracks:()=>tracks};throw Error('No camera supplied in this software test')}}},
    sessionStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)},localStorage:{getItem:()=>null},createImageBitmap:async()=>({width:640,height:480,close(){}}),
    setTimeout:(fn,ms)=>{timers.set(++timer,{fn,ms});return timer},clearTimeout:id=>timers.delete(id),window:{addEventListener:(name,fn)=>{listeners[name]=fn}},location:{origin:'http://127.0.0.1:42137'}};
  vm.runInNewContext(fs.readFileSync(path.join(root,'frontend/safety.js'),'utf8'),context);
  await flush();return {get,requests,saved,run:()=>run,listeners,timers,tracks};
}
async function flush(){for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve))}
test('still upload creates capability, submits actual bytes and finalizes before rendering returned disposition',async()=>{
  const h=await setup();assert.equal(h.get('#ss-runtime').textContent,'Safety service connected');
  const file=new File([new Uint8Array([1,2,3])],'arbitrary-label.png',{type:'image/png'});
  await h.get('#ss-file').emit('change',{target:{files:[file]}});
  await h.get('#ss-form').emit('submit',{preventDefault(){}});await flush();
  const calls=h.requests.map(r=>r.path);
  assert(calls.indexOf('/api/safety/sessions')<calls.indexOf('/api/safety/sessions/'+'a'.repeat(32)+'/frames'));
  assert(calls.some(p=>p.endsWith('/finish')));
  const form=h.requests.find(r=>r.path.endsWith('/frames')).options.body;assert.deepEqual([...new Uint8Array(await form.get('file').arrayBuffer())],[1,2,3]);
  assert.equal(h.get('#ss-decision').textContent,'HOLD FOR REVIEW');assert.equal(h.get('#ss-reasons').textContent,'PARTIAL OBSERVATION');
  assert.equal(h.get('#ss-session-state').textContent,'COMPLETED');assert.equal(h.get('#ss-progress').hidden,true);
  assert.equal(h.get('#ss-show-video').disabled,true,'A still must not be offered as a video');
  const stored=JSON.parse([...h.saved.values()][0]);assert.equal(stored[0].access_token,'test-only-key');
  assert(!h.get('#ss-status').textContent.includes('test-only-key'));
  h.listeners.pagehide();assert.equal(h.timers.size,0);
});
test('denied camera offers upload fallback and records cancellation without claiming active capture',async()=>{
  const h=await setup({denyCamera:true});h.get('#ss-source').value='LIVE_CAMERA';
  await h.get('#ss-source').emit('change');await h.get('#ss-form').emit('submit',{preventDefault(){}});await flush();
  assert.match(h.get('#ss-camera-error').textContent,/permission denied.*Uploaded video/i);
  assert.equal(h.get('#ss-camera-error').hidden,false);assert.equal(h.run().state,'cancelled');
  assert(!h.requests.some(r=>r.path.endsWith('/frames')));assert.equal(h.get('#ss-stop-camera').disabled,true);
});
test('camera navigation teardown stops the real supplied track handle and cancels future captures',async()=>{
  const h=await setup({provideCamera:true});h.get('#ss-source').value='LIVE_CAMERA';
  await h.get('#ss-source').emit('change');await h.get('#ss-form').emit('submit',{preventDefault(){}});await flush();
  assert(h.requests.some(r=>r.path.endsWith('/frames')));assert.equal(h.tracks[0].stopped,false);
  h.listeners.pagehide();assert.equal(h.tracks[0].stopped,true);assert.equal(h.tracks[0].onended,null);assert.equal(h.timers.size,0);assert.equal(h.get('#ss-video').srcObject,null);
});
