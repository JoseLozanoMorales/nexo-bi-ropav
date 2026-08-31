/* Only table syntax is interpreted. All content stays text, never HTML. */
(function(root){
 function cells(line){
  let value=line.trim();if(value.startsWith('|'))value=value.slice(1);if(value.endsWith('|')&&!value.endsWith('\\|'))value=value.slice(0,-1);
  const result=[];let cell='';
  for(let i=0;i<value.length;i++){if(value[i]==='\\'&&value[i+1]==='|'){cell+='|';i++}else if(value[i]==='|'){result.push(cell.trim());cell=''}else cell+=value[i]}
  result.push(cell.trim());return result;
 }
 function parse(text){
  const lines=String(text).split(/\r?\n/),blocks=[];let plain=[],fenced=false;
  const flush=()=>{if(plain.length){blocks.push({type:'text',text:plain.join('\n')});plain=[]}};
  for(let i=0;i<lines.length;i++){
   if(/^\s*(```|~~~)/.test(lines[i])){fenced=!fenced;plain.push(lines[i]);continue}
   const headers=cells(lines[i]),separator=i+1<lines.length?cells(lines[i+1]):[];
   if(!fenced&&lines[i].includes('|')&&headers.length>=2&&separator.length===headers.length&&separator.every(s=>/^:?-{3,}:?$/.test(s))){
    const rows=[];let next=i+2;
    while(next<lines.length&&lines[next].includes('|')&&lines[next].trim()){
     const row=cells(lines[next]);if(row.length!==headers.length)break;rows.push(row);next++;
    }
    if(rows.length){flush();blocks.push({type:'table',headers,rows});i=next-1;continue}
   }
   plain.push(lines[i]);
  }
  flush();return blocks;
 }
 function render(container,text){
  const doc=container.ownerDocument;container.replaceChildren();
  for(const block of parse(text)){
   if(block.type==='text'){const part=doc.createElement('div');part.className='chat-text';part.textContent=block.text;container.appendChild(part);continue}
   container.classList.add('has-table');
   const wrap=doc.createElement('div');wrap.className='chat-table-scroll';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Tabla de resultados; desplaza horizontalmente para ver todas las columnas');
   const table=doc.createElement('table'),head=doc.createElement('thead'),headRow=doc.createElement('tr'),body=doc.createElement('tbody');
   for(const title of block.headers){const cell=doc.createElement('th');cell.scope='col';cell.textContent=title;headRow.appendChild(cell)}head.appendChild(headRow);
   for(const values of block.rows){const row=doc.createElement('tr');if(/^\*{0,2}total\*{0,2}$/i.test(values[0]))row.className='chat-table-total';
    values.forEach((value,index)=>{const cell=doc.createElement(index===0?'th':'td');if(index===0)cell.scope='row';cell.textContent=value;row.appendChild(cell)});body.appendChild(row);
   }
   table.append(head,body);wrap.appendChild(table);container.appendChild(wrap);
  }
 }
 root.ChatTables={parse,render};
 if(typeof module!=='undefined'&&module.exports)module.exports=root.ChatTables;
})(typeof window!=='undefined'?window:globalThis);
