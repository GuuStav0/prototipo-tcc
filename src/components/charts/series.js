// Prepara os pontos da API ({ t: ISO, v }) para os gráficos.
//
// - Converte o tempo para número (eixo X numérico, proporcional ao tempo real).
// - Remove janelas vazias em lacunas curtas (até `maxGapMs`): quando o intervalo de coleta
//   é maior que a janela do gráfico (ex.: histórico a cada 5 min em janelas de 2 min),
//   a linha seguiria quebrada em pontos soltos.
// - Lacunas longas (ex.: servidor fora do ar) continuam visíveis como quebra na linha.
// - O primeiro e o último ponto são mantidos para o eixo cobrir o período inteiro.
export const MAX_GAP_MS = 10 * 60 * 1000;

export function toChartData(points, maxGapMs = MAX_GAP_MS) {
  if (!points?.length) return [];
  const pts = points.map((p) => ({ ts: Date.parse(p.t), v: p.v }));
  const out = [];
  let i = 0;
  while (i < pts.length) {
    if (pts[i].v !== null) {
      out.push(pts[i]);
      i++;
      continue;
    }
    // sequência de janelas vazias: de i até j-1
    let j = i;
    while (j < pts.length && pts[j].v === null) j++;
    const before = out.length ? out.at(-1).ts : null;
    const after = j < pts.length ? pts[j].ts : null;
    const short = before !== null && after !== null && after - before <= maxGapMs;
    if (!short) {
      out.push(pts[i]); // mantém um nulo para quebrar a linha
      if (j - 1 > i && j === pts.length) out.push(pts[j - 1]); // fim do período sem dados
    }
    i = j;
  }
  return out;
}

// Estilo comum dos eixos e tooltips
export const AXIS_TICK = { fill: "#6B7690", fontSize: 11, fontFamily: "JetBrains Mono, monospace" };
export const TOOLTIP_STYLE = {
  background: "#111726", border: "1px solid #263144", borderRadius: 8, fontFamily: "JetBrains Mono, monospace", fontSize: 12,
};
