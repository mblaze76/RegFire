const form = document.querySelector('#event-form');
const field = name => form.elements.namedItem(name);
const feedback = document.querySelector('#feedback');
let initializing=true, opening=false;
function loading(text){document.body.classList.add('workspace-loading');document.getElementById('workspace-loading').textContent=text;}
function loaded(){document.body.classList.remove('workspace-loading');}
let events = [], selected = null, dirty = false, saving = false, activeView = 'event';
async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed. Please try again.');
  return data;
}
function message(text, error = false) { feedback.textContent = text; feedback.className = error ? 'error' : ''; }
function formatFields() {
  const online = field('format').value === 'online';
  document.querySelector('#physical').hidden = online;
  document.querySelector('#virtual').hidden = !online;
  field('url').disabled = !online;
}
const outlineState=new Map();
function renderList(){
 const list=document.getElementById('list');list.replaceChildren();document.getElementById('count').textContent=events.length;
 if(!events.length){const p=document.createElement('p');p.className='empty';p.textContent='No drafts yet. Your saved events will appear here.';list.append(p);}
 for(const event of events){
  const group=document.createElement('details');group.className='event-outline';group.open=outlineState.get(event.id)??event.id===selected;
  const summary=document.createElement('summary');summary.textContent=event.name;group.append(summary);const contents=document.createElement('div');contents.className='outline-pages';group.append(contents);list.append(group);
  function link(label,view,flow){const a=document.createElement('a');a.textContent=label;a.href='#event='+event.id+'&view='+view+(flow?'&flow='+flow.id:'');if(event.id===selected&&view===activeView&&(!flow||flow.id===window.RegistrationFlows?.current()?.id))a.setAttribute('aria-current','page');a.onclick=async e=>{if(activeView==='event'&&(dirty||window.EventFooterBuilder?.dirty || window.SessionsBuilder?.dirty || window.WelcomeBuilder?.dirty)){e.preventDefault();if(!await saveEventDraft()||!await window.WelcomeBuilder.save()||!await window.EventFooterBuilder.save())return;location.hash=a.hash;}};return a;}
  async function draw(){contents.replaceChildren(link('Event details','event'),link('Registration flows','flows'));try{const flows=event.id===selected?window.RegistrationFlows?.list()||[]:await api('/api/events/'+event.id+'/flows');if(!group.isConnected)return;for(const flow of flows){const branch=document.createElement('details'),key=event.id+':'+flow.id;branch.className='flow-outline';branch.open=outlineState.get(key)??(event.id===selected&&flow.id===window.RegistrationFlows?.current()?.id);branch.ontoggle=()=>outlineState.set(key,branch.open);const heading=document.createElement('summary');heading.textContent=flow.name;branch.append(heading);for(const [view,label] of [['setup','Website setup'],['registration',flow.kind==='attendee'?'Attendee details':'Registration details'],['demographics','Demographics'],['sessions','Sessions']])branch.append(link(label,view,flow));contents.append(branch);}}catch{const error=document.createElement('p');error.textContent='Could not load flows. Close and reopen this event to retry.';contents.append(error);}}
  group.ontoggle=()=>{outlineState.set(event.id,group.open);if(group.open)draw();};if(group.open)draw();
 }
}
window.refreshEventOutline=renderList;
async function openDraft(event = null) {
  if (opening || saving || window.RegistrationBuilder?.busy || window.DemographicsBuilder?.busy || window.MembershipBuilder?.busy || window.EventFooterBuilder?.busy || window.SessionsBuilder?.busy || window.WelcomeBuilder?.busy) return;
  if ((dirty || window.RegistrationBuilder?.dirty || window.DemographicsBuilder?.dirty || window.MembershipBuilder?.dirty || window.EventFooterBuilder?.dirty || window.SessionsBuilder?.dirty || window.WelcomeBuilder?.dirty) && !await confirmAction('Discard unsaved changes and continue?')) return;
  opening=true;loading(event?'Loading '+event.name+'…':'Opening new event…');
  window.RegistrationBuilder?.clear(); window.DemographicsBuilder?.clear(); window.MembershipBuilder?.clear(); window.WelcomeBuilder?.clear(); window.SessionsBuilder?.clear(); window.EventFooterBuilder?.clear();
  form.reset(); selected = event?.id || null;
  if (event) for (const [name, value] of Object.entries(event)) { const control = field(name); if (control) control.value = value; }
  else field('timezone').value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  for(const k of ['line1','line2','city','region','postal','country'])field('address_'+k).value=event?.address?.[k]||'';
  document.querySelector('#delete-event').hidden=!event;
  dirty = false; formatFields(); renderList();
  document.querySelector('#editor-title').textContent = event ? 'Edit event' : 'Create an event';
  document.querySelector('#save-state').textContent = event ? 'Saved draft' : 'New draft';
  message(event ? 'Last saved ' + new Date(event.updated).toLocaleString() : 'Only the event name is required.');
  try { await window.RegistrationFlows.load(event); } catch(error){opening=false;loading('Could not load this event. Reload to retry. Your saved data is unchanged.');return;}
  opening=false;loaded();
  if(!window.RegistrationFlows.current()&&activeView!=='flows')activeView='event';
  showView(event ? activeView : 'event');
}
form.addEventListener('input', () => { dirty = true; document.querySelector('#save-state').textContent = 'Unsaved changes'; message('Save your draft to keep these changes.'); });
form.addEventListener('change', formatFields);
document.querySelector('#new').onclick = () => {if(!initializing&&!opening)openDraft();};
window.addEventListener('beforeunload', event => { if (dirty || window.RegistrationBuilder?.dirty || window.DemographicsBuilder?.dirty || window.MembershipBuilder?.dirty || window.EventFooterBuilder?.dirty || window.SessionsBuilder?.dirty || window.WelcomeBuilder?.dirty) { event.preventDefault(); event.returnValue = ''; } });
async function saveEventDraft(){
  if(initializing||opening||saving||!form.reportValidity())return false;
  const data = Object.fromEntries(new FormData(form));
  data.address=Object.fromEntries(['line1','line2','city','region','postal','country'].map(k=>[k,field('address_'+k).value]));
  let advance=false;
  // Preserve values while switching formats, but only the selected format is displayed.
  data.url = field('url').value;
  saving = true; document.querySelector('#save').disabled = true;
  const controls = [...form.elements]; controls.forEach(control => control.disabled = true);
  message('Saving…');
  try {
    const saved = await api('/api/events' + (selected ? '/' + selected : ''), { method: selected ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    selected = saved.id; updateNav(); setLocation(); events = [saved, ...events.filter(item => item.id !== saved.id)]; dirty = false; renderList();
    document.querySelector('#editor-title').textContent = 'Edit event'; document.querySelector('#save-state').textContent = 'Saved draft';
    advance=true;
    message('Saved on this computer · ' + new Date(saved.updated).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}));
  } catch (error) { message(error.message || 'Could not connect. Keep this page open and restart Regfire, then try again.', true); }
  finally { saving = false; controls.forEach(control => control.disabled = false); formatFields(); }
  if(advance && !window.RegistrationFlows.current()){await window.RegistrationFlows.load(events.find(item=>item.id===selected));showView('event');}
  return advance;
}
form.addEventListener('submit',async event=>{event.preventDefault();if(await saveEventDraft()&&window.WelcomeBuilder?.dirty)await window.WelcomeBuilder.save();});
async function finishEvent(){
  const status=document.getElementById('event-done-status'),button=document.getElementById('event-done');
  if(saving||window.MembershipBuilder?.busy||window.EventFooterBuilder?.busy || window.SessionsBuilder?.busy || window.WelcomeBuilder?.busy){status.textContent='A save or upload is still finishing. Please try Done when it completes.';return;}
  if(!form.reportValidity()||(!document.getElementById('welcome-content').hidden&&!document.getElementById('welcome-form').reportValidity())){status.textContent='Please correct the highlighted fields before continuing.';return;}
  button.disabled=true;status.textContent='Saving event and welcome page…';
  try{if(!await saveEventDraft()){status.textContent='Event details could not be saved. Your edits are still here.';return;}if(!await window.WelcomeBuilder.save()){status.textContent='Welcome page could not be saved. Your edits are still here.';return;}if(!await window.EventFooterBuilder.save()){status.textContent='Shared footer could not be saved.';return;}if(!await window.MembershipBuilder.save()){status.textContent='Membership settings could not be saved. Your edits are still here.';return;}await window.RegistrationFlows.load(events.find(item=>item.id===selected));status.textContent='';showView('flows');}finally{button.disabled=false;}
}
document.getElementById('event-done').onclick=finishEvent;
document.getElementById('flows-tab').onclick=()=>activeView==='event'?finishEvent():switchView('flows');
document.getElementById('flows-edit-event').onclick=()=>switchView('event');
async function init() {
  formatFields();
  try {
    const zones = await api('/api/timezones');
    for (const zone of zones) { const option = document.createElement('option'); option.value = zone; option.textContent = zone.replaceAll('_', ' '); field('timezone').append(option); }
    field('timezone').value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    events = await api('/api/events'); renderList();
    const locationState = new URLSearchParams(location.hash.slice(1));
    const requested=locationState.get('event');
    const existing = requested?events.find(item => item.id === requested):events[0];
    if(requested&&!existing)throw new Error('The requested event was not found. Choose an existing event after reloading.');
    if (existing) {
      activeView = ['sessions','flows','setup','registration','demographics','membership'].includes(locationState.get('view')) ? locationState.get('view') : 'event';
      await openDraft(existing);
    } else {updateNav();loaded();}
    initializing=false;
  } catch (error) { loading('Could not load saved events. Reload to retry. '+error.message); }
  const context = document.modelContext;
  if (context?.registerTool) {
    try { await context.registerTool({ name:'list_event_drafts', description:'List saved Regfire event drafts on this computer.', inputSchema:{type:'object',properties:{},additionalProperties:false}, annotations:{readOnlyHint:true,untrustedContentHint:true}, execute:async () => api('/api/events') }); } catch (error) { console.warn('Optional browser tools unavailable', error); }
  }
}
function setLocation() {
  history.replaceState(null, '', selected ? '#event=' + encodeURIComponent(selected) + '&view=' + activeView + (window.RegistrationFlows?.current()?'&flow='+encodeURIComponent(window.RegistrationFlows.current().id):'') : location.pathname);
}
function updateNav() {
  document.getElementById('flows-tab').disabled=!selected;
  document.getElementById('sessions-tab').disabled=!selected;
  document.querySelector('#setup-tab').disabled = !selected;
  document.querySelector('#registration-tab').disabled = !selected;
  document.querySelector('#demographics-tab').disabled = !selected;
  document.querySelector('#nav-hint').hidden = !!selected;
  for (const [id, view] of [['details-tab','event'],['sessions-tab','sessions'],['flows-tab','flows'],['setup-tab','setup'],['registration-tab','registration'],['demographics-tab','demographics']]) {
    const button = document.querySelector('#' + id);
    if (view === activeView) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current');
  }
}
function showView(view, keepRegistration = false) {
  if(view!==activeView)window.scrollTo({top:0,behavior:'instant'});
  if(view==='membership')view='event';
  activeView = view; updateNav(); setLocation();renderList();
  document.querySelector('#sessions-view').hidden = view !== 'sessions';
  if(view==='sessions')window.SessionsBuilder.load(window.flowEvent());
  document.querySelector('#event-view').hidden = view !== 'event';
  document.querySelector('#welcome-view').hidden = !selected;
  document.querySelector('#flows-view').hidden=view!=='flows';
  document.querySelector('#flows-event-name').textContent=events.find(item=>item.id===selected)?.name||'';
  document.querySelector('#flow-context').hidden = ['event','flows'].includes(view);
  for(const id of ['setup-tab','registration-tab','demographics-tab','sessions-tab'])document.getElementById(id).hidden=['event','flows'].includes(view);
  document.querySelector('#flow-context-name').textContent = window.RegistrationFlows?.current()?.name || 'Attendee';
  document.querySelector('#welcome-event-name').textContent = events.find(item => item.id === selected)?.name || '';
  document.querySelector('#builder-view').hidden = !['setup','registration'].includes(view);
  const detailsName=window.RegistrationFlows?.current()?.kind==='attendee'?'Attendee details':'Registration details';
  document.querySelector('#registration-tab').textContent=detailsName;
  document.querySelector('#builder-page-title').textContent = view==='setup'?'Website setup':detailsName;
  document.querySelectorAll('#builder-form > section').forEach((section,index)=>{section.hidden = view==='setup'?index>=3:index<3;const step=section.querySelector('.step');if(step)step.textContent=String(index<3?index+1:index-2).padStart(2,'0');});
  document.querySelector('#demographics-view').hidden = view !== 'demographics';
  document.querySelector('#membership-view').hidden = !selected || !['event','membership'].includes(view);
  if (view === 'event' && selected) {window.WelcomeBuilder.load(events.find(item => item.id === selected));window.EventFooterBuilder.load(events.find(item => item.id === selected));}
  if (selected && ['event','membership'].includes(view)) window.MembershipBuilder.load(window.flowEvent());
  document.querySelector('main').classList.toggle('builder-active', view !== 'event');
  if (view === 'demographics') window.DemographicsBuilder.load(window.flowEvent());
  if (['setup','registration'].includes(view) && !keepRegistration) window.RegistrationBuilder.load(window.flowEvent());
}
async function switchView(view) {
  if (view === activeView || saving || window.RegistrationBuilder?.busy || window.DemographicsBuilder?.busy || window.MembershipBuilder?.busy || window.EventFooterBuilder?.busy || window.SessionsBuilder?.busy || window.WelcomeBuilder?.busy || (view !== 'event' && !selected)) return;
  if (['setup','registration'].includes(activeView) && ['setup','registration'].includes(view)) {showView(view,true);return;}
  if ((dirty || window.RegistrationBuilder?.dirty || window.DemographicsBuilder?.dirty || window.MembershipBuilder?.dirty || window.EventFooterBuilder?.dirty || window.SessionsBuilder?.dirty || window.WelcomeBuilder?.dirty) && !await confirmAction('Discard unsaved changes and continue?')) return;
  dirty = false; window.RegistrationBuilder.clear(); window.DemographicsBuilder?.clear(); window.MembershipBuilder?.clear(); window.WelcomeBuilder?.clear(); window.SessionsBuilder?.clear(); window.EventFooterBuilder?.clear();
  activeView = view;
  openDraft(events.find(item => item.id === selected) || null);
}
document.getElementById('sessions-tab').onclick=()=>switchView('sessions');
document.querySelector('#details-tab').onclick = () => switchView('event');
document.querySelector('#flow-back').onclick = () => switchView('flows');
document.querySelector('#setup-tab').onclick = () => switchView('setup');
document.querySelector('#registration-tab').onclick = () => switchView('registration');
document.querySelector('#demographics-tab').onclick = () => switchView('demographics');
window.addEventListener('DOMContentLoaded', init);


window.confirmAction = function(message) {
  return new Promise(resolve => {
    const dialog = document.querySelector('#confirm-dialog');
    document.querySelector('#confirm-message').textContent = message;
    dialog.returnValue = 'cancel';
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), {once:true});
    dialog.showModal();
  });
};
// Follow direct builder links even when the browser reuses this document.
window.addEventListener('hashchange', async () => {
  if(initializing)return;
  if(opening){setLocation();return;}
  if (saving || window.RegistrationBuilder?.busy || window.DemographicsBuilder?.busy || window.MembershipBuilder?.busy || window.EventFooterBuilder?.busy || window.SessionsBuilder?.busy || window.WelcomeBuilder?.busy) { setLocation(); return; }
  const route = new URLSearchParams(location.hash.slice(1));
  let destination = events.find(item => item.id === route.get('event')) || null;
  if (!destination && route.get('event')) {
    try { events = await api('/api/events'); destination = events.find(item => item.id === route.get('event')) || null; renderList(); } catch(error) { message('Could not open that event. Reload to retry.', true); setLocation(); return; }
  }
  if(route.get('event')&&!destination){message('That saved event could not be found. Your current event is unchanged.',true);setLocation();return;}
  const view = destination && ['sessions','flows','setup','registration','demographics','membership'].includes(route.get('view')) ? route.get('view') : 'event';
  if (destination?.id===selected && (!route.get('flow')||route.get('flow')===window.RegistrationFlows.current()?.id) && ['setup','registration'].includes(activeView) && ['setup','registration'].includes(view)) {showView(view,true);return;}
  if ((dirty || window.RegistrationBuilder?.dirty || window.DemographicsBuilder?.dirty || window.MembershipBuilder?.dirty || window.EventFooterBuilder?.dirty || window.SessionsBuilder?.dirty || window.WelcomeBuilder?.dirty) && !await confirmAction('Discard unsaved changes and open this event?')) {
    setLocation(); return;
  }
  dirty = false;
  window.RegistrationBuilder?.clear(); window.DemographicsBuilder?.clear(); window.MembershipBuilder?.clear(); window.WelcomeBuilder?.clear(); window.SessionsBuilder?.clear(); window.EventFooterBuilder?.clear();
  activeView = view;
  await openDraft(destination);
});

window.flowEvent=()=>{const event=events.find(e=>e.id===selected);const flow=window.RegistrationFlows?.current();return event?{...event,id:flow?.id||event.id}:null;};
window.liveEvent=window.flowEvent;

const addressKeys=['line1','line2','city','region','postal','country'];
function syncEventAddress(){
  field('location').value=addressKeys.map(key=>field('address_'+key).value.trim()).filter(Boolean).join(', ');
}
function applyEventAddress(address){
  for(const k of addressKeys)if(k!=='line2')field('address_'+k).value=address[k]||'';
  syncEventAddress();
  form.querySelector('.event-address').open=true;
  field('location').dispatchEvent(new Event('input',{bubbles:true}));
}
window.AddressLookup.attach(field('address_line1'),applyEventAddress);
for(const k of addressKeys)field('address_'+k).addEventListener('input',syncEventAddress);
document.querySelector('#delete-event').onclick=async()=>{
  const event=events.find(e=>e.id===selected);if(!event||saving)return;
  if(!await confirmAction('Permanently delete “'+event.name+'”? This removes its event draft, registration page, demographic questions, membership settings, imported members, sessions, the shared footer, and uploaded images. Other events are unchanged. Cancel keeps everything.'))return;
  saving=true;const controls=[...form.elements];controls.forEach(c=>c.disabled=true);document.querySelector('#delete-event').disabled=true;
  try{await api('/api/events/'+event.id,{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm_name:event.name})});events=events.filter(e=>e.id!==event.id);dirty=false;saving=false;activeView='event';window.RegistrationBuilder?.clear();window.DemographicsBuilder?.clear();window.MembershipBuilder?.clear(); window.WelcomeBuilder?.clear(); window.SessionsBuilder?.clear(); window.EventFooterBuilder?.clear();await openDraft();message('Event deleted. Create a new draft or choose another event.');}
  catch(e){message(e.message,true);}
  finally{saving=false;controls.forEach(c=>c.disabled=false);document.querySelector('#delete-event').disabled=false;formatFields();}
};

window.DraftAutosave.register({ready:()=>!initializing&&!opening&&dirty&&!saving&&!window.EventFooterBuilder?.busy&&!window.SessionsBuilder?.busy&&!window.WelcomeBuilder?.busy&&activeView==='event',snapshot:()=>{const data=Object.fromEntries(new FormData(form));data.address=Object.fromEntries(['line1','line2','city','region','postal','country'].map(k=>[k,field('address_'+k).value]));data.url=field('url').value;return data;},lock:value=>saving=value,clean:()=>{dirty=false;},status:(state,text,error)=>{document.querySelector('#save-state').textContent=state;message(text,error);},save:async data=>{const wasNew=!selected;const saved=await api('/api/events'+(selected?'/'+selected:''),{method:selected?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});selected=saved.id;events=[saved,...events.filter(item=>item.id!==saved.id)];updateNav();setLocation();renderList();document.querySelector('#editor-title').textContent='Edit event';if(wasNew){await window.RegistrationFlows.load(saved);showView('event');}}});
