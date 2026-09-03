/* Shared chat/export presentation. All text is rendered without trusting HTML. */
const addChatBeforeFooter = addChat;
function splitChatTechnical(text){
 const narrative=[],technical=[];let following=false;
 for(const block of String(text||'').split(/\n\s*\n/)){
  if(/^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:par[aá]metros|filtros(?: usados| aplicados| exactos)?\s*[:(]|consulta (?:realizada|t[eé]cnica)|indicadores?\s*\(\s*copiado|detalles?\s*\(\s*filtros)/i.test(block)){technical.push(block);following=true}
  else if(following&&/^\s*(?:\{|\[|```|[-*]\s)/.test(block))technical.push(block);
  else{narrative.push(block);following=false}
 }
 return {narrative:narrative.join('\n\n'),technical:technical.join('\n\n')};
}
addChat=function(role,text,meta='',chart=null,dashboard=null){
 const parts=role==='assistant'?splitChatTechnical(text):{narrative:text,technical:''};
 const row=addChatBeforeFooter(role,parts.narrative,meta,chart,dashboard);
 if(parts.technical){const footer=document.createElement('section');footer.className='chat-technical';footer.style.cssText='margin-top:20px;padding-top:12px;border-top:1px solid #dfe6ed;font-size:12px;overflow-wrap:anywhere';if(window.ChatTables)ChatTables.render(footer,parts.technical);else footer.textContent=parts.technical;row.querySelector('.chat-bubble').append(footer)}
 return row;
};

function pngCollectionZip(files){
 const encoder=new TextEncoder(),parts=[],directory=[];let offset=0;
 const crc32=bytes=>{let crc=0xffffffff;for(const b of bytes){crc^=b;for(let i=0;i<8;i++)crc=(crc>>>1)^((crc&1)?0xedb88320:0)}return (crc^0xffffffff)>>>0};
 for(const file of files){
  const name=encoder.encode(file.name),bytes=file.bytes,crc=crc32(bytes),local=new Uint8Array(30+name.length),lv=new DataView(local.buffer);
  lv.setUint32(0,0x04034b50,true);lv.setUint16(4,20,true);lv.setUint16(6,0x800,true);lv.setUint32(14,crc,true);lv.setUint32(18,bytes.length,true);lv.setUint32(22,bytes.length,true);lv.setUint16(26,name.length,true);local.set(name,30);parts.push(local,bytes);
  const central=new Uint8Array(46+name.length),cv=new DataView(central.buffer);cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);cv.setUint16(8,0x800,true);cv.setUint32(16,crc,true);cv.setUint32(20,bytes.length,true);cv.setUint32(24,bytes.length,true);cv.setUint16(28,name.length,true);cv.setUint32(42,offset,true);central.set(name,46);directory.push(central);offset+=local.length+bytes.length;
 }
 const end=new Uint8Array(22),ev=new DataView(end.buffer);ev.setUint32(0,0x06054b50,true);ev.setUint16(8,files.length,true);ev.setUint16(10,files.length,true);ev.setUint32(12,directory.reduce((n,x)=>n+x.length,0),true);ev.setUint32(16,offset,true);
 return new Blob([...parts,...directory,end],{type:'application/zip'});
}
const downloadDashboardBeforeCollection=downloadDashboard;
downloadDashboard=function(spec){
 if(!spec.export_collection)return downloadDashboardBeforeCollection(spec);
 const files=spec.charts.map((ch,i)=>{const raw=atob(chartExportCanvas(ch).toDataURL('image/png').split(',')[1]);return {name:`${i+1}-${ch.type}.png`,bytes:Uint8Array.from(raw,c=>c.charCodeAt(0))}});
 const url=URL.createObjectURL(pngCollectionZip(files)),link=document.createElement('a');link.href=url;link.download='graficos-seleccionados.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
const attachDashboardBeforeCollection=attachDashboard;
attachDashboard=function(bubble,spec){attachDashboardBeforeCollection(bubble,spec);if(spec.export_collection)bubble.lastElementChild.querySelector('.dashboard-download').textContent='Descargar ambos PNG (ZIP)'};

function drawForecastSeries(c,ch){
 const w=Number(c.dataset.renderWidth)||c.clientWidth||600,h=360,dpr=devicePixelRatio||1,pad={l:85,r:20,t:24,b:65};
 c.width=w*dpr;c.height=h*dpr;c.style.height=h+'px';const x=c.getContext('2d');x.scale(dpr,dpr);
 const rows=ch.forecast.intervals||[],values=rows.flatMap(r=>[r.inferior,r.estimado,r.superior]).map(Number).filter(Number.isFinite);
 const low=Math.min(0,...values),high=Math.max(1,...values),range=high-low||1;
 const xx=i=>pad.l+(i+.5)*(w-pad.l-pad.r)/Math.max(1,ch.labels.length),yy=v=>h-pad.b-(v-low)/range*(h-pad.t-pad.b);
 x.font='11px Arial';x.textAlign='right';
 for(let i=0;i<=4;i++){const value=low+range*i/4,y=yy(value);x.strokeStyle='#e1e7ed';x.beginPath();x.moveTo(pad.l,y);x.lineTo(w-pad.r,y);x.stroke();x.fillStyle='#526177';x.fillText(chartNumber(value,ch),pad.l-8,y+4)}
 x.textAlign='left';x.fillText(['moneda','currency'].includes(ch.value_format)?'USD':(['percent','porcentaje'].includes(ch.value_format)?'%':'Valor'),pad.l,14);
 ch.datasets.forEach((dataset,j)=>{
  const points=ch.labels.map((period,i)=>{const row=rows.find(r=>r.periodo===period&&r.serie===dataset.label);return row?{...row,x:xx(i)}:null});
  const valid=points.filter(Boolean);if(!valid.length)return;
  const color=dataset.color||chartColor(ch,j);x.fillStyle=color;x.globalAlpha=.12;x.beginPath();valid.forEach((p,i)=>i?x.lineTo(p.x,yy(p.superior)):x.moveTo(p.x,yy(p.superior)));[...valid].reverse().forEach(p=>x.lineTo(p.x,yy(p.inferior)));x.closePath();x.fill();x.globalAlpha=1;
  x.strokeStyle=color;x.lineWidth=2;x.beginPath();let started=false;points.forEach(p=>{if(!p){started=false;return}if(started)x.lineTo(p.x,yy(p.estimado));else x.moveTo(p.x,yy(p.estimado));started=true});x.stroke();valid.forEach(p=>{x.beginPath();x.arc(p.x,yy(p.estimado),3,0,Math.PI*2);x.fillStyle=color;x.fill()});
 });
 ch.labels.forEach((label,i)=>drawOneLabel(x,label,xx(i),h-pad.b+18));
}
function drawGroupRanking(c,ch){
 const w=Number(c.dataset.renderWidth)||c.clientWidth||600,dpr=devicePixelRatio||1,left=w*.49,right=52;
 let ctx=c.getContext('2d');ctx.font='11px Segoe UI';const lines=ch.labels.map(label=>chartExportLines(ctx,label,left-20)),steps=lines.map(a=>Math.max(32,a.length*14+12)),h=steps.reduce((a,b)=>a+b,0)+30;
 c.style.height=h+'px';c.width=w*dpr;c.height=h*dpr;ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.font='11px Segoe UI';let y=12;const vals=ch.datasets[0].values,max=Math.max(1,...vals);
 vals.forEach((v,i)=>{ctx.fillStyle='#526177';ctx.textAlign='right';lines[i].forEach((line,j)=>ctx.fillText(line,left-10,y+steps[i]/2+(j-(lines[i].length-1)/2)*14));let width=v/max*(w-left-right);ctx.fillStyle='#11a99a';ctx.fillRect(left,y+steps[i]/2-12,width,18);ctx.fillStyle='#526177';ctx.textAlign='left';ctx.fillText(Number(v).toLocaleString('es-EC',{maximumFractionDigits:2}),left+width+5,y+steps[i]/2+1);y+=steps[i]});
}
const drawChatChartBeforeForecast=drawChatChart;
function drawSemanticCartesian(c,ch){
 const w=Number(c.dataset.renderWidth)||c.clientWidth||600,dpr=devicePixelRatio||1,labels=ch.labels||[],ds=ch.datasets||[],horizontal=ch.type==='bar'&&ch.orientation==='horizontal';
 const valid=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
 const values=ds.flatMap(d=>d.values||[]).filter(valid).map(Number),low=Math.min(0,...values),high=Math.max(1,...values),range=high-low;
 const fmt=v=>Number(v).toLocaleString('es-EC',{maximumFractionDigits:2});
 let x=c.getContext('2d');x.font='10px Segoe UI';
 const left=horizontal?Math.min(w*.48,260):Math.max(58,...[low,high,low+range/2].map(v=>x.measureText(fmt(v)).width+15));
 const right=horizontal?55:18,plotWidth=w-left-right,step=plotWidth/Math.max(1,labels.length);
 const wrapped=labels.map(l=>{const date=/^(\d{4})-(\d{2})$/.exec(String(l));if(date&&!horizontal&&Number(date[2])>=1&&Number(date[2])<=12)return [['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][Number(date[2])-1],date[1]];return chartExportLines(x,l,horizontal?left-16:Math.max(20,step-8))});
 const bottom=horizontal?48:Math.max(60,...wrapped.map(a=>a.length*12+25));
 const rowHeight=Math.max(34,ds.length*10+12,...wrapped.map(a=>a.length*12+12)),h=horizontal?Math.max(320,labels.length*rowHeight+70):300+bottom;
 c.style.height=h+'px';c.width=w*dpr;c.height=h*dpr;x=c.getContext('2d');x.scale(dpr,dpr);x.font='10px Segoe UI';
 const top=25,plotHeight=h-top-bottom,yy=v=>h-bottom-(v-low)/range*plotHeight,xx=v=>left+(v-low)/range*plotWidth,cx=i=>left+(i+.5)*step;
 for(let i=0;i<=4;i++){const v=low+range*i/4;x.strokeStyle='#e1e7ed';x.lineWidth=1;x.beginPath();if(horizontal){x.moveTo(xx(v),top);x.lineTo(xx(v),h-bottom)}else{x.moveTo(left,yy(v));x.lineTo(w-right,yy(v))}x.stroke();x.fillStyle='#526177';x.textAlign=horizontal?'center':'right';x.fillText(fmt(v),horizontal?xx(v):left-8,horizontal?h-bottom+18:yy(v)+3)}
 x.textAlign='left';x.fillStyle='#526177';x.fillText(['currency','moneda'].includes(ch.value_format)?'USD':['percent','porcentaje'].includes(ch.value_format)?'%':'Valor',left,13);
 labels.forEach((l,i)=>{x.fillStyle='#526177';x.textAlign=horizontal?'right':'center';wrapped[i].forEach((line,j)=>x.fillText(line,horizontal?left-10:cx(i),horizontal?top+(i+.5)*plotHeight/labels.length+(j-(wrapped[i].length-1)/2)*12:h-bottom+18+j*12))});
 ds.forEach((d,j)=>{const color=d.color||chartColor(ch,j);x.strokeStyle=color;x.fillStyle=color;x.lineWidth=2;
  if(ch.type==='bar'){const slot=horizontal?plotHeight/Math.max(1,labels.length):step,bw=Math.min(22,slot/(ds.length+1));labels.forEach((_,i)=>{const v=d.values[i];if(!valid(v))return;if(horizontal){const y=top+i*slot+(slot-bw*ds.length)/2+j*bw;x.fillStyle=color;x.fillRect(Math.min(xx(0),xx(v)),y,Math.abs(xx(v)-xx(0)),Math.max(2,bw-2));x.fillStyle='#526177';x.textAlign='left';x.fillText(fmt(v),Math.min(w-right+5,xx(v)+5),y+bw-3)}else{const pos=left+i*step+(step-bw*ds.length)/2+j*bw;x.fillStyle=color;x.fillRect(pos,Math.min(yy(v),yy(0)),Math.max(2,bw-2),Math.abs(yy(v)-yy(0)))}});return}
  // Separate paths at missing values: neither a zero nor interpolation is implied.
  const segments=[];let segment=[];labels.forEach((_,i)=>{const v=d.values[i];if(valid(v))segment.push([cx(i),yy(Number(v))]);else if(segment.length){segments.push(segment);segment=[]}});if(segment.length)segments.push(segment);
  segments.forEach(points=>{if(ch.type==='area'){x.globalAlpha=.12;x.beginPath();x.moveTo(points[0][0],yy(0));points.forEach(p=>x.lineTo(...p));x.lineTo(points[points.length-1][0],yy(0));x.closePath();x.fill();x.globalAlpha=1}x.beginPath();points.forEach((p,i)=>i?x.lineTo(...p):x.moveTo(...p));x.stroke();points.forEach(p=>{x.beginPath();x.arc(...p,3,0,Math.PI*2);x.fill()})});
 });
}
drawChatChart=function(c,ch){if(ch.ranking)return drawGroupRanking(c,ch);if(ch.forecast&&['line','area'].includes(ch.type))return drawForecastSeries(c,ch);if(ch.semantic&&!ch.objective_visual&&!ch.forecast&&!ch.secondary_axis&&['line','area','bar'].includes(ch.type))return drawSemanticCartesian(c,ch);return drawChatChartBeforeForecast(c,ch)};
const chartLegendBeforeForecast=chartLegend;
chartLegend=function(ch){return chartLegendBeforeForecast(ch)+(ch.forecast&&['line','area'].includes(ch.type)?'<span><i style="background:#b8c9dc"></i>Banda de incertidumbre aproximada (95%, no validada como garantía)</span>':'')};

async function checkApplicationVersion(){
 try{const response=await fetch('/api/version',{cache:'no-store'});if(!response.ok)return;const {version}=await response.json();if(!window.APP_BUILD||version===window.APP_BUILD||document.querySelector('#versionNotice'))return;
 const note=document.createElement('div');note.id='versionNotice';note.setAttribute('role','status');note.style.cssText='position:fixed;bottom:12px;left:12px;right:12px;z-index:10000;background:#12384b;color:white;padding:16px;border-radius:10px';note.textContent='Hay una versión nueva. Conserva tu borrador y recarga la página antes de seguir probando. ';const button=document.createElement('button');button.textContent='Guardar borrador y actualizar';button.onclick=()=>{sessionStorage.setItem('nexo-pending-draft',document.querySelector('#question').value);location.reload()};note.append(button);document.body.append(note);
 }catch(error){console.debug('No se pudo comprobar la versión',error)}
}
const pendingDraft=sessionStorage.getItem('nexo-pending-draft');if(pendingDraft!==null){document.querySelector('#question').value=pendingDraft;sessionStorage.removeItem('nexo-pending-draft')}
setInterval(checkApplicationVersion,60000);window.addEventListener('focus',checkApplicationVersion);
// Share the readable boxplot renderer between chat and PNG exports.
drawBoxplotChart=function(x,ch,w,h){
 const pad={l:70,r:16,t:22,b:70},boxes=ch.boxes||[],values=boxes.flatMap(b=>[b.min,b.max,...(b.outliers||[])]).map(Number);
 const low=Math.min(0,...values),high=Math.max(1,...values),step=(w-pad.l-pad.r)/Math.max(1,boxes.length),y=v=>h-pad.b-(v-low)/(high-low)*(h-pad.t-pad.b);
 x.font='10px Segoe UI';
 for(let i=0;i<=4;i++){let v=low+(high-low)*i/4,yy=y(v);x.strokeStyle='#e5edf3';x.beginPath();x.moveTo(pad.l,yy);x.lineTo(w-pad.r,yy);x.stroke();x.textAlign='right';x.fillStyle='#526177';x.fillText(v.toLocaleString('es-EC',{maximumFractionDigits:2}),pad.l-8,yy+3)}
 x.textAlign='left';x.fillText('USD',pad.l,12);
 boxes.forEach((b,i)=>{let cx=pad.l+(i+.5)*step,bw=Math.min(54,step*.5);x.strokeStyle='#526177';x.lineWidth=1.5;x.beginPath();x.moveTo(cx,y(b.min));x.lineTo(cx,y(b.max));[b.min,b.max].forEach(v=>{x.moveTo(cx-bw/4,y(v));x.lineTo(cx+bw/4,y(v))});x.stroke();x.fillStyle='#11a99a88';x.strokeStyle='#11a99a';x.fillRect(cx-bw/2,y(b.q3),bw,y(b.q1)-y(b.q3));x.strokeRect(cx-bw/2,y(b.q3),bw,y(b.q1)-y(b.q3));x.strokeStyle='#ff9f68';x.lineWidth=3;x.beginPath();x.moveTo(cx-bw/2,y(b.median));x.lineTo(cx+bw/2,y(b.median));x.stroke();(b.outliers||[]).forEach(v=>{x.beginPath();x.arc(cx,y(v),3,0,Math.PI*2);x.fillStyle='#526177';x.fill()});
  x.fillStyle='#526177';x.textAlign='center';x.font='11px Segoe UI';let lines=[''];String(b.label).split(/\s+/).forEach(word=>{let last=lines.length-1,candidate=(lines[last]+' '+word).trim();if(x.measureText(candidate).width>step-8&&lines[last])lines.push(word);else lines[last]=candidate});lines.forEach((line,j)=>x.fillText(line,cx,h-pad.b+18+j*13));
 });
};
renderChat();
