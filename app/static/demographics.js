(() => {
  const $=id=>document.getElementById(id), uid=()=>crypto.randomUUID();
  const kinds={text:'Short text',textarea:'Long text',radio:'Single choice',multiselect:'Multiple choice',select:'Dropdown',number:'Number',date:'Date',boolean:'Yes / no'};
  const opLabels={equals:'Equals',not_equals:'Does not equal',contains:'Contains',includes:'Includes',not_includes:'Does not include',gt:'Greater than / after',gte:'At least / on or after',lt:'Less than / before',lte:'At most / on or before',is_answered:'Is answered'};
  const ops={text:['equals','not_equals','contains','is_answered'],textarea:['equals','not_equals','contains','is_answered'],radio:['equals','not_equals','is_answered'],select:['equals','not_equals','is_answered'],multiselect:['includes','not_includes','is_answered'],number:['equals','not_equals','gt','gte','lt','lte','is_answered'],date:['equals','not_equals','gt','gte','lt','lte','is_answered'],boolean:['equals','not_equals','is_answered']};
  let page=null,event=null,registration=null,changed=false,busy=false,loadToken=0;
  const node=(tag,cls='',text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const label=(text,control)=>{const n=node('label','',text);n.append(control);return n;};
  const input=(value,max=160)=>{const n=node('input');n.value=value;n.maxLength=max;return n;};
  const button=(text,fn,aria,disabled=false)=>{const n=node('button','small-button',text);n.type='button';n.onclick=fn;if(aria)n.setAttribute('aria-label',aria);n.disabled=disabled;return n;};
  function select(items,value){const n=node('select');for(const [id,text] of items){const o=node('option','',text);o.value=id;n.append(o);}n.value=value;return n;}
  function say(message,error=false){$('demo-feedback').textContent=message;$('demo-feedback').className=error?'error':'';}
  function dirty(){changed=true;$('demo-save-state').textContent='Unsaved changes';say('Save demographics to keep these questions and rules.');}
  function edited(){dirty();}
  const regtypes=()=>registration?.regtypes||[];
  const references=id=>page.questions.some(q=>q.conditions.rules.some(r=>r.question_id===id));
  function validOrder(questions){const seen=new Set();for(const q of questions){for(const rule of q.conditions.rules)if(rule.question_id&&!seen.has(rule.question_id))return false;seen.add(q.id);}return true;}
  function commitOrder(questions){if(!validOrder(questions)){say('A branching source must stay before every question that uses it. Adjust the rules before moving this question.',true);$('demo-order-status').textContent='Order unchanged: branching source must remain earlier.';return false;}page.questions=questions;edited();renderQuestions();return true;}
  function move(index,delta){const next=[...page.questions];[next[index],next[index+delta]]=[next[index+delta],next[index]];commitOrder(next);}
  async function load(ev){
    const ticket=++loadToken;event=ev;page=null;changed=false;
    $('demo-loading').hidden=false;$('demo-content').hidden=true;$('demo-load-error').hidden=true;$('demo-event-name').textContent=ev?.name||'';
    try{
      const [definition,reg]=await Promise.all([api('/api/events/'+ev.id+'/demographics'),api('/api/events/'+ev.id+'/registration-page')]);
      if(ticket!==loadToken)return;page=definition;registration=reg;
      $('demo-title').value=page.title;$('demo-intro').value=page.intro;$('demo-save-state').textContent=page.updated?'Saved demographics':'New question draft';say(page.updated?'Last saved '+new Date(page.updated).toLocaleString():'Start with the questions your event needs. No questions are required by default.');
      renderQuestions();$('demo-content').hidden=false;
    }catch(error){if(ticket===loadToken){$('demo-load-message').textContent=error.message;$('demo-load-error').hidden=false;}}
    finally{if(ticket===loadToken)$('demo-loading').hidden=true;}
  }
  function renderQuestions(){
    const target=$('demo-questions');target.replaceChildren();
    if(!page.questions.length)target.append(node('div','empty','No demographic questions yet. Add only what your event needs.'));
    page.questions.forEach((q,index)=>{
      const card=node('div','question-card');card.dataset.questionId=q.id;
      const heading=node('div','item-heading');heading.append(handle(q,index),node('strong','', 'Question '+(index+1)));
      const actions=node('div','order-controls');actions.append(button('↑',()=>move(index,-1),'Move question '+(index+1)+' up',index===0),button('↓',()=>move(index,1),'Move question '+(index+1)+' down',index===page.questions.length-1),button('Duplicate',()=>{
        const copy=structuredClone(q);copy.id=uid();copy.label=('Copy of '+q.label).slice(0,160);copy.options=copy.options.map(o=>({...o,id:uid()}));page.questions.splice(index+1,0,copy);edited();renderQuestions();
      },'Duplicate question '+(index+1),page.questions.length>=50),button('Remove',async()=>{
        if(references(q.id)){say('Other questions branch from this question. Remove or change those rules before deleting it.',true);return;}
        if(!await confirmAction('Remove '+(q.label||'this question')+' from Demographics?'))return;
        page.questions.splice(index,1);edited();renderQuestions();
      },'Remove question '+(index+1)));heading.append(actions);card.append(heading);
      const title=input(q.label);title.oninput=()=>{q.label=title.value;edited();};card.append(label('Question label',title));
      const help=node('textarea');help.rows=2;help.maxLength=1000;help.value=q.help;help.oninput=()=>{q.help=help.value;edited();};card.append(label('Help text (optional)',help));
      const type=select(Object.entries(kinds),q.type);type.onchange=async()=>{
        const next=type.value,previous=q.type,choice=['select','radio','multiselect'];
        const dependent=page.questions.flatMap(other=>other.conditions.rules.filter(r=>r.question_id===q.id));
        const compatible=(['select','radio'].includes(previous)&&['select','radio'].includes(next))||(['text','textarea'].includes(previous)&&['text','textarea'].includes(next));
        const reset=dependent.filter(r=>r.operator!=='is_answered'&&!compatible);
        const removesChoices=choice.includes(previous)&&!choice.includes(next)&&q.options.length>0;
        if(reset.length||removesChoices){type.value=previous;
          const explanation='Change “'+(q.label||'this question')+'” from '+kinds[previous]+' to '+kinds[next]+'? '+(reset.length?reset.length+' branching condition(s) will become “Is answered”; their follow-up questions are kept. ':'')+(removesChoices?'The existing answer-choice list will be removed. ':'')+'Review the rules after changing the type.';
          if(!await confirmAction(explanation))return;
        }
        for(const rule of reset){rule.operator='is_answered';rule.value=null;}
        q.type=next;if(!choice.includes(next))q.options=[];else if(q.options.length<2)q.options=[{id:uid(),label:'Option 1'},{id:uid(),label:'Option 2'}];
        edited();renderQuestions();say('Question type changed to '+kinds[next]+'. '+(reset.length?'Review the updated “Is answered” branching rules, then save.':'Save demographics to keep the change.'));
      };card.append(label('Question type',type));
      const required=node('input');required.type='checkbox';required.checked=q.required;required.onchange=()=>{q.required=required.checked;edited();};const req=node('label','check-label');req.append(required,document.createTextNode('Required when visible'));card.append(req);
      const assignment=node('div','question-assignment');assignment.append(node('strong','','RegType assignment'));
      const visible=select([['all','All RegTypes'],['selected','Selected RegTypes']],q.visible_to===null?'all':'selected');visible.onchange=()=>{q.visible_to=visible.value==='all'?null:[];edited();renderQuestions();};assignment.append(label('Who sees this question?',visible));
      if(q.visible_to!==null){const group=node('fieldset');group.append(node('legend','','Select one or more RegTypes'));regtypes().forEach(r=>{const check=node('input');check.type='checkbox';check.checked=q.visible_to.includes(r.id);check.onchange=()=>{q.visible_to=check.checked?[...q.visible_to,r.id]:q.visible_to.filter(id=>id!==r.id);edited();};const l=node('label','check-label');l.append(check,document.createTextNode(r.name));group.append(l);});assignment.append(group);}
      assignment.append(node('p','field-note','The same question can be shared by several RegTypes. Branching rules must also match.'));card.append(assignment);
      if(['select','radio','multiselect'].includes(q.type)){
        const options=node('div','question-options');options.append(node('h4','','Answer choices'));
        q.options.forEach((option,oi)=>{const row=node('div','option-row');const control=input(option.label,120);control.setAttribute('aria-label','Choice '+(oi+1));control.oninput=()=>{option.label=control.value;edited();};row.append(control,button('Remove',()=>{
          if(page.questions.some(other=>other.conditions.rules.some(r=>r.question_id===q.id&&r.value===option.id))){say('A branching rule uses this option. Change that rule before removing the option.',true);return;}
          q.options.splice(oi,1);edited();renderQuestions();
        },'Remove choice '+(oi+1),q.options.length<=2));options.append(row);});
        options.append(button('＋ Add choice',()=>{q.options.push({id:uid(),label:''});edited();renderQuestions();},'Add choice to question '+(index+1),q.options.length>=30));card.append(options);
      }
      const branch=node('div','question-branch');branch.append(node('h4','','Branching'));
      branch.append(node('p','field-note',q.conditions.rules.length?'Show this question when its RegType assignment matches AND the rules below match.':'No answer conditions. Show for its assigned RegTypes.'));
      if(q.conditions.rules.length){const mode=select([['all','All rules must match'],['any','Any rule can match']],q.conditions.mode);mode.onchange=()=>{q.conditions.mode=mode.value;edited();};branch.append(label('Rule logic',mode));}
      q.conditions.rules.forEach((rule,ri)=>{
        const box=node('div','branch-rule');const parent=page.questions.find(p=>p.id===rule.question_id);
        const source=select(page.questions.slice(0,index).map(p=>[p.id,p.label||'Untitled earlier question']),rule.question_id);
        source.onchange=()=>{const p=page.questions.find(p=>p.id===source.value);rule.question_id=p.id;rule.operator=ops[p.type][0];rule.value=p.type==='boolean'?true:'';edited();renderQuestions();};box.append(label('Earlier question',source));
        const operator=select((ops[parent?.type]||[]).map(key=>[key,opLabels[key]]),rule.operator);operator.onchange=()=>{rule.operator=operator.value;rule.value=rule.operator==='is_answered'?null:parent.type==='boolean'?true:'';edited();renderQuestions();};box.append(label('Comparison',operator));
        if(rule.operator!=='is_answered'&&parent){let value;
          if(['radio','select','multiselect'].includes(parent.type))value=select([['','Choose an answer'],...parent.options.map(o=>[o.id,o.label||'Unnamed choice'])],rule.value||'');
          else if(parent.type==='boolean')value=select([['true','Yes'],['false','No']],String(rule.value));
          else{value=input(rule.value??'',5000);if(['number','date'].includes(parent.type)){value.type=parent.type;if(parent.type==='number')value.step='any';}}
          const change=()=>{rule.value=parent.type==='boolean'?value.value==='true':value.value;edited();};value.oninput=change;box.append(label('Answer value',value));
        }
        box.append(button('Remove rule',()=>{q.conditions.rules.splice(ri,1);edited();renderQuestions();},'Remove rule '+(ri+1)+' from question '+(index+1)));branch.append(box);
      });
      branch.append(button('＋ Add rule',()=>{const parent=page.questions[index-1];q.conditions.rules.push({question_id:parent.id,operator:ops[parent.type][0],value:parent.type==='boolean'?true:''});edited();renderQuestions();},'Add rule to question '+(index+1),index===0||q.conditions.rules.length>=10));
      if(index===0)branch.append(node('p','field-note','The first question has no earlier answers to branch from.'));
      card.append(branch);target.append(card);
    });
    $('demo-add').disabled=page.questions.length>=50;
  }
  let drag=null,raf=null;
  function cleanDrop(){document.querySelectorAll('.question-card.drop-before,.question-card.drop-after').forEach(el=>el.classList.remove('drop-before','drop-after'));}
  function findDrop(){cleanDrop();const target=document.elementFromPoint(drag.x,drag.y)?.closest('.question-card');drag.target=null;if(!target||target.dataset.questionId===drag.id)return;const rect=target.getBoundingClientRect();drag.after=drag.y>rect.top+rect.height/2;drag.target=target.dataset.questionId;target.classList.add(drag.after?'drop-after':'drop-before');}
  function scrollDrag(){if(!drag?.active)return;if(drag.y<70||drag.y>innerHeight-70){window.scrollBy(0,drag.y<70?-12:12);findDrop();}raf=requestAnimationFrame(scrollDrag);}
  function handle(q,index){const h=button('⠿',()=>{},'Drag question '+(index+1)+' to reorder');h.className='drag-handle';h.title='Drag to reorder, or use up/down controls.';
    h.onpointerdown=e=>{if(e.button!==0||busy)return;drag={id:q.id,start:e.clientY,x:e.clientX,y:e.clientY,active:false,target:null};h.setPointerCapture(e.pointerId);};
    h.onpointermove=e=>{if(!drag)return;drag.x=e.clientX;drag.y=e.clientY;if(!drag.active&&Math.abs(drag.y-drag.start)>6){drag.active=true;h.closest('.question-card').classList.add('dragging');scrollDrag();}if(drag.active){e.preventDefault();findDrop();}};
    function finish(cancel){if(!drag)return;const d=drag;drag=null;cancelAnimationFrame(raf);cleanDrop();document.querySelector('.question-card.dragging')?.classList.remove('dragging');if(!cancel&&d.active&&d.target){const next=[...page.questions];const [item]=next.splice(next.findIndex(q=>q.id===d.id),1);const to=next.findIndex(q=>q.id===d.target)+(d.after?1:0);next.splice(to,0,item);if(commitOrder(next))$('demo-order-status').textContent='Moved '+item.label+' to position '+(to+1)+'.';}}
    h.onpointerup=()=>finish(false);h.onpointercancel=()=>finish(true);return h;
  }
  const commonQuestionTemplates={"What is your primary job function?": {"type": "select", "answers": ["Executive leadership", "Engineering / technical", "Operations / production", "Purchasing / procurement", "Sales / business development", "Marketing / communications", "Research / development", "Consulting", "Education / training", "Other"]}, "What is your job level or seniority?": {"type": "radio", "answers": ["Owner / partner", "Executive / C-suite", "Vice president", "Director", "Manager / supervisor", "Individual contributor", "Student / trainee", "Other"]}, "Which industry does your organization primarily serve?": {"type": "select", "answers": ["Manufacturing", "Wholesale / distribution", "Retail / e-commerce", "Technology", "Healthcare / life sciences", "Construction / real estate", "Financial / professional services", "Education / research", "Government / nonprofit", "Other"]}, "What type of organization do you work for?": {"type": "radio", "answers": ["Manufacturer / producer", "Distributor / wholesaler", "Retailer / reseller", "Service provider / consultant", "End-user organization", "Government / public sector", "Association / nonprofit", "Education / research institution", "Other"]}, "How many employees work at your organization?": {"type": "radio", "answers": ["1–10", "11–50", "51–250", "251–500", "501–1,000", "1,001 or more", "Not sure"]}, "What is your role in purchasing decisions?": {"type": "radio", "answers": ["Final decision-maker", "Direct buyer / purchaser", "Recommend products or services", "Research / evaluate options", "Not involved in purchasing", "Other"]}, "Which products or services are you interested in?": {"type": "multiselect", "answers": ["Equipment / machinery", "Software / technology", "Materials / components", "Professional services / consulting", "Training / education", "Other"]}, "What are your main reasons for attending?": {"type": "multiselect", "answers": ["Discover new products or services", "Find suppliers / make purchases", "Learn / attend education sessions", "Network with industry peers", "Meet existing business partners", "Keep up with industry trends", "Explore business partnerships", "Other"]}, "How many years have you worked in your industry?": {"type": "radio", "answers": ["Less than 1 year", "1–5 years", "6–10 years", "11–15 years", "16–20 years", "21 years or more"]}, "What is your organization’s annual purchasing budget?": {"type": "radio", "answers": ["Under 10,000", "10,000–49,999", "50,000–99,999", "100,000–499,999", "500,000–999,999", "1,000,000 or more", "Not sure", "Prefer not to answer"]}};
  $('demo-add-common').onclick=()=>{const label=$('demo-common-question').value,template=commonQuestionTemplates[label];if(!template)return;if(page.questions.length>=50){$('demo-common-status').textContent='The question limit has been reached.';return;}const help=label.includes('purchasing budget')?'Amounts in '+(registration?.currency||'USD')+'.':'';page.questions.push({id:uid(),label,help,type:template.type,required:false,options:template.answers.map(answer=>({id:uid(),label:answer})),visible_to:null,conditions:{mode:'all',rules:[]}});edited();renderQuestions();$('demo-common-status').textContent='Question and editable starter answers added.';$('demo-common-question').value='';$('demo-questions').lastElementChild.querySelector('input').focus();};
  $('demo-add').onclick=()=>{page.questions.push({id:uid(),label:'',help:'',type:'text',required:false,options:[],visible_to:null,conditions:{mode:'all',rules:[]}});edited();renderQuestions();$('demo-questions').lastElementChild.querySelector('input').focus();};
  $('demo-title').oninput=()=>{page.title=$('demo-title').value;edited();};$('demo-intro').oninput=()=>{page.intro=$('demo-intro').value;edited();};
  $('demo-retry').onclick=()=>load(event);
  async function save(){if(busy||!page||!$('demo-editor').reportValidity())return false;busy=true;const controls=[...$('demo-editor').elements];controls.forEach(c=>c.disabled=true);say('Saving demographics…');
    try{page=await api('/api/events/'+event.id+'/demographics',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(page)});changed=false;$('demo-save-state').textContent='Saved demographics';say('Saved on this computer · '+new Date(page.updated).toLocaleTimeString());$('demo-title').value=page.title;$('demo-intro').value=page.intro;return true;}
    catch(error){say(error.message,true);return false;}finally{busy=false;controls.forEach(c=>c.disabled=false);renderQuestions();}
  };
  $('demo-editor').onsubmit=e=>{e.preventDefault();window.saveSetupNext();};
  window.DemographicsBuilder={load,save,snapshot(){return page?{event_id:event.id,page:structuredClone(page)}:null;},clear(){loadToken++;page=null;changed=false;},get dirty(){return changed;},get busy(){return busy;}};
  window.DraftAutosave.register({ready:()=>!!(page&&changed&&!busy),snapshot:()=>(structuredClone(page)),lock:value=>busy=value,clean:()=>{changed=false;},status:(state,message,error)=>{$('demo-save-state').textContent=state;say(message,error);},save:data=>api('/api/events/'+event.id+'/demographics',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})});
})();
