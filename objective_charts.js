/* Functional Power BI objective visuals: accessible tables, signed axes and treemap. */
function objectiveValue(value, format) {
  if (value === null || value === undefined) return 'N/D';
  if (format === 'text') return String(value);
  return dashboardValue({value, format});
}
function objectiveHeight(ch) {
  if (['table','matrix'].includes(ch.type)) return 60+(ch.rows||[]).length*30;
  if (ch.orientation==='horizontal') return Math.max(320,(ch.labels||[]).length*42+60);
  return 340;
}
function attachObjectiveTable(bubble,ch) {
  const box=document.createElement('div');box.className='chat-chart objective-table';
  const h=document.createElement('h3');h.textContent=ch.title;box.appendChild(h);
  const p=document.createElement('p');p.className='chart-description';p.textContent=ch.description;box.appendChild(p);
  const scroll=document.createElement('div');scroll.className='objective-table-scroll';scroll.tabIndex=0;
  const table=document.createElement('table');const head=table.createTHead().insertRow();
  ch.columns.forEach(col=>{const th=document.createElement('th');th.scope='col';th.textContent=col.label;head.appendChild(th)});
  const body=table.createTBody();(ch.rows||[]).forEach(row=>{const tr=body.insertRow();ch.columns.forEach(col=>{const td=tr.insertCell();td.textContent=objectiveValue(row[col.key],col.format)})});
  if(!ch.rows.length){const td=body.insertRow().insertCell();td.colSpan=ch.columns.length;td.textContent='Sin datos para estos filtros.'}
  scroll.appendChild(table);box.appendChild(scroll);
  const source=document.createElement('small');source.textContent='Fuente: '+ch.source;box.appendChild(source);bubble.appendChild(box);
}
function objectiveText(ctx,text,x,y,width){ctx.save();ctx.beginPath();ctx.rect(x,y-13,Math.max(width,0),19);ctx.clip();ctx.fillText(String(text),x,y);ctx.restore()}
function drawObjectiveChart(canvas,ch){
  const w=Number(canvas.dataset.renderWidth)||canvas.clientWidth||600,h=objectiveHeight(ch),dpr=window.devicePixelRatio||1;
  canvas.style.height=h+'px';canvas.width=w*dpr;canvas.height=h*dpr;
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.font='11px Segoe UI';ctx.fillStyle='#526177';
  if(['table','matrix'].includes(ch.type)){
    const cols=ch.columns||[],cw=w/Math.max(cols.length,1);ctx.fillStyle='#e8f7f5';ctx.fillRect(0,0,w,40);
    cols.forEach((col,i)=>{ctx.fillStyle='#12384b';objectiveText(ctx,col.label,i*cw+5,24,cw-10)});
    (ch.rows||[]).forEach((row,j)=>{const y=40+j*30;ctx.fillStyle=j%2?'#f4f7fa':'#fff';ctx.fillRect(0,y,w,30);cols.forEach((col,i)=>{ctx.fillStyle='#526177';objectiveText(ctx,objectiveValue(row[col.key],col.format),i*cw+5,y+20,cw-10)})});return;
  }
  if(ch.type==='treemap'){
    const groups=new Map();(ch.nodes||[]).forEach(n=>{if(n.value>0){if(!groups.has(n.group))groups.set(n.group,[]);groups.get(n.group).push(n)}});
    const total=[...groups.values()].flat().reduce((s,n)=>s+n.value,0);let left=0,index=0;
    if(!total){ctx.fillText('Sin ingresos positivos para representar áreas.',15,35);return}
    groups.forEach((nodes,group)=>{const sum=nodes.reduce((s,n)=>s+n.value,0),gw=w*sum/total,color=ch.colors[index++%ch.colors.length];let top=30;
      ctx.fillStyle='#12384b';objectiveText(ctx,group,left+5,20,gw-10);
      nodes.forEach(n=>{const nh=(h-32)*n.value/sum;ctx.fillStyle=color;ctx.fillRect(left+2,top+2,Math.max(0,gw-4),Math.max(0,nh-4));ctx.fillStyle='#10243e';if(nh>25)objectiveText(ctx,n.label,left+7,top+18,gw-14);if(nh>44)objectiveText(ctx,objectiveValue(n.value,'currency'),left+7,top+37,gw-14);top+=nh});left+=gw});return;
  }
  const labels=ch.labels||[],sets=ch.datasets||[];
  if(!labels.length||!sets.length){ctx.fillText('Sin datos para estos filtros.',15,35);return}
  if(ch.type==='pie'){
    const values=sets[0].values.map(v=>Math.max(0,Number(v)||0)),total=values.reduce((a,b)=>a+b,0);if(!total){ctx.fillText('Sin datos para representar proporciones.',15,35);return}
    let angle=-Math.PI/2;const radius=Math.min(w,h)*.35;values.forEach((value,i)=>{const next=angle+value/total*2*Math.PI;ctx.beginPath();ctx.moveTo(w/2,h/2);ctx.arc(w/2,h/2,radius,angle,next);ctx.closePath();ctx.fillStyle=ch.colors[i%ch.colors.length];ctx.fill();if(value/total>.04){ctx.fillStyle='#10243e';ctx.textAlign='center';ctx.fillText((100*value/total).toFixed(1)+'%',w/2+Math.cos((angle+next)/2)*radius*.7,h/2+Math.sin((angle+next)/2)*radius*.7)}angle=next});return;
  }
  const values=sets.flatMap(d=>d.values).filter(v=>v!==null&&v!==undefined).map(Number),min=Math.min(0,...values),max=Math.max(0,...values),span=max-min||1;
  const horizontal=ch.orientation==='horizontal',pad={l:horizontal?135:70,r:15,t:20,b:70},pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;
  const yp=v=>pad.t+(max-v)/span*ph,xp=v=>pad.l+(v-min)/span*pw;
  ctx.font='10px Segoe UI';
  for(let i=0;i<=4;i++){const v=min+span*i/4;ctx.strokeStyle='#e3eaf0';ctx.beginPath();
    if(horizontal){ctx.moveTo(xp(v),pad.t);ctx.lineTo(xp(v),h-pad.b);ctx.fillStyle='#526177';ctx.textAlign='center';ctx.fillText(v.toLocaleString('es-CO',{maximumFractionDigits:1})+(ch.value_format==='percent'?'%':''),xp(v),h-pad.b+20)}
    else{ctx.moveTo(pad.l,yp(v));ctx.lineTo(w-pad.r,yp(v));ctx.fillStyle='#526177';ctx.textAlign='right';ctx.fillText(v.toLocaleString('es-CO',{maximumFractionDigits:1})+(ch.value_format==='percent'?'%':''),pad.l-6,yp(v)+4)}ctx.stroke()}
  const step=(horizontal?ph:pw)/labels.length,bw=Math.min(28,step*.75/sets.length);
  const tickStride=ch.type==='line'?Math.max(1,Math.ceil(labels.length/Math.max(2,Math.floor(pw/75)))):1;
  labels.forEach((label,i)=>{if(i%tickStride!==0&&i!==labels.length-1)return;ctx.fillStyle='#526177';if(horizontal){ctx.textAlign='right';ctx.fillText(String(label).slice(0,22),pad.l-8,pad.t+(i+.5)*step+4)}else{ctx.save();ctx.translate(pad.l+(i+.5)*step,h-pad.b+15);ctx.rotate(-.45);ctx.textAlign='right';ctx.fillText(String(label),0,0);ctx.restore()}});
  sets.forEach((set,j)=>{ctx.fillStyle=set.color;ctx.strokeStyle=set.color;ctx.lineWidth=2;let connected=false;ctx.beginPath();set.values.forEach((value,i)=>{
    if(value===null||value===undefined){connected=false;return}const v=Number(value),cx=pad.l+(i+.5)*step,cy=yp(v);
    if(ch.type==='line'){if(connected)ctx.lineTo(cx,cy);else ctx.moveTo(cx,cy);connected=true}
    else if(horizontal){const y=pad.t+(i+.5)*step+(j-sets.length/2)*bw;ctx.fillRect(Math.min(xp(0),xp(v)),y,Math.abs(xp(v)-xp(0)),Math.max(1,bw-2))}
    else{const x=cx+(j-sets.length/2)*bw;ctx.fillRect(x,Math.min(yp(0),cy),Math.max(1,bw-2),Math.abs(cy-yp(0)))}});if(ch.type==='line')ctx.stroke()});
}

/* Keep existing generic charts untouched. Hooks also apply to saved chat and PNG. */
const baseObjectiveDraw=drawChatChart,baseObjectiveAttach=attachChart,baseObjectiveDashboard=attachDashboard,
      baseObjectiveHeight=dashboardChartHeight,baseObjectiveValue=dashboardValue;
drawChatChart=function(c,ch){return ch.objective_visual?drawObjectiveChart(c,ch):baseObjectiveDraw(c,ch)};
attachChart=function(bubble,ch){if(ch.objective_visual&&['table','matrix'].includes(ch.type))return attachObjectiveTable(bubble,ch);baseObjectiveAttach(bubble,ch);if(ch.objective_visual)bubble.lastElementChild.classList.add('objective-visual-chart')};
dashboardChartHeight=function(ch){return ch.objective_visual?objectiveHeight(ch):baseObjectiveHeight(ch)};
dashboardValue=function(item){return item.value===null||item.value===undefined?'N/D':baseObjectiveValue(item)};
attachDashboard=function(bubble,spec){
  baseObjectiveDashboard(bubble,spec);if(!spec.objective_id)return;
  const root=bubble.lastElementChild,section=document.createElement('section');section.className='objective-context';
  const p=document.createElement('p');p.textContent=spec.objective;section.appendChild(p);
  const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Cómo se construye: medidas, criterios y límites';details.appendChild(summary);
  const list=document.createElement('ul');(spec.warnings||[]).forEach(note=>{const li=document.createElement('li');li.textContent=note;list.appendChild(li)});details.appendChild(list);
  Object.entries(spec.measure_definitions||{}).forEach(([name,formula])=>{const p=document.createElement('p');p.textContent=name+': '+formula;details.appendChild(p)});section.appendChild(details);
  root.querySelector('.dashboard-head').after(section);
  const download=document.createElement('button');download.className='primary';download.textContent='Descargar definición JSON';download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(spec,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='objetivo-'+spec.objective_id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};section.appendChild(download);
};
const baseObjectiveDownload=downloadDashboard;
downloadDashboard=function(spec){
  if(!spec.objective_id)return baseObjectiveDownload(spec);
  const width=1400,margin=48,gap=24,inner=width-2*margin,half=(inner-gap)/2,slots=[];
  let top=330,pending=null;
  for(const chart of spec.charts){
    const full=['table','matrix'].includes(chart.type),height=objectiveHeight(chart)+175;
    if(full){if(pending){top+=pending.height+gap;pending=null}slots.push({chart,x:margin,y:top,width:inner,height});top+=height+gap}
    else if(!pending){pending={chart,x:margin,y:top,width:half,height};slots.push(pending)}
    else{const rowHeight=Math.max(pending.height,height);pending.height=rowHeight;slots.push({chart,x:margin+half+gap,y:top,width:half,height:rowHeight});top+=rowHeight+gap;pending=null}
  }
  if(pending)top+=pending.height+gap;
  const footer=110+(spec.warnings||[]).length*50;
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=top+footer;const ctx=canvas.getContext('2d');
  ctx.fillStyle='#f4f7fa';ctx.fillRect(0,0,width,canvas.height);ctx.fillStyle='#12384b';ctx.fillRect(0,0,width,165);
  dashboardCanvasText(ctx,spec.title,margin,45,'bold 28px Arial','#fff');ctx.font='14px Arial';ctx.fillStyle='#8de8dd';dashboardWrapText(ctx,spec.subtitle,margin,75,inner,18,2);
  ctx.fillStyle='#fff';dashboardWrapText(ctx,spec.objective,margin,110,inner,19,3);
  const kw=(inner-12*(spec.kpis.length-1))/spec.kpis.length;
  spec.kpis.forEach((k,i)=>{const x=margin+i*(kw+12);ctx.fillStyle='#fff';ctx.fillRect(x,185,kw,108);dashboardCanvasText(ctx,k.label,x+14,216,'bold 13px Arial','#526177');dashboardCanvasText(ctx,dashboardValue(k),x+14,256,'bold 22px Arial')});
  slots.forEach(slot=>{const {chart,x,y,width:cw,height}=slot;ctx.fillStyle='#fff';ctx.fillRect(x,y,cw,height);ctx.font='bold 17px Arial';ctx.fillStyle='#10243e';dashboardWrapText(ctx,chart.title,x+18,y+28,cw-36,20,2);ctx.font='12px Arial';ctx.fillStyle='#526177';dashboardWrapText(ctx,chart.description,x+18,y+65,cw-36,17,2);
    const image=document.createElement('canvas');image.dataset.renderWidth=String(cw-36);drawObjectiveChart(image,chart);ctx.drawImage(image,x+18,y+100,cw-36,objectiveHeight(chart));
    const entries=chart.type==='pie'?chart.labels.map((label,i)=>({label,color:chart.colors[i]})):chart.datasets||[];ctx.font='11px Arial';let lx=x+18;
    entries.forEach(entry=>{ctx.fillStyle=entry.color;ctx.fillRect(lx,y+height-46,9,9);dashboardCanvasText(ctx,entry.label,lx+14,y+height-38,'11px Arial','#526177');lx+=ctx.measureText(entry.label).width+34});
    dashboardCanvasText(ctx,'Fuente: '+chart.source,x+18,y+height-16,'10px Arial','#526177');
  });
  dashboardCanvasText(ctx,'Criterios y límites de esta recreación',margin,top+25,'bold 16px Arial');ctx.font='12px Arial';ctx.fillStyle='#526177';
  (spec.warnings||[]).forEach((note,i)=>dashboardWrapText(ctx,note,margin,top+52+i*50,inner,17,2));
  const a=document.createElement('a');a.download='objetivo-'+spec.objective_id+'.png';a.href=canvas.toDataURL('image/png');a.click();
};
// app.js restores chat at load; redraw once with objective-aware renderers.
renderChat();
