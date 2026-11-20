// Static time-series data is generated from the versioned MIT Election Lab source.
// Configure window.ELECTORAL_API before this script to enable the live results API.
const API=(window.ELECTORAL_API||"").replace(/\/$/,""),$=id=>document.getElementById(id),fmt=new Intl.NumberFormat("en-US");
const names={president:"Presidência",senate:"Senado",house:"Câmara",governor:"Governador",state_house:"State House",state_senate:"State Senate"};
const palette={DEMOCRAT:"#70a7ff",REPUBLICAN:"#ff7777",LIBERTARIAN:"#e5c46a",GREEN:"#70d6a3",OTHER:"#b6a2d9"};let historyData=null;
async function request(path){const r=await fetch(API+path);if(!r.ok)throw Error("API "+r.status);return r.json()}
const statusLabel=s=>({certified:"Certificado",preliminary:"Preliminar",estimated:"Estimado",historical_final:"Histórico final"})[s]||s;
function renderSeries() {
 if (!historyData) return;
 const state = $("series-state").value;
 const metric = $("series-metric").value;
 const rows = state === "US" ? historyData.national : historyData.states.filter(x => x.state_po === state);
 const years = historyData.metadata.years;
 const parties = metric === "margin" ? ["DEMOCRATIC MARGIN"] : [...new Set(rows.map(x => x.party))].filter(Boolean).sort();
 const valueFor = (year, party) => {
  if (metric === "margin") {
   const dem = rows.find(z => Number(z.election_year) === Number(year) && z.party === "DEMOCRAT");
   const rep = rows.find(z => Number(z.election_year) === Number(year) && z.party === "REPUBLICAN");
   if (!dem || !rep || !Number(dem.total_votes)) return null;
   return (Number(dem.votes) - Number(rep.votes)) / Number(dem.total_votes) * 100;
  }
  const row = rows.find(z => Number(z.election_year) === Number(year) && z.party === party);
  if (!row) return null;
  return metric === "votes" ? Number(row.votes) : Number(row.vote_share) * 100;
 };
 const values = parties.flatMap(p => years.map(y => valueFor(y, p))).filter(Number.isFinite);
 if (!values.length) {
  $("timeseries-chart").innerHTML = '<text x="450" y="170" text-anchor="middle" class="chart-empty">Sem observações para esta seleção.</text>';
  return;
 }
 let min = metric === "margin" ? Math.floor(Math.min(...values) / 5) * 5 : 0;
 let max = metric === "votes" ? Math.max(...values) * 1.08 : Math.ceil(Math.max(...values) / 5) * 5;
 if (metric === "vote_share") max = Math.min(100, max);
 if (metric === "margin") { min = Math.min(min, 0); max = Math.max(max, 0); }
 if (max <= min) { min -= 1; max += 1; }
 const W = 900, H = 340, L = 76, R = 24, T = 24, B = 48;
 const plotW = W - L - R, plotH = H - T - B;
 const x = i => L + i / Math.max(years.length - 1, 1) * plotW;
 const y = v => T + (max - v) / (max - min) * plotH;
 let svg = "";
 for (let tick = 0; tick <= 4; tick++) {
  const v = min + (max - min) * tick / 4, yy = y(v);
  const label = metric === "votes" ? (v / 1e6).toFixed(1) + "M" : v.toFixed(0) + (metric === "margin" ? " p.p." : "%");
  svg += '<line x1="' + L + '" y1="' + yy + '" x2="' + (W-R) + '" y2="' + yy + '" class="chart-grid"/>';
  svg += '<text x="' + (L-12) + '" y="' + (yy+4) + '" text-anchor="end" class="chart-axis">' + label + '</text>';
 }
 if (metric === "margin") svg += '<line x1="' + L + '" y1="' + y(0) + '" x2="' + (W-R) + '" y2="' + y(0) + '" stroke="#eef4fb" stroke-opacity=".55" stroke-dasharray="5 5"/>';
 years.forEach((yr, i) => { svg += '<text x="' + x(i) + '" y="' + (H-16) + '" text-anchor="middle" class="chart-axis">' + yr + '</text>'; });
 parties.forEach(party => {
  let segment = [];
  const segments = [];
  years.forEach((yr, i) => {
   const value = valueFor(yr, party);
   if (Number.isFinite(value)) segment.push({x:x(i), y:y(value), yr, value});
   else if (segment.length) { segments.push(segment); segment = []; }
  });
  if (segment.length) segments.push(segment);
  segments.forEach(points => {
   const d = points.map((p, i) => (i ? "L" : "M") + p.x.toFixed(1) + " " + p.y.toFixed(1)).join(" ");
   const color = metric === "margin" ? "#e5c46a" : (palette[party] || "#b6a2d9");
   svg += '<path d="' + d + '" class="chart-line" stroke="' + color + '"/>';
   points.forEach(p => {
    const val = metric === "votes" ? fmt.format(Math.round(p.value)) : p.value.toFixed(2) + (metric === "margin" ? " p.p." : "%");
    svg += '<circle cx="' + p.x + '" cy="' + p.y + '" r="5" class="chart-dot" fill="' + color + '"><title>' + p.yr + " · " + party + ": " + val + '</title></circle>';
   });
  });
 });
 $("timeseries-chart").innerHTML = svg;
 $("series-legend").innerHTML = parties.map(p => '<span><i style="background:' + (metric === "margin" ? "#e5c46a" : (palette[p] || "#b6a2d9")) + '"></i>' + (p === "DEMOCRATIC MARGIN" ? "Margem Democrata − Republicana" : p) + '</span>').join("");
 $("series-description").textContent = (state === "US" ? "Estados Unidos" : state) + " · " + ({votes:"votos agregados por partido",vote_share:"participação nos votos totais reportados",margin:"diferença entre participação democrata e republicana"})[metric];
 $("series-footnote").textContent = "Fonte: MIT Election Data and Science Lab, county-level returns 2000–2024. total_votes é deduplicado por unidade territorial e ciclo. Margem = (votos Democratas − votos Republicanos) / total_votes × 100. A série não mede turnout da população elegível.";
}
async function loadHistory(){try{const response=await fetch("data/presidential-timeseries.json");if(!response.ok)throw Error("Dataset histórico ainda não publicado");historyData=await response.json();const states=[...new Set(historyData.states.map(x=>x.state_po))].sort();$("series-state").innerHTML='<option value="US">Estados Unidos</option>'+states.map(s=>'<option value="'+s+'">'+s+"</option>").join("");$("series-source").textContent="MIT Election Lab · V"+historyData.metadata.dataset_version;$("connection").textContent="Série histórica verificada · "+historyData.metadata.years[0]+"–"+historyData.metadata.years.at(-1);$("records").textContent=fmt.format(historyData.metadata.rows_silver);$("years").textContent=historyData.metadata.years.join(", ");$("offices").textContent="1 · Presidência";$("certified").textContent="Fonte histórica";renderSeries()}catch(e){$("connection").textContent="Série histórica não publicada";$("timeseries-chart").innerHTML='<text x="450" y="170" text-anchor="middle" class="chart-empty">Execute o workflow Refresh electoral datasets para publicar os dados.</text>';console.error(e)}}
async function results(){if(!API)return;try{const p=new URLSearchParams();if($("year").value)p.set("year",$("year").value);if($("office").value)p.set("office",$("office").value);const d=await request("/v1/results?"+p);$("result-count").textContent=fmt.format(d.items.length)+" observações";$("results").innerHTML=d.items.length?d.items.map(r=>'<tr><td>'+r.election_year+"</td><td>"+(names[r.office]||r.office)+"</td><td>"+r.geography_name+"</td><td>"+r.candidate+"</td><td>"+(r.party||"—")+"</td><td>"+fmt.format(r.votes)+"</td><td>"+statusLabel(r.result_status)+"</td></tr>").join(""):'<tr><td colspan="7" class="empty">Nenhum resultado para os filtros.</td></tr>'}catch(e){$("results").innerHTML='<tr><td colspan="7" class="empty">Falha ao consultar resultados. Verifique API e CORS.</td></tr>'}}
$("refresh").addEventListener("click",()=>{loadHistory();if(API)results()});$("series-state").addEventListener("change",renderSeries);$("series-metric").addEventListener("change",renderSeries);$("year").addEventListener("change",results);$("office").addEventListener("change",results);loadHistory();if(API)results();else $("result-count").textContent="API não configurada · série histórica estática";

// House returns are a separate dataset and are not mixed with presidential contests.
let houseData = null;
function renderHouse() {
 if (!houseData) return;
 const year = Number($("house-year").value);
 const state = $("house-state").value;
 const rows = houseData.states
  .filter(row => Number(row.election_year) === year && row.state_po === state)
  .sort((a,b) => Number(b.votes) - Number(a.votes));
 $("house-results").innerHTML = rows.length
  ? rows.map(row => '<tr><td>' + row.party + '</td><td>' + fmt.format(Number(row.votes)) + '</td><td>' + (Number(row.vote_share) * 100).toFixed(2) + '%</td></tr>').join("")
  : '<tr><td colspan="3" class="empty">Sem observações para esta seleção.</td></tr>';
 $("house-footnote").textContent = "Fonte: MIT Election Data and Science Lab · " + houseData.metadata.version + ". " + houseData.metadata.contests + " contests distritais no Silver; " + houseData.metadata.missing_candidate_votes_excluded + " linhas sem votos de candidato foram excluídas de Silver, sem imputação de zero. A tabela resume apenas eleições gerais regulares.";
}
async function loadHouse() {
 try {
  const response = await fetch("data/house-timeseries.json");
  if (!response.ok) throw Error("Dataset House ainda não publicado");
  houseData = await response.json();
  const years = [...new Set(houseData.states.map(row => Number(row.election_year)))].sort((a,b) => b-a);
  const states = [...new Map(houseData.states.map(row => [row.state_po, row.state])).entries()].sort((a,b) => a[1].localeCompare(b[1]));
  $("house-year").innerHTML = years.map(year => '<option value="' + year + '">' + year + '</option>').join("");
  $("house-state").innerHTML = states.map(([code,name]) => '<option value="' + code + '">' + name + ' (' + code + ')</option>').join("");
  $("house-source").textContent = "MEDSL · " + houseData.metadata.version;
  $("offices").textContent = "2 · Presidência e Câmara";
  $("house-year").addEventListener("change", renderHouse);
  $("house-state").addEventListener("change", renderHouse);
  renderHouse();
 } catch (error) {
  $("house-results").innerHTML = '<tr><td colspan="3" class="empty">Dataset da Câmara indisponível. Execute Refresh electoral datasets.</td></tr>';
  console.error(error);
 }
}
loadHouse();


// Senate statewide returns: regular general elections are aggregated separately
// from special elections and runoffs; the source's TOTAL mode avoids double-counting.
let senateData = null;
function renderSenate() {
 if (!senateData) return;
 const year = Number($("senate-year").value);
 const state = $("senate-state").value;
 const rows = senateData.states
  .filter(row => Number(row.election_year) === year && row.state_po === state)
  .sort((a,b) => Number(b.votes) - Number(a.votes));
 $("senate-results").innerHTML = rows.length
  ? rows.map(row => '<tr><td>' + row.party + '</td><td>' + fmt.format(Number(row.votes)) + '</td><td>' + (Number(row.vote_share) * 100).toFixed(2) + '%</td></tr>').join("")
  : '<tr><td colspan="3" class="empty">Sem observações para esta seleção.</td></tr>';
 $("senate-footnote").textContent = "Fonte: MIT Election Data and Science Lab · " + senateData.metadata.version + ". " + senateData.metadata.contests + " contests no Silver; " + senateData.metadata.missing_candidate_votes_excluded + " linhas sem votos foram excluídas. O painel agrega apenas eleições gerais regulares e usa as linhas TOTAL para evitar dupla contagem de modos de votação.";
}
async function loadSenate() {
 try {
  const response = await fetch("data/senate-timeseries.json");
  if (!response.ok) throw Error("Dataset Senate ainda não publicado");
  senateData = await response.json();
  const years = [...new Set(senateData.states.map(row => Number(row.election_year)))].sort((a,b) => b-a);
  const states = [...new Map(senateData.states.map(row => [row.state_po, row.state])).entries()].sort((a,b) => a[1].localeCompare(b[1]));
  $("senate-year").innerHTML = years.map(year => '<option value="' + year + '">' + year + '</option>').join("");
  $("senate-state").innerHTML = states.map(([code,name]) => '<option value="' + code + '">' + name + ' (' + code + ')</option>').join("");
  $("senate-source").textContent = "MEDSL · " + senateData.metadata.version + " · " + fmt.format(senateData.metadata.silver_rows) + " registros";
  $("offices").textContent = "3 · Presidência, Senado e Câmara";
  $("senate-year").addEventListener("change", renderSenate);
  $("senate-state").addEventListener("change", renderSenate);
  renderSenate();
 } catch (error) {
  $("senate-results").innerHTML = '<tr><td colspan="3" class="empty">Dataset do Senado indisponível. Execute Refresh electoral datasets.</td></tr>';
  console.error(error);
 }
}
loadSenate();


// State executive and legislative contests from MEDSL 2024 precinct archives.
let stateOfficeData = null;
function stateOfficeRows() {
 if (!stateOfficeData) return [];
 const office = $("state-office-type").value;
 const state = $("state-office-state").value;
 const district = $("state-office-district").value;
 return stateOfficeData.results.filter(row =>
  row.office === office && row.state_po === state &&
  (!district || String(row.district || "") === district)
 ).sort((a,b) => Number(b.votes) - Number(a.votes));
}
function renderStateOffices() {
 if (!stateOfficeData) return;
 const rows = stateOfficeRows();
 $("state-office-results").innerHTML = rows.length
  ? rows.map(row => '<tr><td>' + (row.district || "Estadual") + '</td><td>' + (row.party || "Sem classificação") + '</td><td>' + fmt.format(Number(row.votes)) + '</td><td>' + (Number(row.vote_share) * 100).toFixed(2) + '%</td></tr>').join("")
  : '<tr><td colspan="4" class="empty">Não há observações para este cargo, estado e distrito em 2024.</td></tr>';
 $("state-office-footnote").textContent =
  "Fonte: MIT Election Data and Science Lab · commit " + stateOfficeData.metadata.repository_commit.slice(0, 12) +
  ". " + fmt.format(stateOfficeData.metadata.silver_rows) + " registros Silver e " +
  stateOfficeData.metadata.contests + " contests. Arquivos de 51 estados/DC verificados por Git blob SHA-1; " +
  stateOfficeData.metadata.missing_votes_excluded + " votos ausentes e " +
  stateOfficeData.metadata.negative_votes_excluded + " valores negativos não entram em Silver. " +
  "Somente mode=TOTAL; ausência de distrito impede classificação distrital e é excluída.";
}
function updateStateOfficeDistricts() {
 if (!stateOfficeData) return;
 const office = $("state-office-type").value;
 const state = $("state-office-state").value;
 const districts = [...new Set(stateOfficeData.results
  .filter(row => row.office === office && row.state_po === state && row.district)
  .map(row => String(row.district)))].sort((a,b) => a.localeCompare(b,undefined,{numeric:true}));
 $("state-office-district").innerHTML = '<option value="">Todos</option>' +
  districts.map(d => '<option value="' + d + '">' + d + '</option>').join("");
}
async function loadStateOffices() {
 try {
  const response = await fetch("data/state-offices-2024.json");
  if (!response.ok) throw Error("State office dataset not published");
  stateOfficeData = await response.json();
  const stateNames = new Map();
  for (const row of stateOfficeData.results) {
   if (!stateNames.has(row.state_po)) stateNames.set(row.state_po, row.state_fips);
  }
  const states = [...stateNames.keys()].sort();
  $("state-office-state").innerHTML = states.map(code =>
   '<option value="' + code + '">' + code + '</option>'
  ).join("");
  $("state-office-source").textContent = "MEDSL · 2024 · " +
   fmt.format(stateOfficeData.metadata.silver_rows) + " registros";
  $("state-office-type").addEventListener("change", () => {
   updateStateOfficeDistricts();
   renderStateOffices();
  });
  $("state-office-state").addEventListener("change", () => {
   updateStateOfficeDistricts();
   renderStateOffices();
  });
  $("state-office-district").addEventListener("change", renderStateOffices);
  updateStateOfficeDistricts();
  renderStateOffices();
  $("offices").textContent = "6 · Presidência, Senado, Câmara e estaduais";
 } catch (error) {
  $("state-office-results").innerHTML =
   '<tr><td colspan="4" class="empty">Dados estaduais indisponíveis. Execute Refresh electoral datasets.</td></tr>';
  console.error(error);
 }
}
loadStateOffices();
