/* Organizer-only contextual guidance; never writes event settings. */
(()=>{
 const guide={
 'Membership setup':['Configure membership checks for this registration flow.','Choose the membership source, review eligibility rules and test the lookup before using it.','Offer an eligible member the appropriate registration rate.'],
 'The essentials':['Name and describe this event.','Use a name attendees will recognize.','Annual Leadership Summit'],
 'When & where':['Set the event schedule and location.','Choose the timezone, then dates and either a venue or online link.','A conference running Tuesday through Wednesday.'],
 'Attendee photos':['Control whether attendees can upload a photo.','Enable uploads and review the available screening options.','Collect portraits for attendee badges.'],
 'Organizer':['Set the organizer contact information.','Enter the contact attendees should use for event questions.','Your event support email address.'],
 'Page title':['Customize the welcome page heading.','Enter the title and choose its available text styling.','Welcome to the RegFire Expo'],
 'Welcome background':['Style the event welcome page background.','Choose the available color or image options and check the preview.','Use a branded background behind the welcome content.'],
 'Show logo':['Set the main event logo.','Upload the event mark here; use Sponsor logos for partners.','The conference logo at the top of the welcome page.'],
 'Sponsor logos':['Display supporting organizations.','Add each sponsor separately, then use its Replace or Remove control.','Three transparent sponsor logos displayed together.'],
 'About the event':['Introduce the event to attendees.','Write a concise description and preview the presentation.','Who should attend and what they can expect.'],
 'Register buttons':['Direct visitors into registration flows.','Choose the flow and edit the button label.','Separate buttons for attendees and exhibitors.'],
 'Registration footer':['Set the shared registration footer.','Edit the footer here and check it across your registration flows.','Contact information and event policies.'],
 'Page introduction':['Introduce this step of registration.','Set the heading and introductory copy for this page.','Choose your pass to get started.'],
 'Show branding':['Style the registration page.','Select branding assets and appearance settings, then review the attendee preview.','Match the page to your event colors.'],
 'RegTypes & pricing':['Define the registration choices and prices.','Add types, configure rates, and add nested choices where needed.','A one-day pass with Tuesday or Wednesday choices.'],
 'Registration fields':['Choose the attendee information to collect.','Add or edit fields and their required or visibility settings.','Require a name and email address.'],
 'Promo codes':['Configure promotional discounts and their limits.','Create a code, review its discount and allotment, and save the settings.','A limited-use exhibitor promotion.'],
 'Your questions':['Build demographic questions for this registration flow.','Add a question, choose its answer format, and edit its choices.','Ask attendees which topics interest them.'],
 'Eligibility & policy':['Configure membership eligibility checks.','Select the membership source and review lookup and eligibility settings.','Verify a member before applying member pricing.'],
 'Import members':['Replace the membership list from a file.','Upload a CSV, map columns, preview validation, then confirm replacement. Keep your original file.','Import member IDs, names, emails and expiration dates.'],
 'Agenda settings':['Configure the attendee session page.','Review the available agenda settings and check the preview.','Present sessions for a multi-day conference.'],
 'Create a speaker':['Add a speaker profile.','Enter the speaker details and picture, then associate the speaker with a session.','A keynote speaker with a biography and portrait.'],
 'Create a session':['Add a session to this registration flow.','Set its title, schedule, room and speaker using the available fields.','A Tuesday morning workshop.'],
 'Your sessions':['Manage sessions already added to this flow.','Review the list and edit the session that needs a change.','Update a room or session time.'],
 'Import CSV or TSV':['Create session records from a spreadsheet export.','Follow the import instructions and review the result before relying on the agenda.','Import a conference schedule from a CSV file.'],
 'Options settings':['Configure the extra-options page.','Set the page options and review how they appear to attendees.','Introduce optional event add-ons.'],
 'Your extra options':['Manage optional selections for attendees.','Add each option and review its available price and selection settings.','An optional event activity.']
 };
 const panel=document.createElement('div');panel.className='context-help-panel';panel.id='regfire-context-help';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Section help');document.body.append(panel);
 let active=null,pinned=false,timer,suppressFocus=false;
 function restore(b){suppressFocus=true;b?.focus();suppressFocus=false;}
 function close(){clearTimeout(timer);if(active)active.setAttribute('aria-expanded','false');panel.hidden=true;active=null;pinned=false;}
 function place(){if(!active)return;const r=active.getBoundingClientRect();panel.style.left=Math.max(8,Math.min(r.left,innerWidth-panel.offsetWidth-8))+'px';panel.style.top=Math.max(8,Math.min(r.bottom+8,innerHeight-panel.offsetHeight-8))+'px';}
 function show(button,title,info,keep=false){clearTimeout(timer);if(active&&active!==button)close();active=button;pinned=keep||pinned;button.setAttribute('aria-expanded','true');panel.replaceChildren();const heading=document.createElement('strong');heading.textContent=title;panel.append(heading);info.forEach((text,i)=>{const p=document.createElement('p');p.textContent=(i===1?'How: ':i===2?'Example: ':'')+text;panel.append(p);});const dismiss=document.createElement('button');dismiss.type='button';dismiss.textContent='Close help';dismiss.onclick=()=>{const b=active;close();restore(b);};panel.append(dismiss);panel.hidden=false;place();}
 function later(){clearTimeout(timer);timer=setTimeout(()=>{if(!pinned&&!panel.matches(':hover')&&!panel.contains(document.activeElement))close();},180);}
 panel.addEventListener('mouseenter',()=>clearTimeout(timer));panel.addEventListener('mouseleave',later);
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&active){const b=active;close();restore(b);}});
 document.addEventListener('pointerdown',e=>{if(active&&!panel.contains(e.target)&&!active.contains(e.target))close();});
 window.addEventListener('resize',place);window.addEventListener('scroll',()=>{if(active)place();},true);
 function refresh(){document.querySelectorAll('h3').forEach(h=>{if(h.dataset.contextHelp)return;const title=h.textContent.trim().replace(/\s+\d+$/,'');const info=guide[title];if(!info)return;h.dataset.contextHelp='true';const b=document.createElement('button');b.type='button';b.className='context-help-trigger';b.textContent='?';b.setAttribute('aria-label','Help: '+title);b.setAttribute('aria-controls',panel.id);b.setAttribute('aria-haspopup','dialog');b.setAttribute('aria-expanded','false');b.addEventListener('mouseenter',()=>show(b,title,info));b.addEventListener('mouseleave',later);b.addEventListener('focus',()=>{if(!suppressFocus)show(b,title,info);});b.addEventListener('blur',later);b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();show(b,title,info,true);panel.querySelector('button').focus();});h.after(b);});if(active&&(!active.isConnected||!active.getClientRects().length))close();}
 let queued=false;new MutationObserver(()=>{if(!queued){queued=true;requestAnimationFrame(()=>{queued=false;refresh();});}}).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});refresh();
})();
