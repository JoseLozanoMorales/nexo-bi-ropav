const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8');
const renderer=source.slice(source.indexOf('function drawChatChart('),source.indexOf('function drawStackedChart('));
for(const width of [240,320,600]){
 const labels=[],ctx={scale(){},fillRect(){},measureText:t=>({width:String(t).length*6}),fillText(text,x,y){labels.push({text,x,align:this.textAlign});}};
 const scope={devicePixelRatio:1};vm.createContext(scope);vm.runInContext(renderer,scope);
 for(const format of ['currency','number']){
  labels.length=0;
  scope.drawChatChart({style:{},dataset:{renderWidth:width},getContext:()=>ctx},{
   type:'bar',orientation:'horizontal',value_format:format,labels:['Femenino','Masculino'],
   datasets:[{values:[21651.77,19823.56],color:'#11a99a'}]});
  const values=labels.filter(l=>l.align==='left');
  assert.equal(values.length,2);
  for(const label of values){assert.ok(label.x>=0);assert.ok(label.x+ctx.measureText(label.text).width<=width,JSON.stringify(label));}
 }
}
console.log('6 pruebas de etiquetas numéricas sin recorte: OK');
