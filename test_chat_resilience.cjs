const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8');
const adaptive=source.slice(source.indexOf('async function adaptive()'),source.indexOf('async function loadIntegrations()'));
const persist=source.split('\n').find(line=>line.startsWith('function persistChats()'));
function fixture(){
 const nodes=new Map(), shown=[];
 const node=()=>({value:'Consulta de prueba',style:{},disabled:false,appendChild(){},remove(){},focus(){}});
 const origin={id:'original',title:'Original',messages:[]},other={id:'other',messages:[]};
 let resolve;
 const context={chats:[origin,other],activeChatId:origin.id,chatMessages:origin.messages,
  $:s=>{if(!nodes.has(s))nodes.set(s,node());return nodes.get(s)},
  document:{createElement:node},saveChat(){},persistChats(){},renderChatList(){},load(){},
  addChat:(...args)=>shown.push(args),toast(){},fetch:()=>new Promise(r=>resolve=r),console};
 vm.createContext(context);vm.runInContext(adaptive,context);
 return {context,origin,other,shown,finish:result=>resolve(result)};
}
(async()=>{
 let f=fixture(),pending=f.context.adaptive();
 f.context.activeChatId=f.other.id;f.context.chatMessages=f.other.messages;
 f.finish({ok:true,json:async()=>({text:'Respuesta correcta',model:'test'})});await pending;
 assert.equal(f.origin.messages[1].content,'Respuesta correcta');assert.equal(f.other.messages.length,0);
 assert.equal(f.shown.length,1);assert.equal(f.context.$('#ask').disabled,false);
 f=fixture();pending=f.context.adaptive();f.context.chats=[f.other];
 f.finish({ok:true,json:async()=>({text:'No resucitar chat borrado'})});await pending;
 assert.equal(f.origin.messages.length,1);assert.equal(f.context.chats.length,1);
 f=fixture();pending=f.context.adaptive();
 f.finish({ok:false,json:async()=>{throw new Error('invalid json')}});await pending;
 assert.equal(f.origin.messages[1].error,true);assert.match(f.origin.messages[1].content,/respuesta no válida/);
 assert.equal(f.context.$('#ask').disabled,false);
 let warnings=0;
 const ctx={localStorage:{setItem(){throw new Error('quota')}},CHAT_KEY:'test',chats:[],storageWarningShown:false,toast(){warnings++},console:{warn(){}}};
 vm.createContext(ctx);vm.runInContext(persist,ctx);
 assert.equal(ctx.persistChats(),false);assert.equal(ctx.persistChats(),false);assert.equal(warnings,1);
 console.log('4 pruebas de resiliencia del cliente: OK');
})().catch(e=>{console.error(e);process.exitCode=1});
