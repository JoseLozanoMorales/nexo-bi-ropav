/* Navigation and viewport handling are independent of analytics and PNG export. */
(()=>{
 const sidebar=document.querySelector('#mainSidebar'),toggle=document.querySelector('#menuToggle'),backdrop=document.querySelector('#menuBackdrop'),close=document.querySelector('#menuClose');
 const compact=matchMedia('(max-width:1000px)');
 function setMenu(open){
  open=!!open&&compact.matches;
  document.body.classList.toggle('menu-open',open);toggle.setAttribute('aria-expanded',String(open));backdrop.hidden=!open;
  sidebar.inert=compact.matches&&!open;
  if(open)close.focus();
 }
 toggle.addEventListener('click',()=>setMenu(!document.body.classList.contains('menu-open')));
 close.addEventListener('click',()=>{setMenu(false);toggle.focus()});
 backdrop.addEventListener('click',()=>{setMenu(false);toggle.focus()});
 sidebar.addEventListener('click',event=>{if(event.target.closest('[data-view]')){setMenu(false);if(compact.matches)toggle.focus()}});
 document.addEventListener('keydown',event=>{
  if(!document.body.classList.contains('menu-open'))return;
  if(event.key==='Escape'){setMenu(false);toggle.focus()}
  if(event.key==='Tab'){
   const items=[...sidebar.querySelectorAll('button,a[href]')].filter(el=>!el.disabled&&el.getClientRects().length);
   const first=items[0],last=items.at(-1);
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
  }
 });
 compact.addEventListener('change',()=>setMenu(false));setMenu(false);
 const workspace=document.querySelector('.chat-workspace'),history=workspace.querySelector('.chat-history');
 history.id='conversationHistory';
 const historyButton=document.createElement('button');historyButton.type='button';historyButton.className='history-toggle';historyButton.textContent='Conversaciones';historyButton.setAttribute('aria-controls',history.id);historyButton.setAttribute('aria-expanded','false');workspace.prepend(historyButton);
 historyButton.addEventListener('click',()=>{const open=workspace.classList.toggle('history-open');historyButton.setAttribute('aria-expanded',String(open))});
 history.addEventListener('click',event=>{if(event.target.closest('.history-item')||event.target.closest('#newChat')){workspace.classList.remove('history-open');historyButton.setAttribute('aria-expanded','false')}});
 const chat=document.querySelector('#adaptiveView');
 function resizeChat(){
  if(chat.classList.contains('hidden'))return;
  const viewport=window.visualViewport;
  const bottom=(viewport?viewport.height+viewport.offsetTop:innerHeight);
  chat.style.setProperty('--chat-space',Math.max(160,bottom-chat.getBoundingClientRect().top-12)+'px');
 }
 new MutationObserver(resizeChat).observe(chat,{attributes:true,attributeFilter:['class']});
 window.addEventListener('resize',resizeChat);window.visualViewport?.addEventListener('resize',resizeChat);resizeChat();
})();
