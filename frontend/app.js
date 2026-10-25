
    const $ = (s) => document.querySelector(s);
    let current = null, cases = [], profilesList = [], activeCase = null, layer = 'compare', currentComparison = null, zoomLevel = 1;
    let busy = false, panEnabled = false, panX = 0, panY = 0, dragOrigin = null;
    const statusBox = $('#status');
    const emptyViewport = $('#canvas').innerHTML;
    function esc(s){return String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
    function status(message,error=false){statusBox.textContent=message;statusBox.className='statusline show'+(error?' error':'');}
    function clearStatus(){statusBox.className='statusline';}
    async function api(url,options){const r=await fetch(url,options);if(!r.ok){let detail;try{detail=(await r.json()).detail}catch{detail={message:r.statusText}};throw new Error(detail?.message||JSON.stringify(detail));}return r.json();}
    async function boot(){
      try{
        const [health,profileData,caseData,history,evaluation]=await Promise.all([api('/api/health'),api('/api/profiles'),api('/api/demo-cases'),api('/api/inspections'),api('/api/evaluations/latest')]);
        const remote=health.runtime==='aws';$('#runtime').textContent=remote?'Vision service · AWS':'Vision service · local';$('#runtime-notice').hidden=!remote;$('#studio-mode').textContent=`Inspection studio / ${remote?'AWS demo':'local profile'}`;$('#footer-storage').textContent=remote?'AWS demo · records and generated images expire after 24 hours · no automatic training from reviewer feedback':'Images remain in local development storage · no automatic training from reviewer feedback';$('#cv-version').textContent='OpenCV '+health.opencv_version;$('#footer-build').textContent=`OpenCV ${health.opencv_version} · build ${health.build_revision} · ${health.renderer}`;
        profilesList=profileData.profiles;const p=profilesList.find(p=>p.default)||profilesList[0];$('#category').innerHTML=profilesList.map(item=>`<option value="${esc(item.category)}" ${item.category===p.category?'selected':''}>${esc(item.display_name)}</option>`).join('');applyProfile(p);
        $('#runtime-dot').classList.add('online');
        $('#upload-privacy').textContent=remote?'Licensed examples · live analysis on AWS in Sydney.':'Processed by this local service.';
        $('#settings-runtime').textContent=`OpenCV ${health.opencv_version} · ${remote?'AWS demo, Sydney':'local service'}`;
        $('#settings-profile').textContent=p.display_name;
        $('#settings-storage').textContent=remote?'AWS task-local storage · expires after 24 hours.':'Local service storage · 30-day default retention.';
        cases=caseData.cases;renderCases();renderHistory(history.inspections);renderEvaluation(evaluation);
      }catch(e){$('#runtime').textContent='Vision service unavailable';$('#runtime-dot').classList.add('offline');$('#cases').innerHTML='<span class="tiny">Capture library unavailable. Reload when the service is ready.</span>';status('Service is not ready: '+e.message,true);}
    }
    function applyProfile(p){$('#category').value=p.category;$('#settings-profile').textContent=p.display_name;$('#profile-name').textContent=p.display_name;$('#model-mode').textContent=p.synthetic?'Synthetic reference':'Normal-patch model';$('#score-note').textContent=`${p.training_count} normal train · ${p.calibration_count} calibration images · ${p.data_source||'synthetic profile'}`;$('#demo-heading').hidden=false;$('#demo-title').textContent=p.synthetic?'Synthetic examples':'Real image examples';$('#viewer-subtitle').textContent='Choose an example to analyze live';$('#evaluation-heading').textContent=p.synthetic?'Evaluation · synthetic holdout':'Evaluation · real benchmark';$('#profile-scope').textContent=p.synthetic?'The fitted profile and its holdout evaluation are synthetic.':'Real VisA images, Amazon Science, CC BY 4.0. Examples are curated; the benchmark includes missed defects. The official test split was reused during development.';$('#profile-description').textContent=p.synthetic?'OpenCV 5 synthetic regression examples and bounded review actions.':'Real photographs, live OpenCV 5 analysis, and an original / heatmap / overlay comparison.';}
    async function changeProfile(){
      if(busy)return;setBusy(true);
      try{
        const category=$('#category').value,p=profilesList.find(p=>p.category===category);
        const [demo,evaluation]=await Promise.all([api('/api/demo-cases?category='+encodeURIComponent(category)),api('/api/evaluations/latest?category='+encodeURIComponent(category))]);
        current=null;activeCase=null;currentComparison=null;panX=0;panY=0;cases=demo.cases;applyProfile(p);renderCases();renderEvaluation(evaluation);
        $('#canvas').classList.remove('compare-view');$('#canvas').innerHTML=emptyViewport;
        $('#decision').textContent='Awaiting inspection';$('#decision-text').textContent='Choose an example to compute new evidence.';$('#result-pill').className='result-pill';
        for(const id of ['score','threshold','image-hash','synthetic-label','focus-value','clipping-value'])$('#'+id).textContent='—';
        $('#score-fill').style.width='0';$('#quality-state').textContent='Awaiting image';$('#quality-flags').innerHTML='';$('#trace').innerHTML='';$('#trace-count').textContent='0 steps';$('#image-dimensions').textContent='No image loaded';
        $('#export-json').disabled=true;$('#export-html').disabled=true;$('#roi-layer').disabled=true;updateReferenceControls(false);
        $('#review-actions').hidden=true;$('#review-note-box').hidden=true;$('#retake-box').hidden=true;document.querySelectorAll('[data-zoom],#fit-view,#pan-mode').forEach(b=>b.disabled=true);
        await loadHistory();clearStatus();
      }catch(e){status('Could not load profile: '+e.message,true);}finally{setBusy(false);}
    }
    function renderCases(){const host=$('#cases');const real=cases.some(c=>c.synthetic===false);$('#case-count').textContent=`${cases.length} ${real?'real photos':'seeded'}`;host.innerHTML=cases.map(c=>`<button class="case ${activeCase===c.id?'active':''}" data-case="${esc(c.id)}" aria-pressed="${activeCase===c.id}" ${busy?'disabled':''}><img src="${esc(c.image_url)}" alt="${esc(c.title)}" loading="lazy"><span><strong>${esc(c.title)}</strong><span>${esc(c.description)}</span><span class="tag">${c.synthetic===false?'VisA · CC BY 4.0':'Synthetic fixture'}</span></span></button>`).join('');host.querySelectorAll('[data-case]').forEach(b=>b.addEventListener('click',()=>runCase(b.dataset.case)));$('#demo-credit').hidden=!real;}
    function renderHistory(items=[]){items=items.filter(x=>x.class_name===$('#category').value);const host=$('#history');if(!items.length){host.innerHTML='<span class="tiny">No inspections yet. Start with a capture above.</span>';return;}host.innerHTML=items.map(x=>`<button class="case" data-history="${esc(x.id)}" ${busy?'disabled':''}><span class="history-symbol ${x.decision==='PASS'?'pass':x.decision==='DEFECT_FOUND'?'defect':''}" aria-hidden="true">${x.decision==='PASS'?'✓':x.decision==='DEFECT_FOUND'?'!':'?'}</span><span><strong>${esc(x.decision.replaceAll('_',' '))}</strong><span>${new Date(x.created_at).toLocaleString()}</span><span class="tag">Score ${Number(x.score).toFixed(3)}</span></span></button>`).join('');host.querySelectorAll('[data-history]').forEach(b=>b.addEventListener('click',async()=>{if(busy)return;setBusy(true);try{clearStatus();show(await api('/api/inspections/'+b.dataset.history));}catch(e){status(e.message,true)}finally{setBusy(false)}}));}
    async function loadHistory(){try{renderHistory((await api('/api/inspections')).inspections)}catch(e){status(e.message,true)}}
    async function runCase(id){if(busy)return;const c=cases.find(x=>x.id===id);if(!c)return;activeCase=id;renderCases();try{const r=await fetch(c.image_url);if(!r.ok)throw new Error('Demo image could not be loaded.');const blob=await r.blob();const file=new File([blob],c.image_url.split('/').pop(),{type:blob.type||'application/octet-stream'});await inspectFile(file);}catch(e){status('Could not inspect the demo image: '+e.message,true)}}
    async function inspectFile(file){if(busy||!file)return;clearStatus();const form=new FormData();form.append('file',file,file.name);form.append('category',$('#category').value);setBusy(true);$('#decision').textContent='Inspecting capture';$('#decision-text').textContent='Measuring source pixels and evaluating the next action.';$('#result-pill').className='result-pill processing';status('Decoding source pixels and running OpenCV 5…');try{const result=await api('/api/inspections',{method:'POST',body:form});show(result);status('Inspection complete · output and trace persisted.');await loadHistory();}catch(e){if(current)show(current);else{$('#decision').textContent='Inspection failed';$('#decision-text').textContent='No result was produced. Check the image and try again.';$('#result-pill').className='result-pill error';}status('Inspection failed: '+e.message,true);}finally{setBusy(false);}}
    function show(r){current=r;currentComparison=null;layer='compare';updateReferenceControls(false);setZoom(1);activeCase=cases.find(c=>c.sha256===r.image_sha256)?.id||null;renderCases();if(layer==='roi'&&!r.assets.roi_url)layer='overlay';$('#roi-layer').disabled=!r.assets.roi_url;$('#viewer-subtitle').textContent=`${r.class_name} · ${r.runtime_ms.toFixed(1)} ms`;$('#image-dimensions').textContent=`${r.source_dimensions.width} × ${r.source_dimensions.height} px · source resolution retained`;$('#image-hash').textContent='SHA256 '+r.image_sha256.slice(0,16)+'…';$('#image-hash').title=r.image_sha256;$('#synthetic-label').textContent=r.synthetic?'Seeded synthetic fixture':r.demo_attribution?'Real VisA photograph · CC BY 4.0':'User-provided image';$('#model-mode').textContent=r.model_mode==='opencv_dnn_patch_memory'?'Normal-patch model':r.model_mode;
      $('#decision').textContent=r.decision.replace('_',' ');$('#decision-text').textContent=r.decision_text;$('#result-pill').className='result-pill '+(r.decision==='PASS'?'pass':r.decision==='DEFECT_FOUND'?'defect':'review');$('#score').textContent=Number(r.score).toFixed(3);$('#threshold').textContent=Number(r.threshold).toFixed(3);$('#score-note').textContent=r.pass_threshold!=null?`PASS ≤ ${Number(r.pass_threshold).toFixed(3)} · review band up to ${Number(r.threshold).toFixed(3)} · normal-calibrated boundaries`:'Calibrated on normal-only images.';const ratio=Number(r.score)/(Number(r.threshold)||1);$('#score-fill').style.width=Math.max(2,Math.min(100,ratio*70))+'%';$('#threshold-mark').style.left='70%';$('#score-fill').style.background=r.decision==='DEFECT_FOUND'?'var(--red)':r.decision==='NEEDS_REVIEW'?'var(--amber)':'var(--cyan)';
      $('#focus-value').textContent=Number(r.quality.focus_laplacian_variance).toFixed(2)+' Lap var';$('#focus-meter').style.width=Math.min(100,Number(r.quality.focus_laplacian_variance)/80*100)+'%';$('#clipping-value').textContent=(Number(r.quality.clipped_pixel_fraction)*100).toFixed(2)+'%';$('#clipping-meter').style.width=Math.min(100,Number(r.quality.clipped_pixel_fraction)*300)+'%';$('#quality-state').textContent=r.quality.flags.length?'Needs attention':'Within heuristics';$('#quality-state').className=r.quality.flags.length?'warn':'ok';const warningFlags=r.quality.suitability?.flags||[];$('#quality-flags').innerHTML=r.quality.flags.map(f=>`<span class="flag">${esc(f)}</span>`).join('')+(warningFlags.length?warningFlags.map(f=>`<span class="flag">Advisory: ${esc(f)}</span>`).join(''):'')||'<span class="tiny">No configured quality flags</span>';
      renderTrace(r.agent_trace);panX=0;panY=0;setLayer(layer);$('#export-json').disabled=false;$('#export-html').disabled=false;$('#review-actions').hidden=false;$('#review-note-box').hidden=false;$('#retake-box').hidden=r.needs_action?.type!=='new_capture';$('#review-note').value='';$('#viewer-state').textContent='EVIDENCE LOADED';$('#viewer-state').classList.add('ready');document.querySelectorAll('[data-zoom],#fit-view,#pan-mode').forEach(b=>b.disabled=false);if(r.reviewer)status(`Reviewer action saved: ${r.reviewer.decision} · model result remains ${r.decision}.`);
    }
    function setLayer(name){
      if(name==='roi'&&!current?.assets.roi_url)return;
      if((name==='aligned'||name==='difference')&&!currentComparison?.accepted)return;
      layer=name;
      document.querySelectorAll('[data-layer]').forEach(b=>{b.classList.toggle('active',b.dataset.layer===name);b.setAttribute('aria-pressed',String(b.dataset.layer===name));});
      const host=$('#canvas');
      if(!current)return;
      host.classList.toggle('compare-view',name==='compare');
      if(name==='compare'){
        const panels=[['original_url','Original photograph'],['heatmap_url','Anomaly heatmap'],['overlay_url','Model overlay']];
        host.innerHTML='<div class="evidence-comparison">'+panels.map(([key,title])=>`<figure><figcaption>${esc(title)}</figcaption><div class="image-wrap"><img src="${esc(current.assets[key])}" alt="${esc(title)} for inspection ${esc(current.id)}" draggable="false"></div></figure>`).join('')+'</div>';
        host.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>status('An evidence image could not be loaded. Check retention or reopen the inspection.',true)));
        setZoom(zoomLevel);return;
      }
      const choices={
        overlay:{key:'overlay_url',label:'Model overlay',regions:true},
        original:{key:'original_url',label:'Input image',regions:true},
        heatmap:{key:'heatmap_url',label:'Score heatmap',regions:true},
        roi:{key:'roi_url',label:'Native source-pixel crop',regions:false},
        aligned:{url:currentComparison?.aligned_url,label:'Aligned reference comparison',regions:false},
        difference:{url:currentComparison?.difference_url,label:'Reference difference map',regions:false},
      };
      const choice=choices[name]||choices.overlay;
      const imageUrl=choice.url||current.assets[choice.key];
      const w=current.source_dimensions.width,h=current.source_dimensions.height;
      const boxes=!choice.regions?'':(current.regions||[]).map((r,i)=>{const [x1,y1,x2,y2]=r.bbox_xyxy;return `<rect data-region="${i}" tabindex="0" role="button" aria-label="Select anomaly region ${i+1}" x="${x1}" y="${y1}" width="${x2-x1}" height="${y2-y1}"><title>Region ${i+1}: score ${Number(r.max_score).toFixed(3)}</title></rect>`}).join('');
      host.classList.add('loaded');
      host.innerHTML=`<span class="badge">${esc(choice.label)}</span><div class="image-wrap"><img src="${esc(imageUrl)}" alt="${esc(choice.label)} for inspection ${esc(current.id)}" draggable="false"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Localized anomaly regions">${boxes}</svg></div>`;
      host.querySelector('img').addEventListener('error',()=>status('This evidence image could not be loaded. Reopen the inspection or check whether its retention period expired.',true));
      if(name==='roi'||name==='aligned'||name==='difference'){panX=0;panY=0;}
      setZoom(zoomLevel);
      host.querySelectorAll('[data-region]').forEach(box=>{const select=()=>{const r=current.regions[Number(box.dataset.region)];status(`Selected source region ${r.bbox_xyxy.join(', ')} · native bbox · peak anomaly score ${Number(r.max_score).toFixed(3)}.`)};box.addEventListener('click',select);box.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});});
    }
    function setZoom(value){
      zoomLevel=Math.max(0.5,Math.min(3,value));
      $('#zoom-reset').textContent=`${Math.round(zoomLevel*100)}%`;
      document.querySelectorAll('#canvas .image-wrap').forEach(w=>w.style.transform=`translate(${panX}px,${panY}px) scale(${zoomLevel})`);
    }
    function setBusy(value){
      busy=value;document.body.classList.toggle('busy',value);$('#evidence-viewer').setAttribute('aria-busy',String(value));
      document.querySelectorAll('[data-case],[data-history],[data-review],#browse,#category,#retake-button,#refresh-history').forEach(b=>b.disabled=value);
      $('#browse').innerHTML=value?'<i class="spinner" aria-hidden="true"></i>Inspecting…':'Choose image <svg><use href="#i-arrow"/></svg>';
      $('#compare-reference').disabled=value||!current;
      $('#viewer-state').textContent=value?'PROCESSING':current?'EVIDENCE LOADED':'STANDBY';
    }
    function updateReferenceControls(hasComparison,hint=''){
      $('#compare-reference').disabled=!current;
      $('#aligned-layer').disabled=!hasComparison;
      $('#difference-layer').disabled=!hasComparison;
      $('#compare-hint').textContent=hint||(hasComparison?'Reference aligned. Select a comparison layer.':current?'Choose a reference image; unstable alignment is refused.':'Run an inspection before comparing a reference.');
    }
    async function compareReference(referenceFile){
      if(!current||!referenceFile||busy)return;
      const button=$('#compare-reference');
      setBusy(true);
      status('Registering the reference with OpenCV ECC…');
      try{
        const source=await fetch(current.assets.original_url);
        if(!source.ok)throw new Error('The current inspection image could not be loaded.');
        const candidateBlob=await source.blob();
        const candidate=new File([candidateBlob],`inspection-${current.id}.png`,{type:'image/png'});
        const form=new FormData();
        form.append('reference',referenceFile,referenceFile.name);
        form.append('candidate',candidate,candidate.name);
        const result=await api('/api/align',{method:'POST',body:form});
        if(!result.accepted){
          currentComparison=null;
          updateReferenceControls(false,`Alignment refused: ${result.alignment.reason||'unstable transform'}. Use a more consistent reference.`);
          status('Reference comparison was refused because registration was not reliable.',true);
          return;
        }
        currentComparison=result;
        const correlation=Number(result.alignment.correlation).toFixed(3);
        const delta=Number(result.comparison.p95_lab_delta).toFixed(2);
        updateReferenceControls(true,`Aligned · ECC ${correlation} · p95 Lab delta ${delta}`);
        setLayer('difference');
        status('Reference aligned. The difference map is computed from the registered pair.');
      }catch(error){
        updateReferenceControls(false,'Reference comparison failed; the current inspection result is unchanged.');
        status(`Reference comparison failed: ${error.message}`,true);
      }finally{
        setBusy(false);
      }
    }
    function renderTrace(entries=[]){$('#trace-count').textContent=`${entries.length} ${entries.length===1?'step':'steps'}`;const names={inspect_full:'Full image inspection',inspect_crop:'Inspect native-resolution crop',request_new_capture:'Request another capture',request_human_review:'Request human review'};$('#trace').innerHTML=entries.map(t=>`<div class="trace-item"><strong>${esc(names[t.selected_tool]||t.selected_tool)} <span class="tiny">· ${esc(t.state_after)}</span></strong><p>${esc(t.decision_reason_code)}${t.elapsed_ms?` · ${Number(t.elapsed_ms).toFixed(2)} ms`:''}</p><details><summary>Measured input and output</summary><pre>${esc(JSON.stringify({observation:t.observation,input:t.tool_input,result:t.tool_result||{evidence_id:t.tool_result_id},created_at:t.created_at},null,2))}</pre></details></div>`).join('')||'<span class="tiny">No agent trace.</span>';}
    async function review(decision){if(!current||busy)return;setBusy(true);try{const item=await api(`/api/inspections/${current.id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,note:$('#review-note').value||null})});current.reviewer=item.reviewer;status(`Reviewer action saved: ${decision}. The computer-vision result remains ${current.decision}.`);await loadHistory();}catch(e){status('Review was not saved: '+e.message,true)}finally{setBusy(false)}}
    async function submitRetake(file){if(!current||!file||busy)return;const parent=current.id;const form=new FormData();form.append('file',file,file.name);setBusy(true);try{status('Running a new inspection on the supplied capture…');const r=await api(`/api/inspections/${parent}/continue`,{method:'POST',body:form});show(r);status('New capture inspected and linked to the prior request.');await loadHistory();}catch(e){status('New capture was not accepted: '+e.message,true)}finally{setBusy(false)}}
    function renderEvaluation(e){const host=$('#evaluation');if(e.status==='not_evaluated'){host.innerHTML=`<p>${esc(e.message)}</p>`;return;}$('#eval-status').textContent=`${esc(e.dataset)} · ${esc(e.run_id||'run')}`;const m=e.metrics||{};host.innerHTML=`<div class="eval-line"><span class="eval-stat"><strong>${esc(m.sample_count??'—')}</strong>images</span><span class="eval-stat"><strong>${esc(m.image_auroc??'Not measured')}</strong>image AUROC</span><span class="eval-stat"><strong>${esc(m.f1_at_threshold??'Not measured')}</strong>F1 at frozen threshold</span><span class="eval-stat"><strong>${esc(m.pixel_iou??'Not measured')}</strong>pixel IoU</span><span class="eval-stat"><strong>${esc(e.synthetic===true?'Synthetic':'Real')}</strong>dataset type</span></div><p>${esc(e.interpretation||'See evaluation artifact for method and failure cases.')}</p>`;}
    $('#browse').addEventListener('click',()=>$('#file-input').click());$('#file-input').addEventListener('change',e=>{if(e.target.files[0])inspectFile(e.target.files[0]);e.target.value=''});$('#drop-zone').addEventListener('dragover',e=>{e.preventDefault();e.currentTarget.style.borderColor='var(--cyan)'});$('#drop-zone').addEventListener('dragleave',e=>e.currentTarget.style.borderColor='');$('#drop-zone').addEventListener('drop',e=>{e.preventDefault();e.currentTarget.style.borderColor='';if(e.dataTransfer.files[0])inspectFile(e.dataTransfer.files[0])});document.querySelectorAll('[data-layer]').forEach(b=>b.addEventListener('click',()=>setLayer(b.dataset.layer)));$('#refresh-history').addEventListener('click',loadHistory);$('#export-json').addEventListener('click',()=>current&&(location.href=`/api/inspections/${current.id}/export?format=json`));$('#export-html').addEventListener('click',()=>current&&(location.href=`/api/inspections/${current.id}/export?format=html`));$('#review-actions').addEventListener('click',e=>{if(e.target.dataset.review)review(e.target.dataset.review)});$('#retake-button').addEventListener('click',()=>$('#retake-input').click());$('#retake-input').addEventListener('change',e=>{if(e.target.files[0])submitRetake(e.target.files[0]);e.target.value=''});
    $('#category').addEventListener('change',changeProfile);
    $('#compare-reference').addEventListener('click',()=>$('#reference-input').click());
    $('#reference-input').addEventListener('change',e=>{if(e.target.files[0])compareReference(e.target.files[0]);e.target.value=''});
    document.querySelectorAll('[data-zoom]').forEach(button=>button.addEventListener('click',()=>{const step=button.dataset.zoom;if(step==='reset'){panX=0;panY=0;}setZoom(step==='reset'?1:zoomLevel+Number(step)*0.25);}));
    $('#fit-view').addEventListener('click',()=>{panX=0;panY=0;setZoom(1);});
    $('#pan-mode').addEventListener('click',()=>{panEnabled=!panEnabled;$('#pan-mode').setAttribute('aria-pressed',String(panEnabled));$('#pan-mode').classList.toggle('active',panEnabled);$('#canvas').classList.toggle('pan-enabled',panEnabled);});
    $('#canvas').addEventListener('pointerdown',e=>{if(!panEnabled||!current||e.button!==0)return;dragOrigin={pointerId:e.pointerId,x:e.clientX-panX,y:e.clientY-panY};$('#canvas').setPointerCapture(e.pointerId);$('#canvas').classList.add('panning');});
    $('#canvas').addEventListener('pointermove',e=>{if(!dragOrigin||dragOrigin.pointerId!==e.pointerId)return;const bounds=$('#canvas').getBoundingClientRect();panX=Math.max(-bounds.width,Math.min(bounds.width,e.clientX-dragOrigin.x));panY=Math.max(-bounds.height,Math.min(bounds.height,e.clientY-dragOrigin.y));setZoom(zoomLevel);});
    function stopPanning(){dragOrigin=null;$('#canvas').classList.remove('panning');}
    $('#canvas').addEventListener('pointerup',stopPanning);$('#canvas').addEventListener('pointercancel',stopPanning);$('#canvas').addEventListener('lostpointercapture',stopPanning);
    $('#canvas').addEventListener('keydown',e=>{if(!panEnabled||!current)return;const offsets={ArrowLeft:[20,0],ArrowRight:[-20,0],ArrowUp:[0,20],ArrowDown:[0,-20]};if(!offsets[e.key])return;e.preventDefault();panX+=offsets[e.key][0];panY+=offsets[e.key][1];setZoom(zoomLevel);});
    $('#canvas').tabIndex=0;$('#canvas').setAttribute('aria-label','Evidence viewport. Enable pan and use arrow keys to move the image.');
    $('#fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('#evidence-viewer').requestFullscreen();}catch{status('Fullscreen is unavailable in this browser. The evidence viewer remains usable.',true);}});
    document.addEventListener('fullscreenchange',()=>{$('#fullscreen').setAttribute('aria-label',document.fullscreenElement?'Exit fullscreen viewer':'Enter fullscreen viewer');});
    const settings=$('#settings-dialog');
    $('#open-settings').addEventListener('click',()=>settings.showModal());
    $('#close-settings').addEventListener('click',()=>settings.close());$('#settings-done').addEventListener('click',()=>settings.close());
    settings.addEventListener('click',e=>{if(e.target!==settings)return;const b=settings.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)settings.close();});
    try{$('#reduce-motion').checked=localStorage.getItem('reflex-reduced-motion')==='true';}catch{/* Browser storage may be disabled. */}
    document.body.classList.toggle('reduced-motion',$('#reduce-motion').checked);
    $('#reduce-motion').addEventListener('change',e=>{document.body.classList.toggle('reduced-motion',e.target.checked);try{localStorage.setItem('reflex-reduced-motion',String(e.target.checked));}catch{/* Keep the preference for this page session. */}});
    function updateNavigation(){const target=location.hash||'#workspace';document.querySelectorAll('.navigation a').forEach(a=>{const active=a.getAttribute('href')===target;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}
    document.querySelectorAll('.navigation a').forEach(a=>a.addEventListener('click',()=>{const target=$(a.getAttribute('href'));if(target)target.focus({preventScroll:true});}));
    window.addEventListener('hashchange',updateNavigation);updateNavigation();
    boot();
  
