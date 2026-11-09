// Mocker helper — 在 https://mocker.dronetag.app 分頁用 javascript_tool 整段執行（可重複執行，冪等）。
// 之後即可呼叫 await mk.ready() / mk.create({...}) / mk.list() / mk.end(id) 等。
// Token 不落地、不回傳：只存在頁面記憶體 window.__mkTok，由攔截頁面自己的 fetch 取得。
(() => {
  if (!window.__mkHooked) {
    window.__mkHooked = true;
    const of = window.fetch;
    window.fetch = function (input, init) {
      try {
        const h = (init && init.headers) || (input instanceof Request ? input.headers : null);
        const a = h ? (h instanceof Headers ? h.get('authorization') : (h.Authorization || h.authorization)) : null;
        if (a) window.__mkTok = a;
      } catch (e) {}
      return of.apply(this, arguments);
    };
  }

  const PRESETS = {
    neihu: { name: '臺北市內湖運動中心', lat: 25.0782, lon: 121.57503 }, // OSM way/196802634（agy 查，2026-11-09）
  };

  const api = async (method, path, body) => {
    if (!window.__mkTok) throw new Error('NO_TOKEN：先執行 mk.ready()（會開關一次建立視窗讓頁面送出帶 token 的請求）');
    const r = await fetch(path, {
      method,
      headers: { Authorization: window.__mkTok, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    const t = await r.text();
    let j = null; try { j = t ? JSON.parse(t) : null; } catch (e) {}
    if (!r.ok) throw new Error(`HTTP ${r.status} ${method} ${path}: ${t.slice(0, 400)}`);
    return j;
  };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // 檢查 token。拿不到時回 NO_TOKEN：用 computer 工具「真的」點一下地圖（開 Create Simulation 視窗，
  // 頁面會帶 token 打 /ui/engines），再按 Esc 關窗，然後重跑 mk.ready()。合成事件點不開視窗。
  async function ready() {
    if (window.__mkTok) {
      try { await api('GET', '/api/v1/simulations/'); return 'ready'; } catch (e) { window.__mkTok = null; }
    }
    for (let i = 0; i < 8 && !window.__mkTok; i++) await sleep(250);
    return window.__mkTok ? 'ready' : 'NO_TOKEN';
  }

  // 某引擎＋情境的表單定義（含可選 Sensor ID、UAS ID 下拉、timeout 選項、必填欄位）
  async function schema(engine, scenario = 'circle') {
    const j = await api('OPTIONS', `/api/v1/ui/simulations?scenario=${scenario}&engine=${engine}`);
    const P = j.properties;
    const out = { engine, scenario, required: j.required, fields: {} };
    for (const [k, v] of Object.entries(P)) {
      out.fields[k] = {
        title: v.title, default: v.default, enum: v.enum || v.anyOf?.find((x) => x.enum)?.enum,
        min: v.minimum ?? v.exclusiveMinimum, max: v.maximum, const: v.const,
      };
    }
    return out;
  }

  const shortId = () => 'FA' + Date.now().toString(36).toUpperCase().slice(-6);

  /**
   * 建立模擬。opts：
   *  engine: nri_via_live | nri_via_funnel | dri_via_funnel（必填）
   *  scenario: circle（預設）| random | realistic_survey
   *  at: 'neihu'（預設）或 {lat, lon}；alt（起點高度，預設 100）
   *  uas_id：不給時自動選（有下拉就取第一個，否則產生 1596F + 隨機）
   *  sensor_id：不給時自動取可選的第一個（dri 必填）
   *  radius（circle，預設 150）、speed（km/h，預設 30）
   *  passes/length/separation/altVar（survey，預設 5/200/10/3）
   *  tech（nri_via_funnel 傳輸技術，預設 bluetooth_long_range）
   *  timeout（900/1800/3600，預設 900）、interval（ms，預設 500）
   */
  async function create(opts = {}) {
    const engine = opts.engine; if (!engine) throw new Error('engine 必填');
    const scenario = opts.scenario || 'circle';
    const sc = await schema(engine, scenario);
    const F = sc.fields;
    const at = typeof opts.at === 'object' ? opts.at : PRESETS[opts.at || 'neihu'];
    const body = {
      simulator: engine, scenario,
      uas_id: opts.uas_id || F.uas_id?.enum?.[0] || ('1596F' + shortId()),
      origin_latitude: at.lat, origin_longitude: at.lon, origin_altitude: opts.alt ?? 100,
      interval_sim: opts.interval ?? 500, timeout: opts.timeout ?? 900,
    };
    if (F.sensor_id) body.sensor_id = opts.sensor_id || F.sensor_id.enum?.[0] || null;
    if (F.bt_mac_address && opts.bt_mac) body.bt_mac_address = opts.bt_mac;
    if (F.transmission_technology) body.transmission_technology = opts.tech || F.transmission_technology.default || 'bluetooth_long_range';
    if (scenario === 'circle') Object.assign(body, { radius_m: opts.radius ?? 150, speed_kmh: opts.speed ?? 30 });
    if (scenario === 'random') Object.assign(body, { speed_kmh: opts.speed ?? 30 });
    if (scenario === 'realistic_survey') Object.assign(body, {
      pass_count: opts.passes ?? 5, pass_length: opts.length ?? 200, separation: opts.separation ?? 10,
      altitude_variation: opts.altVar ?? 3, speed_kmh: opts.speed ?? 30,
    });
    for (const k of sc.required) if (body[k] === undefined || body[k] === null) throw new Error(`缺必填欄位 ${k}`);
    const res = await api('POST', '/api/v1/simulations/', body);
    return { sent: body, created: res };
  }

  const pick = (o, ks) => Object.fromEntries(ks.filter((k) => o && o[k] !== undefined).map((k) => [k, o[k]]));

  // 列出目前所有模擬的設定與即時狀態（扁平化，方便做表）
  async function list() {
    const sims = await api('GET', '/api/v1/simulations/');
    return (sims || []).map((s) => {
      const c = s.configuration || {}, sc = c.scenario || {}, o = sc.origin_location || {}, st = s.state || {};
      return {
        id: s.id, uas_id: c.uas_id, engine: c.simulator, scenario: sc.type, sensor_id: c.sensor_id,
        tech: c.transmission_technology, origin: o.latitude != null ? `${o.latitude}, ${o.longitude}, ${o.altitude} m` : null,
        params: pick(sc, ['radius_m', 'speed_kmh', 'pass_count', 'pass_length', 'separation', 'altitude_variation']),
        interval_ms: c.interval_sim, timeout_s: c.timeout, paused: c.paused, flight_id: c.flight_id,
        state: st,
      };
    });
  }

  const get = (uasId) => api('GET', `/api/v1/simulations/${encodeURIComponent(uasId)}/`);
  const pause = (uasId, paused = true) => api('PATCH', `/api/v1/simulations/${encodeURIComponent(uasId)}/configuration/`, { paused });
  // 注入狀態：可手動移動位置（location:{latitude,longitude,altitude}）、改電量等
  const setState = (uasId, patch) => api('PATCH', `/api/v1/simulations/${encodeURIComponent(uasId)}/state`, patch);
  // 路徑參數是 uas_id（不是 list 裡的 UUID id）。END FLIGHT＝kill=false（nri 會送 status past）；FORCE KILL＝kill=true
  const end = (uasId) => api('DELETE', `/api/v1/simulations/${encodeURIComponent(uasId)}/?kill=false`);
  const kill = (uasId) => api('DELETE', `/api/v1/simulations/${encodeURIComponent(uasId)}/?kill=true`);
  const endAll = async () => { const l = await list(); for (const s of l) await end(s.uas_id); return l.map((s) => s.uas_id); };
  const version = () => api('GET', '/api/v1/version');

  // 給人看的設定表（Markdown）
  async function table() {
    const l = await list();
    if (!l.length) return '（目前沒有執行中的模擬）';
    const rows = l.map((s) => {
      const st = s.state || {}, loc = st.location || {};
      return `| ${s.uas_id} | ${s.engine} | ${s.scenario} | ${s.sensor_id ?? '—'} | ${s.tech ?? '—'} | ${s.origin} | ${Object.entries(s.params).map(([k, v]) => `${k} ${v}`).join(', ')} | ${s.interval_ms} ms / ${s.timeout_s} s | ${s.paused ? '暫停' : '執行中'} | ${loc.latitude != null ? `${loc.latitude.toFixed(5)}, ${loc.longitude.toFixed(5)}, ${Math.round(loc.altitude)} m` : '—'} | ${st.battery_percentage ?? '—'}% |`;
    });
    return ['| UAS ID | 引擎 | 情境 | Sensor | 傳輸 | 起點 | 航線參數 | 間隔／逾時 | 狀態 | 目前位置 | 電量 |',
      '|---|---|---|---|---|---|---|---|---|---|---|', ...rows].join('\n');
  }

  window.mk = { PRESETS, ready, schema, create, list, table, get, pause, setState, end, kill, endAll, version, api };
  return 'mk loaded: ' + Object.keys(window.mk).join(', ');
})();
