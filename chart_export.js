/* Export the current chart specification, without querying the AI or database. */
function chartExportLines(ctx, text, width) {
  const lines = [];
  for (const paragraph of String(text || '').split(/\n/)) {
    let line = '';
    for (const char of paragraph) {
      if (line && ctx.measureText(line + char).width > width) {
        const space = line.lastIndexOf(' ');
        if (space > 0) {
          lines.push(line.slice(0, space));
          line = line.slice(space + 1) + char;
        } else {
          lines.push(line);
          line = char;
        }
      } else line += char;
    }
    if (line.trim()) lines.push(line.trim());
  }
  return lines;
}

function chartExportCanvas(chart, exportWidth = 1200) {
  const width = exportWidth, margin = width < 800 ? 24 : 48, inner = width - margin * 2;
  const plot = document.createElement('canvas');
  plot.dataset.renderWidth = String(inner);
  // Use the same renderer (including objective-specific overrides) as the chat.
  const estimatedHeight = dashboardChartHeight(chart);
  if (estimatedHeight > 12000) throw new Error('El gráfico es demasiado alto para exportarlo en una sola imagen. Reduce las filas o categorías.');
  drawChatChart(plot, chart);
  const plotHeight = parseFloat(plot.style.height) || estimatedHeight;
  const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
  if (!ctx || !plot.width || !plot.height) throw new Error('No se pudo dibujar el gráfico.');
  ctx.font = 'bold 26px Arial';
  const title = chartExportLines(ctx, chart.title || 'Gráfico', inner);
  ctx.font = '16px Arial';
  const description = chartExportLines(ctx, chart.description, inner);
  const source = chartExportLines(ctx, 'Fuente: ' + (chart.source || 'No especificada'), inner);
  const legendNode = document.createElement('div');
  if (!['table', 'matrix'].includes(chart.type)) legendNode.innerHTML = chartLegend(chart);
  const legend = [...legendNode.querySelectorAll('span')].map(node => ({
    lines: chartExportLines(ctx, node.textContent, inner - 26),
    color: node.querySelector('i')?.style.backgroundColor || '#11a99a'
  }));
  const top = margin + title.length * 32 + 16 + description.length * 23 + 20;
  const legendHeight = legend.reduce((sum, entry) => sum + entry.lines.length * 22 + 8, 0);
  const height = Math.ceil(top + plotHeight + 24 + legendHeight + source.length * 22 + margin);
  if (height > 14000) throw new Error('La imagen sería demasiado grande. Reduce las filas o categorías.');
  canvas.width = width;
  canvas.height = height;
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, width, height);
  let y = margin;
  const write = (lines, font, color, step, x = margin) => {
    ctx.font = font; ctx.fillStyle = color;
    for (const line of lines) {ctx.fillText(line, x, y); y += step;}
  };
  write(title, 'bold 26px Arial', '#12384b', 32);
  y += 16;
  write(description, '16px Arial', '#526177', 23);
  ctx.drawImage(plot, margin, top, inner, plotHeight);
  y = top + plotHeight + 24;
  for (const entry of legend) {
    ctx.fillStyle = entry.color; ctx.fillRect(margin, y - 12, 12, 12);
    write(entry.lines, '16px Arial', '#526177', 22, margin + 26);
    y += 8;
  }
  write(source, '16px Arial', '#526177', 22);
  return canvas;
}

async function downloadChartPNG(chart) {
  const canvas = chartExportCanvas(chart);
  const blob = await new Promise((resolve, reject) => canvas.toBlob(
    data => data ? resolve(data) : reject(new Error('El navegador no pudo crear el PNG.')), 'image/png'));
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.download = (String(chart.title || 'grafico').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '').slice(0, 100) || 'grafico') + '.png';
  link.href = url;
  try {document.body.appendChild(link); link.click();}
  finally {link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);}
}

const attachChartBeforeExport = attachChart;
attachChart = function(bubble, chart) {
  attachChartBeforeExport(bubble, chart);
  const box = bubble.lastElementChild;
  const actions = document.createElement('div'), button = document.createElement('button');
  actions.className = 'chart-export-actions';
  button.type = 'button'; button.className = 'primary chart-download';
  button.textContent = 'Descargar PNG';
  button.setAttribute('aria-label', 'Descargar PNG: ' + (chart.title || 'gráfico'));
  const status = document.createElement('small');
  status.setAttribute('role', 'status');
  actions.append(button, status); box.appendChild(actions);
  button.addEventListener('click', async () => {
    button.disabled = true; button.textContent = 'Preparando…'; status.textContent = '';
    try {await downloadChartPNG(chart);}
    catch (error) {console.error('Error al exportar gráfico', error); status.textContent = error.message || 'No se pudo descargar el gráfico. Inténtalo de nuevo.';}
    finally {button.disabled = false; button.textContent = 'Descargar PNG';}
  });
};
// Restored conversations also get the download control.
renderChat();
