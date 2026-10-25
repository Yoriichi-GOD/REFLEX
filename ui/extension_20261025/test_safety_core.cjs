const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const core = require(path.resolve(__dirname, '../..', 'frontend/safety.js'));

test('calibration rejects mirrored, intersecting, tiny and nonfinite panels', () => {
  assert.deepEqual(core.validateQuad([[0,0],[1,0],[1,1],[0,1]]), [[0,0],[1,0],[1,1],[0,1]]);
  for (const q of [[[0,0],[0,1],[1,1],[1,0]], [[0,0],[1,1],[1,0],[0,1]], [[0,0],[.1,0],[.1,.1],[0,.1]], [[0,0],[1,0],[NaN,1],[0,1]]]) assert.throws(() => core.validateQuad(q));
});
test('upload bounds depend on actual MIME and bytes, not a misleading name', () => {
  assert.equal(core.validateFile({name:'defect.exe',size:20,type:'image/png'}, 'STILL_IMAGE'), true);
  for (const file of [{size:0,type:'video/mp4'}, {size:50*1024*1024+1,type:'video/mp4'}, {size:5,type:'text/html'}]) assert.throws(() => core.validateFile(file,'STREAM_REPLAY'));
  assert.throws(() => core.validateFile({size:12*1024*1024+1,type:'image/png'},'STILL_IMAGE'));
});
test('capability URLs reject cross-origin, cross-session, traversal and URL tokens', () => {
  const origin='http://127.0.0.1:42137';
  assert.equal(core.protectedURL('/api/safety/sessions/one/media','one',origin), origin+'/api/safety/sessions/one/media');
  for (const url of ['https://elsewhere.test/api/safety/sessions/one/media','/api/safety/sessions/two/media','/api/safety/sessions/one/../two/media','//elsewhere.test/x','/api/safety/sessions/one/media?token=secret','/api/safety/sessions/one-more/media']) assert.throws(()=>core.protectedURL(url,'one',origin));
});
test('protected requests carry capability in header and refuse redirects', async () => {
  let observed;
  const result=await core.authorized('/api/safety/sessions/one/media',{id:'one',access_token:'test-only-key'}, {}, async (url,options)=>{observed={url,options};return new Response('media')},'http://127.0.0.1:42137');
  assert.equal(await result.text(),'media');
  assert.equal(observed.options.headers.get('Authorization'),'Bearer test-only-key');
  assert.equal(observed.options.redirect,'error');
  assert(!observed.url.includes('test-only-key'));
});
test('missing capability cannot reach the network', async () => {
  let called=false;
  await assert.rejects(core.authorized('/api/safety/sessions/one', {id:'one'}, {},async()=>{called=true},'http://127.0.0.1:42137'));
  assert.equal(called,false);
});
test('server error messages redact the current capability', async () => {
  await assert.rejects(core.authorized('/api/safety/sessions/one',{id:'one',access_token:'test-only-key'}, {},async()=>Response.json({detail:'bad test-only-key'},{status:403}),'http://127.0.0.1:42137'), error=>!error.message.includes('test-only-key')&&error.message.includes('redacted'));
});
const run = overrides => ({id:'a',state:'completed',policy:'single',source_mode:'STREAM_REPLAY',media:{sha256:'media-hash'},recipe_state:{recipe_sha256:'recipe-hash'},calibration_quad:[[0,0],[1,0],[1,1],[0,1]],start_state:'unknown',final_checkpoint:false,...overrides});
test('saved comparison accepts actual matched policy records', () => {assert.equal(core.compareRuns(run(),run({id:'b',policy:'agent'})),true)});
test('comparison rejects same run/policy, unfinished or missing proof', () => {
  for(const other of [run(),run({id:'b'}),run({id:'b',policy:'agent',state:'running'}),run({id:'b',policy:'agent',media:{}})]) assert.throws(()=>core.compareRuns(run(),other));
});
test('comparison rejects changes to media, recipe, panel, start state or checkpoint', () => {
  for(const changed of [{media:{sha256:'other'}},{recipe_state:{recipe_sha256:'other'}},{calibration_quad:[[0,0],[.9,0],[1,1],[0,1]]},{start_state:'empty_observed'},{final_checkpoint:true}]) assert.throws(()=>core.compareRuns(run(),run({id:'b',policy:'agent',...changed})));
});
test('clock distinguishes absent timestamp from observed zero', () => {assert.equal(core.time(null),'—');assert.equal(core.time(0),'0:00.000');assert.equal(core.time(125123),'2:05.123')});
test('camera cleanup stops every track and removes disconnect callbacks', () => {
  const stopped=[];const tracks=[0,1].map(id=>({onended(){throw Error('should not run')},stop(){assert.equal(this.onended,null);stopped.push(id)}}));
  core.stopStream({getTracks:()=>tracks});assert.deepEqual(stopped,[0,1]);core.stopStream(null);
});
