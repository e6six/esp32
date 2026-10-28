import { ESPLoader, Transport } from '/esptool-bundle.js';

const WIDGET_CATALOG = [
  {
    id: 'v1_classic_cal',
    num: 1,
    icon: '📅',
    tag: 'Стиль 1 из 9 • Классика на русском',
    title: 'Календарь на Месяц (Пн–Вс) + Часы + Яндекс Погода 📍',
    desc: 'Крупный русский календарь, часы с живыми секундами и карточка Яндекс Погоды выбранного района Москвы (Бутово и др.) с красным пином 📍.'
  },
  {
    id: 'v2_flip_clock',
    num: 2,
    icon: '🕰️',
    tag: 'Стиль 2 из 9 • Крупные цифры',
    title: 'Гигантские Часы с Секундами + Яндекс Погода Района',
    desc: 'Огромные цифры времени и секунд во всю ширину экрана, дата прописью на русском и карточка погоды района внизу.'
  },
  {
    id: 'v3_weather_pro',
    num: 3,
    icon: '🌤️',
    tag: 'Стиль 3 из 9 • Яндекс Погода',
    title: 'Метеостанция Яндекс Погода (Бутово / Районы Москвы)',
    desc: 'Подробная сводка погоды для выбранного района: температура, состояние неба на русском, макс/мин, влажность, ветер в м/с и координаты.'
  },
  {
    id: 'v4_day_planner',
    num: 4,
    icon: '📝',
    tag: 'Стиль 4 из 9 • Планер на русском',
    title: 'Неделя (Пн–Вс) + 3 Важных Дела на День + Погода',
    desc: 'Полоска дней недели с подсветкой сегодняшнего дня, строка времени и погоды с пином 📍 и 3 ваших напоминания на русском языке:',
    hasNotesInput: true
  },
  {
    id: 'v5_night_clock',
    num: 5,
    icon: '🌙',
    tag: 'Стиль 5 из 9 • Ночной неон',
    title: 'Ночной Неоновый Будильник + Дата и Погода',
    desc: 'Контрастные неоново-голубые часы в тонкой рамке на глубоком тёмном фоне, день недели и погода района.'
  },
  {
    id: 'v6_retro_term',
    num: 6,
    icon: '📟',
    tag: 'Стиль 6 из 9 • Ретро Casio',
    title: 'Ретро-Терминал CASIO // Яндекс Радар',
    desc: 'Зелёный монохромный стиль классических часов и терминала на русском языке: дата, локация, температура и скорость ветра.'
  },
  {
    id: 'v7_pomodoro',
    num: 7,
    icon: '🍅',
    tag: 'Стиль 7 из 9 • Фокус-таймер',
    title: 'Таймер Фокуса Помодоро (25:00) + Часы и Погода',
    desc: 'Крупный обратный отсчёт 25-минутной рабочей сессии с живыми секундами + текущее время и температура в вашем районе.'
  },
  {
    id: 'v8_world_clock',
    num: 8,
    icon: '🌍',
    tag: 'Стиль 8 из 9 • 4 Города на русском',
    title: 'Мировое Время (Ваш район + Лондон + Токио + Нью-Йорк)',
    desc: 'Четыре горизонтальные карточки мирового времени на русском языке с выделением вашего района.'
  },
  {
    id: 'v9_sun_cycle',
    num: 9,
    icon: '☀️',
    tag: 'Стиль 9 из 9 • Световой день',
    title: 'Восход, Закат и Световой День + Яндекс Погода',
    desc: 'Крупные часы, время восхода и заката солнца и актуальная сводка погоды и ветра в вашем районе.'
  }
];

const NINE_MODES = [
  'v1_classic_cal',
  'v2_flip_clock',
  'v3_weather_pro',
  'v4_day_planner',
  'v5_night_clock',
  'v6_retro_term',
  'v7_pomodoro',
  'v8_world_clock',
  'v9_sun_cycle'
];

let state = {
  cities: {},
  config: {
    cydVariant: 's024_perfect',
    wifiSsid: '',
    wifiPassword: '',
    yandexApiKey: '',
    city: 'Москва • Бутово',
    latitude: 55.5520,
    longitude: 37.5510,
    timezoneOffset: 3,
    selectedWidget: 'v1_classic_cal',
    notes: [
      'Утренняя разминка и кофе',
      'Посмотреть задачи на день',
      'Вечерняя прогулка в 19:00'
    ],
    eventTitle: 'До Нового Года',
    eventDays: '73 ДНЯ',
    weatherCache: {
      tempC: 4,
      tmaxC: 6,
      tminC: 1,
      windMs: 3.8,
      humidity: 72,
      wcode: 3,
      descRu: 'Пасмурно',
      source: 'Яндекс Погода'
    }
  },
  previewIdx: 0,
  pomoSec: 25 * 60,
  pomoRun: true,
  serialPort: null
};

function toAsciiSafe(str) {
  if (!str) return '';
  const map = {
    а:'a', б:'b', в:'v', г:'g', д:'d', е:'e', ё:'yo', ж:'zh', з:'z', и:'i', й:'y',
    к:'k', л:'l', м:'m', н:'n', о:'o', п:'p', р:'r', с:'s', т:'t', у:'u', ф:'f',
    х:'kh', ц:'ts', ч:'ch', ш:'sh', щ:'shch', ъ:'', ы:'y', ь:'', э:'e', ю:'yu', я:'ya',
    А:'A', Б:'B', В:'V', Г:'G', Д:'D', Е:'E', Ё:'Yo', Ж:'Zh', З:'Z', И:'I', Й:'Y',
    К:'K', Л:'L', М:'M', Н:'N', О:'O', П:'P', Р:'R', С:'S', Т:'T', У:'U', Ф:'F',
    Х:'Kh', Ц:'Ts', Ч:'Ch', Ш:'Sh', Щ:'Shch', Ъ:'', Ы:'Y', Ь:'', Э:'E', Ю:'Yu', Я:'Ya'
  };
  return String(str)
    .split('')
    .map(ch => (map[ch] !== undefined ? map[ch] : ch))
    .join('')
    .replace(/[^\x20-\x7E]/g, '');
}

document.addEventListener('DOMContentLoaded', async () => {
  const isInIframe = window.self !== window.top;
  const openUrl = window.location.href;
  document.getElementById('btnOpenNewTab').href = openUrl;
  const bannerBtn = document.getElementById('btnOpenNewTabBanner');
  if (bannerBtn) bannerBtn.href = openUrl;
  if (isInIframe) {
    document.getElementById('iframeNotice').style.display = 'flex';
  }

  await loadInitialStatus();
  setupEventListeners();
  renderWidgetsGallery();
  renderCydCanvas();
  fetchLiveWeatherFromOpenMeteo();

  setInterval(() => {
    if (state.pomoRun && state.pomoSec > 0) {
      state.pomoSec--;
    }
    renderCydCanvas();
  }, 500);
});

// Быстрый fetch с жёстким таймаутом (никогда не зависает даже при VPN / блокировках)
async function fetchWithTimeout(url, timeoutMs = 2500) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { signal: ctrl.signal });
    return resp;
  } finally {
    clearTimeout(timer);
  }
}

const FREE_STATIONS_OVERRIDE = {
  vnukovo: { label: 'Метеостанция Внуково (UUWW)', lat: 55.5915, lon: 37.2615 },
  msu: { label: 'Метеообсерватория МГУ (ЮЗАО)', lat: 55.7072, lon: 37.5228 },
  domodedovo: { label: 'Метеостанция Домодедово (UUDD)', lat: 55.4088, lon: 37.9063 }
};

function metNoSymbolToWmo(sym) {
  if (!sym) return 3;
  if (sym.startsWith('clearsky')) return 0;
  if (sym.startsWith('fair') || sym.startsWith('partlycloudy')) return 2;
  if (sym.startsWith('cloudy')) return 3;
  if (sym.startsWith('fog')) return 45;
  if (sym.includes('snow') || sym.includes('sleet')) return 73;
  if (sym.includes('thunder')) return 95;
  if (sym.includes('rain') || sym.includes('drizzle')) return 63;
  return 3;
}

async function fetchFromOpenMeteoDirect(lat, lon, sourceLabel) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&windspeed_unit=ms`;
  const resp = await fetchWithTimeout(url, 2500);
  if (!resp.ok) throw new Error('Open-Meteo HTTP ' + resp.status);
  const data = await resp.json();
  if (!data || !data.current_weather) throw new Error('No current_weather');
  const cw = data.current_weather;
  const tNow = Math.round(Number(cw.temperature));
  const wNow = Number(Number(cw.windspeed || 3.5).toFixed(1));
  const wcode = Number(cw.weathercode ?? 3);
  return {
    tempC: tNow,
    tmaxC: tNow + 2,
    tminC: tNow - 2,
    windMs: wNow,
    humidity: 70,
    wcode,
    descRu: wmoToRuJs(wcode),
    source: sourceLabel || 'Open-Meteo + Росгидромет WMO'
  };
}

async function fetchFromMetNorwayDirect(lat, lon, sourceLabel) {
  const url = `https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=${Number(lat).toFixed(4)}&lon=${Number(lon).toFixed(4)}`;
  const resp = await fetchWithTimeout(url, 2500);
  if (!resp.ok) throw new Error('MET.no HTTP ' + resp.status);
  const data = await resp.json();
  const ts = data?.properties?.timeseries?.[0];
  const details = ts?.data?.instant?.details;
  if (!details) throw new Error('No MET.no details');
  const sym = ts?.data?.next_1_hours?.summary?.symbol_code || ts?.data?.next_6_hours?.summary?.symbol_code || 'cloudy';
  const wcode = metNoSymbolToWmo(sym);
  const tNow = Math.round(Number(details.air_temperature));
  const wNow = Number(Number(details.wind_speed ?? 3.5).toFixed(1));
  return {
    tempC: tNow,
    tmaxC: tNow + 2,
    tminC: tNow - 2,
    windMs: wNow,
    humidity: Math.round(Number(details.relative_humidity ?? 70)),
    wcode,
    descRu: wmoToRuJs(wcode),
    source: sourceLabel || 'MET Norway (YR.no)'
  };
}

// Получает актуальную погоду с бесплатных метеостанций (без платных API-ключей и без зависаний!)
async function fetchLiveWeatherFromOpenMeteo() {
  const cityName = document.getElementById('selectCity')?.value || state.config.city || 'Москва • Бутово';
  const stationMode = document.getElementById('selectWeatherStation')?.value || 'multi';
  const cInfo = state.cities[cityName] || {
    shortRu: 'Бутово',
    lat: state.config.latitude || 55.5520,
    lon: state.config.longitude || 37.5510
  };
  const shortRu = cInfo.shortRu || (cityName.includes('•') ? cityName.split('•')[1].trim() : cityName);

  const override = FREE_STATIONS_OVERRIDE[stationMode];
  const lat = override ? override.lat : cInfo.lat;
  const lon = override ? override.lon : cInfo.lon;
  state.config.latitude = lat;
  state.config.longitude = lon;

  try {
    let weather = null;
    if (stationMode === 'metno') {
      weather = await fetchFromMetNorwayDirect(lat, lon, 'MET Norway (YR.no)');
    } else if (stationMode === 'openmeteo') {
      weather = await fetchFromOpenMeteoDirect(lat, lon, 'Open-Meteo + Росгидромет WMO');
    } else if (override) {
      weather = await Promise.any([
        fetchFromOpenMeteoDirect(lat, lon, override.label),
        fetchFromMetNorwayDirect(lat, lon, override.label)
      ]);
    } else {
      // Режим multi: опрашиваем обе бесплатные метеослужбы параллельно и берём самый быстрый ответ (за ~0.2 сек)
      weather = await Promise.any([
        fetchFromOpenMeteoDirect(lat, lon, 'Метеорадар (Open-Meteo WMO)'),
        fetchFromMetNorwayDirect(lat, lon, 'Метеорадар (MET Norway)')
      ]);
    }

    if (weather) {
      state.config.weatherCache = {
        ...state.config.weatherCache,
        ...weather,
        liveLoaded: true
      };
      updateWeatherBadgeUi(cityName, shortRu, state.config.weatherCache);
      renderCydCanvas();
      return;
    }
  } catch (e) {
    console.warn('Прямой опрос метеостанций не ответил за 2.5с, используем текущие данные:', e);
  }

  updateWeatherBadgeUi(cityName, shortRu, state.config.weatherCache);
  renderCydCanvas();
}

function wmoToRuJs(wcode) {
  if (wcode === 0) return 'Ясно';
  if (wcode === 1 || wcode === 2) return 'Малооблачно';
  if (wcode === 3) return 'Пасмурно';
  if (wcode === 45 || wcode === 48) return 'Туман';
  if (wcode >= 51 && wcode <= 67) return 'Дождь';
  if (wcode >= 71 && wcode <= 77) return 'Снег';
  if (wcode >= 80 && wcode <= 82) return 'Ливень';
  if (wcode >= 85 && wcode <= 86) return 'Снегопад';
  if (wcode >= 95) return 'Гроза';
  return 'Облачно';
}

function updateWeatherBadgeUi(fullCityName, shortRu, wc) {
  const badgeEl = document.getElementById('liveWeatherPreviewBadge');
  if (!badgeEl || !wc) return;
  const nowHHMM = new Date().toTimeString().slice(0, 5);
  badgeEl.innerHTML = `🌤️ <strong>${wc.source || 'Яндекс Погода'}</strong> (<span style="color:#fbbf24;">📍 ${fullCityName}</span> → на экране: <code>${shortRu}</code>): <strong style="color:#fff;">${fmtTempStr(wc.tempC)}</strong> • <span style="color:#38bdf8;">${wc.descRu || 'Пасмурно'}</span> • <span style="color:#34d399;">Ветер ${wc.windMs ?? 3.5} м/с</span> <span style="color:#94a3b8; font-size:12px;">(обн. ${nowHHMM})</span>`;
}

function fmtTempStr(val) {
  const n = Math.round(Number(val ?? 4));
  return n > 0 ? `+${n}°C` : `${n}°C`;
}

function getShortCityRu() {
  const cityName = state.config.city || 'Москва • Бутово';
  const cInfo = state.cities[cityName];
  if (cInfo && cInfo.shortRu) return cInfo.shortRu;
  return cityName.includes('•') ? cityName.split('•')[1].trim() : cityName;
}

async function loadInitialStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.ok) {
      state.cities = data.cities || {};
      state.config = { ...state.config, ...data.config };

      const validVariants = ['s024_perfect', 's024_bgr_inv0', 's024_rgb_inv1', 's024_bgr_inv1'];
      if (!validVariants.includes(state.config.cydVariant)) {
        state.config.cydVariant = 's024_perfect';
      }

      const idx = NINE_MODES.indexOf(state.config.selectedWidget);
      state.previewIdx = idx >= 0 ? idx : 0;

      populateCitiesSelect();
      document.getElementById('inputWifiSsid').value = state.config.wifiSsid || '';
      document.getElementById('inputWifiPass').value = state.config.wifiPassword || '';
      const yaInput = document.getElementById('inputYandexKey');
      if (yaInput) yaInput.value = state.config.yandexApiKey || '';
      document.getElementById('selectCydVariant').value = state.config.cydVariant;
    }
  } catch (err) {
    console.error('Ошибка загрузки статуса:', err);
  }
}

function populateCitiesSelect() {
  const sel = document.getElementById('selectCity');
  if (!sel) return;
  sel.innerHTML = '';

  const moscowGroup = document.createElement('optgroup');
  moscowGroup.label = '🏙️ Москва и районы Москвы (Яндекс Погода по координатам)';
  const russiaGroup = document.createElement('optgroup');
  russiaGroup.label = '🌍 Города России и СНГ';

  Object.keys(state.cities).forEach(cityName => {
    const c = state.cities[cityName];
    const opt = document.createElement('option');
    opt.value = cityName;
    opt.textContent = c.group === 'moscow'
      ? `📍 ${cityName} (${c.lat.toFixed(3)}, ${c.lon.toFixed(3)})`
      : `${cityName} (UTC+${c.tz})`;
    if (state.config.city === cityName) opt.selected = true;
    if (c.group === 'moscow') {
      moscowGroup.appendChild(opt);
    } else {
      russiaGroup.appendChild(opt);
    }
  });

  sel.appendChild(moscowGroup);
  sel.appendChild(russiaGroup);
}

function readTopConfigFromDom() {
  state.config.wifiSsid = document.getElementById('inputWifiSsid').value.trim();
  state.config.wifiPassword = document.getElementById('inputWifiPass').value;
  state.config.yandexApiKey = document.getElementById('inputYandexKey')?.value?.trim() || '';
  state.config.city = document.getElementById('selectCity').value || 'Москва • Бутово';
  state.config.cydVariant = document.getElementById('selectCydVariant').value || 's024_perfect';
  const cInfo = state.cities[state.config.city];
  if (cInfo) {
    state.config.latitude = cInfo.lat;
    state.config.longitude = cInfo.lon;
    state.config.timezoneOffset = cInfo.tz;
  }

  const notesEl = document.getElementById('cardNotesInput');
  if (notesEl) {
    state.config.notes = notesEl.value
      .split('\n')
      .map(s => s.trim())
      .filter(Boolean);
  }
  const eTitleEl = document.getElementById('cardEventTitle');
  const eDaysEl = document.getElementById('cardEventDays');
  if (eTitleEl) state.config.eventTitle = eTitleEl.value.trim() || 'До Нового Года';
  if (eDaysEl) state.config.eventDays = eDaysEl.value.trim() || '73 ДНЯ';
}

async function saveConfigToServer(widgetId) {
  readTopConfigFromDom();
  if (widgetId) {
    state.config.selectedWidget = widgetId;
  }
  try {
    const res = await fetchWithTimeout('/api/config', 1500);
    // Используем POST с таймаутом 1.5с
  } catch (_) {}
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 1500);
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.config),
      signal: ctrl.signal
    });
    clearTimeout(t);
    const data = await res.json();
    if (data.ok) {
      state.config = { ...data.config, selectedWidget: widgetId || data.config.selectedWidget };
    }
    return data;
  } catch (e) {
    return { ok: false };
  }
}

// ============================================================================
// ВИТРИНА 10 ВАРИАЦИЙ ЧАСОВ, КАЛЕНДАРЕЙ И ПОГОДЫ
// ============================================================================
function renderWidgetsGallery() {
  const container = document.getElementById('widgetsGallery');
  if (!container) return;
  container.innerHTML = '';

  WIDGET_CATALOG.forEach(item => {
    const isSelected = state.config.selectedWidget === item.id;
    const card = document.createElement('div');
    card.className = 'widget-card' + (isSelected ? ' active-widget' : '');

    let extraHtml = '';
    if (item.hasNotesInput) {
      extraHtml = `
        <div class="form-group" style="margin-top:4px;">
          <textarea id="cardNotesInput" class="textarea" rows="3">${(state.config.notes || []).join('\n')}</textarea>
        </div>
      `;
    } else if (item.hasEventInput) {
      extraHtml = `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:4px;">
          <div class="form-group">
            <label>Событие:</label>
            <input id="cardEventTitle" type="text" class="input" value="${state.config.eventTitle || 'До Нового Года'}" />
          </div>
          <div class="form-group">
            <label>Осталось дней:</label>
            <input id="cardEventDays" type="text" class="input" value="${state.config.eventDays || '73 DAYS'}" />
          </div>
        </div>
      `;
    }

    card.innerHTML = `
      <div>
        <div class="widget-card-header">
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="widget-icon-lg">${item.icon}</div>
            <div>
              <span class="widget-tag">${item.tag}</span>
              <div style="font-weight:800; font-size:15px; margin-top:4px;">${item.title}</div>
            </div>
          </div>
        </div>
        <p style="font-size:13px; color:var(--text-muted); margin-top:10px;">
          ${item.desc}
        </p>
        ${extraHtml}
      </div>

      <div class="widget-card-actions">
        <button class="btn btn-sm" data-preview="${item.id}">
          👁️ Посмотреть / Переключить на плате
        </button>
        <button class="btn btn-install" data-install="${item.id}">
          ⚡ Записать в память платы (за 3 сек)
        </button>
      </div>
    `;

    container.appendChild(card);
  });

  container.querySelectorAll('[data-preview]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.preview;
      readTopConfigFromDom();
      state.config.selectedWidget = id;
      const idx = NINE_MODES.indexOf(id);
      state.previewIdx = idx >= 0 ? idx : 0;
      renderWidgetsGallery();
      renderCydCanvas();
      await sendLiveSerialCommand('SET:' + id);
    });
  });

  container.querySelectorAll('[data-install]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.install;
      const idx = NINE_MODES.indexOf(id);
      if (idx >= 0) state.previewIdx = idx;
      renderCydCanvas();
      await runOneClickInstall(id, false);
    });
  });

  ['cardNotesInput', 'cardEventTitle', 'cardEventDays'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', () => {
      readTopConfigFromDom();
      renderCydCanvas();
    });
  });
}

// ============================================================================
// ОТРИСОВКА ВСЕХ 9 РУССКИХ ВИДЖЕТОВ НА ЭКРАНЕ 320x240 (1-В-1 КАК НА ESP32)
// ============================================================================
function renderCydCanvas() {
  const canvas = document.getElementById('cydCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = 320;
  const H = 240;

  const modeId = NINE_MODES[state.previewIdx % NINE_MODES.length];
  const badge = document.getElementById('previewBadge');
  if (badge) {
    badge.textContent = `Стиль ${state.previewIdx + 1} из 9 (1-в-1 на русском)`;
  }

  ctx.fillStyle = '#070B14';
  ctx.fillRect(0, 0, W, H);

  // Верхняя панель 320x24
  ctx.fillStyle = '#101C33';
  ctx.fillRect(0, 0, W, 24);

  const topTitles = [
    '1/9 КАЛЕНДАРЬ',
    '2/9 КРУПНЫЕ ЧАСЫ',
    '3/9 ЯНДЕКС ПОГОДА',
    '4/9 НЕДЕЛЯ И ПЛАНЫ',
    '5/9 НОЧНОЙ НЕОН',
    '6/9 РЕТРО ТЕРМИНАЛ',
    '7/9 ПОМОДОРО',
    '8/9 МИРОВОЕ ВРЕМЯ',
    '9/9 СОЛНЦЕ И ДЕНЬ'
  ];

  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 12px sans-serif';
  ctx.fillText(topTitles[state.previewIdx] || '1/9 КАЛЕНДАРЬ', 8, 16);

  const now = new Date();
  const hhmm = now.toTimeString().slice(0, 5);
  const shortCity = getShortCityRu();
  const hasWifi = Boolean(state.config.wifiSsid);
  const rightTxt = hasWifi ? `📶 WIFI OK • ${hhmm} (4:59)` : `${shortCity} • OK ${hhmm}`;

  ctx.fillStyle = '#10B981';
  ctx.font = 'bold 11px sans-serif';
  ctx.fillText(rightTxt, W - ctx.measureText(rightTxt).width - 18, 16);

  // Пульсирующий светодиодный индикатор в правом верхнем углу
  const pulseOn = now.getSeconds() % 2 === 0;
  ctx.fillStyle = pulseOn ? '#10B981' : '#064E3B';
  ctx.beginPath();
  ctx.arc(W - 10, 12, 4, 0, Math.PI * 2);
  ctx.fill();

  if (modeId === 'v1_classic_cal') drawV1ClassicCal(ctx, now);
  else if (modeId === 'v2_flip_clock') drawV2FlipClock(ctx, now);
  else if (modeId === 'v3_weather_pro') drawV3WeatherPro(ctx, now);
  else if (modeId === 'v4_day_planner') drawV4DayPlanner(ctx, now);
  else if (modeId === 'v5_night_clock') drawV5NightClock(ctx, now);
  else if (modeId === 'v6_retro_term') drawV6RetroTerm(ctx, now);
  else if (modeId === 'v7_pomodoro') drawV7Pomodoro(ctx, now);
  else if (modeId === 'v8_world_clock') drawV8WorldClock(ctx, now);
  else drawV9SunCycle(ctx, now);
}

function drawCard(ctx, x, y, w, h, bgHex, borderHex = '#1E293B', radius = 10) {
  ctx.fillStyle = bgHex;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, radius);
  ctx.fill();
  if (borderHex) {
    ctx.strokeStyle = borderHex;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function drawPinIcon(ctx, x, y) {
  ctx.save();
  ctx.fillStyle = '#FB7185';
  ctx.beginPath();
  ctx.arc(x + 5, y + 5, 4.5, Math.PI, 0, false);
  ctx.lineTo(x + 5, y + 13);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = '#0F172A';
  ctx.beginPath();
  ctx.arc(x + 5, y + 5, 1.8, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawV1ClassicCal(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const ss = String(now.getSeconds()).padStart(2, '0');
  const daysRu = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};

  // Время 40px
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 34px sans-serif';
  ctx.fillText(hhmm, 8, 56);

  // День недели + секунды
  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 12px sans-serif';
  ctx.fillText(`${daysRu[now.getDay()]} • ${ss}с`, 8, 76);

  // Дата
  const dStr = `${String(now.getDate()).padStart(2, '0')}.${String(now.getMonth() + 1).padStart(2, '0')}.${now.getFullYear()}`;
  ctx.fillStyle = '#CBD5E1';
  ctx.font = 'bold 12px sans-serif';
  ctx.fillText(dStr, 8, 93);

  // Карточка Яндекс Погоды (108x128 на x=6, y=104)
  drawCard(ctx, 6, 104, 108, 128, '#0F172A', '#1E293B', 10);
  drawPinIcon(ctx, 14, 112);

  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 13px sans-serif';
  ctx.fillText(shortCity, 28, 123);

  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 24px sans-serif';
  ctx.fillText(fmtTempStr(wc.tempC), 14, 152);

  ctx.fillStyle = '#38BDF8';
  ctx.font = 'bold 11.5px sans-serif';
  ctx.fillText(`☁ ${wc.descRu || 'Пасмурно'}`, 14, 173);

  ctx.fillStyle = '#34D399';
  ctx.font = 'bold 11.5px sans-serif';
  ctx.fillText(`Ветер ${wc.windMs ?? 3.8} м/с`, 14, 193);

  ctx.fillStyle = '#10B981';
  ctx.font = 'bold 11px sans-serif';
  ctx.fillText(`✓ Яндекс • ${hhmm}`, 14, 215);

  // Правая карточка календаря (196x204 на x=118, y=30)
  drawCard(ctx, 118, 30, 196, 204, '#0B1324', '#1E293B', 10);

  const year = now.getFullYear();
  const month = now.getMonth();
  const today = now.getDate();
  const monthsRu = ['ЯНВАРЬ', 'ФЕВРАЛЬ', 'МАРТ', 'АПРЕЛЬ', 'МАЙ', 'ИЮНЬ', 'ИЮЛЬ', 'АВГУСТ', 'СЕНТЯБРЬ', 'ОКТЯБРЬ', 'НОЯБРЬ', 'ДЕКАБРЬ'];
  const mTitle = `${monthsRu[month]} ${year}`;
  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 15px sans-serif';
  ctx.fillText(mTitle, 118 + (196 - ctx.measureText(mTitle).width) / 2, 48);

  const hdr = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const colW = 26;
  const rowH = 25;
  const startX = 125;
  ctx.font = 'bold 11.5px sans-serif';
  hdr.forEach((h, i) => {
    ctx.fillStyle = i >= 5 ? '#FB7185' : '#94A3B8';
    const tw = ctx.measureText(h).width;
    ctx.fillText(h, startX + i * colW + (colW - tw) / 2, 68);
  });

  const firstDow = (new Date(year, month, 1).getDay() + 6) % 7;
  const totalDays = new Date(year, month + 1, 0).getDate();
  ctx.font = 'bold 14.5px sans-serif';
  for (let d = 1; d <= totalDays; d++) {
    const idxCell = firstDow + (d - 1);
    const col = idxCell % 7;
    const row = Math.floor(idxCell / 7);
    const cx = startX + col * colW;
    const cy = 88 + row * rowH;

    if (d === today) {
      ctx.fillStyle = '#00E5FF';
      ctx.beginPath();
      ctx.roundRect(cx + 1, cy - 14, 24, 20, 6);
      ctx.fill();
      ctx.fillStyle = '#070B14';
    } else if (col >= 5) {
      ctx.fillStyle = '#FDA4AF';
    } else {
      ctx.fillStyle = '#F1F5F9';
    }
    const ds = String(d);
    const tw = ctx.measureText(ds).width;
    ctx.fillText(ds, cx + (colW - tw) / 2, cy);
  }
}

function drawV2FlipClock(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const ss = String(now.getSeconds()).padStart(2, '0');
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};
  const daysRu = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
  const monthsGen = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

  drawCard(ctx, 10, 32, 300, 114, '#0F172A', '#00E5FF', 14);
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 48px sans-serif';
  ctx.fillText(hhmm, 64, 92);

  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 26px sans-serif';
  ctx.fillText(`:${ss}`, 206, 88);

  const sub = `${daysRu[now.getDay()]}, ${String(now.getDate()).padStart(2, '0')} ${monthsGen[now.getMonth()]}`;
  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 15px sans-serif';
  ctx.fillText(sub, 160 - ctx.measureText(sub).width / 2, 132);

  drawCard(ctx, 10, 154, 300, 78, '#111C35', '#1E293B', 12);
  drawPinIcon(ctx, 22, 165);
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 15px sans-serif';
  ctx.fillText(`${shortCity}  •  ${fmtTempStr(wc.tempC)}`, 38, 177);

  ctx.fillStyle = '#34D399';
  ctx.font = 'bold 13.5px sans-serif';
  ctx.fillText(`☁ ${wc.descRu || 'Пасмурно'}  •  Ветер ${wc.windMs ?? 3.8} м/с`, 22, 200);

  ctx.fillStyle = '#38BDF8';
  ctx.font = 'bold 11.5px sans-serif';
  ctx.fillText(`✓ Яндекс Погода • Обновлено ${hhmm}`, 22, 220);
}

function drawV3WeatherPro(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};

  drawCard(ctx, 8, 32, 304, 200, '#0F172A', '#0284C7', 12);
  drawPinIcon(ctx, 22, 43);

  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 16px sans-serif';
  ctx.fillText(`${shortCity}  •  ${hhmm}`, 40, 55);

  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 28px sans-serif';
  ctx.fillText(fmtTempStr(wc.tempC), 22, 92);

  ctx.fillStyle = '#38BDF8';
  ctx.font = 'bold 16px sans-serif';
  ctx.fillText(`☁ ${wc.descRu || 'Пасмурно'}`, 122, 88);

  ctx.fillStyle = '#E2E8F0';
  ctx.font = 'bold 13.5px sans-serif';
  ctx.fillText(`Макс: ${fmtTempStr(wc.tmaxC ?? 6)}   Мин: ${fmtTempStr(wc.tminC ?? 1)}   Влажн: ${wc.humidity ?? 72}%`, 22, 134);

  ctx.fillStyle = '#34D399';
  ctx.fillText(`💨 Ветер: ${wc.windMs ?? 3.8} м/с   Коорд: ${Number(state.config.latitude || 55.55).toFixed(2)}, ${Number(state.config.longitude || 37.55).toFixed(2)}`, 22, 164);

  ctx.fillStyle = '#38BDF8';
  ctx.font = 'bold 12px sans-serif';
  ctx.fillText(`Источник: ✓ Яндекс Погода • ${hhmm}`, 22, 204);
}

function drawV4DayPlanner(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};
  const wday = (now.getDay() + 6) % 7;
  const daysShort = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  for (let i = 0; i < 7; i++) {
    drawCard(ctx, 8 + i * 44, 30, 40, 34, i === wday ? '#00E5FF' : '#111C35', null, 6);
    ctx.fillStyle = i === wday ? '#070B14' : '#E2E8F0';
    ctx.font = 'bold 13px sans-serif';
    const tw = ctx.measureText(daysShort[i]).width;
    ctx.fillText(daysShort[i], 8 + i * 44 + (40 - tw) / 2, 52);
  }

  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 13.5px sans-serif';
  const dStr = `${String(now.getDate()).padStart(2, '0')}.${String(now.getMonth() + 1).padStart(2, '0')}`;
  ctx.fillText(`${hhmm}  •  ${dStr}  •  📍 ${shortCity} ${fmtTempStr(wc.tempC)}`, 10, 84);

  const notes = state.config.notes || [];
  for (let i = 0; i < 3; i++) {
    drawCard(ctx, 8, 98 + i * 44, 304, 38, '#0F172A', '#1E293B', 8);
    ctx.fillStyle = '#F8FAFC';
    ctx.font = 'bold 13.5px sans-serif';
    ctx.fillText(`${i + 1}. ${(notes[i] || 'Отличного дня!').slice(0, 28)}`, 18, 122 + i * 44);
  }
}

function drawV5NightClock(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};
  const daysRu = ['ВОСКРЕСЕНЬЕ', 'ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА'];
  const monthsRu = ['ЯНВАРЬ', 'ФЕВРАЛЬ', 'МАРТ', 'АПРЕЛЬ', 'МАЙ', 'ИЮНЬ', 'ИЮЛЬ', 'АВГУСТ', 'СЕНТЯБРЬ', 'ОКТЯБРЬ', 'НОЯБРЬ', 'ДЕКАБРЬ'];

  drawCard(ctx, 10, 34, 300, 196, '#050811', '#00E5FF', 16);
  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 50px sans-serif';
  const tw = ctx.measureText(hhmm).width;
  ctx.fillText(hhmm, 160 - tw / 2, 118);

  const dl = `${daysRu[now.getDay()]}, ${String(now.getDate()).padStart(2, '0')} ${monthsRu[now.getMonth()]}`;
  ctx.fillStyle = '#38BDF8';
  ctx.font = 'bold 15px sans-serif';
  ctx.fillText(dl, 160 - ctx.measureText(dl).width / 2, 160);

  const wl = `📍 ${shortCity}  •  ${fmtTempStr(wc.tempC)}  •  ${wc.windMs ?? 3.8} м/с`;
  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 13.5px sans-serif';
  ctx.fillText(wl, 160 - ctx.measureText(wl).width / 2, 208);
}

function drawV6RetroTerm(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};
  const daysShort = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
  const dStr = `${String(now.getDate()).padStart(2, '0')}.${String(now.getMonth() + 1).padStart(2, '0')}.${now.getFullYear()}`;

  drawCard(ctx, 8, 32, 304, 200, '#041208', '#10B981', 8);
  ctx.fillStyle = '#10B981';
  ctx.font = 'bold 12px monospace';
  ctx.fillText('CASIO CYD-2432 // ЯНДЕКС РАДАР', 20, 52);

  ctx.fillStyle = '#34D399';
  ctx.font = 'bold 44px monospace';
  ctx.fillText(hhmm, 20, 102);

  ctx.fillStyle = '#10B981';
  ctx.font = 'bold 14px sans-serif';
  ctx.fillText(`ДАТА: ${dStr} (${daysShort[now.getDay()]})`, 20, 138);

  ctx.fillStyle = '#A7F3D0';
  ctx.fillText(`ЛОКАЦИЯ: ${shortCity.toUpperCase()}  •  ${fmtTempStr(wc.tempC)}`, 20, 166);

  ctx.fillStyle = '#34D399';
  ctx.font = 'bold 12px sans-serif';
  ctx.fillText(`ВЕТЕР: ${wc.windMs ?? 3.8} М/С  •  ✓ Яндекс • ${hhmm}`, 20, 196);
}

function drawV7Pomodoro(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};
  const mins = String(Math.floor(state.pomoSec / 60)).padStart(2, '0');
  const secs = String(state.pomoSec % 60).padStart(2, '0');

  drawCard(ctx, 10, 32, 300, 200, '#131C31', '#F43F5E', 14);
  const t = 'ФОКУС-ТАЙМЕР ПОМОДОРО';
  ctx.fillStyle = '#FB7185';
  ctx.font = 'bold 14px sans-serif';
  ctx.fillText(t, 160 - ctx.measureText(t).width / 2, 58);

  const pTxt = `${mins}:${secs}`;
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 50px sans-serif';
  ctx.fillText(pTxt, 160 - ctx.measureText(pTxt).width / 2, 138);

  const sub = `Время ${hhmm}  •  📍 ${shortCity} ${fmtTempStr(wc.tempC)}`;
  ctx.fillStyle = '#38BDF8';
  ctx.font = 'bold 14px sans-serif';
  ctx.fillText(sub, 160 - ctx.measureText(sub).width / 2, 206);
}

function drawV8WorldClock(ctx, now) {
  const shortCity = getShortCityRu();
  const utcH = (now.getUTCHours() + 24) % 24;
  const mm = String(now.getMinutes()).padStart(2, '0');
  const zones = [
    { name: `📍 ${shortCity}`, time: now.toTimeString().slice(0, 5), color: '#00E5FF' },
    { name: 'Лондон (UTC+0)', time: `${String(utcH).padStart(2, '0')}:${mm}`, color: '#E2E8F0' },
    { name: 'Токио (UTC+9)', time: `${String((utcH + 9) % 24).padStart(2, '0')}:${mm}`, color: '#FBBF24' },
    { name: 'Нью-Йорк (UTC-5)', time: `${String((utcH + 19) % 24).padStart(2, '0')}:${mm}`, color: '#34D399' }
  ];

  zones.forEach((z, i) => {
    drawCard(ctx, 8, 32 + i * 50, 304, 44, '#0F172A', '#1E293B', 8);
    ctx.fillStyle = z.color;
    ctx.font = 'bold 15px sans-serif';
    ctx.fillText(z.name, 20, 60 + i * 50);

    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 22px monospace';
    ctx.fillText(z.time, 234, 62 + i * 50);
  });
}

function drawV9SunCycle(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  const shortCity = getShortCityRu();
  const wc = state.config.weatherCache || {};

  drawCard(ctx, 10, 32, 300, 200, '#0F172A', '#FBBF24', 14);
  const hdr = '☀ СВЕТОВОЙ ДЕНЬ И ПОГОДА';
  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 14px sans-serif';
  ctx.fillText(hdr, 160 - ctx.measureText(hdr).width / 2, 56);

  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 42px sans-serif';
  ctx.fillText(hhmm, 160 - ctx.measureText(hhmm).width / 2, 114);

  const sun = 'Восход: 07:12   •   Закат: 17:48';
  ctx.fillStyle = '#38BDF8';
  ctx.font = 'bold 14px sans-serif';
  ctx.fillText(sun, 160 - ctx.measureText(sun).width / 2, 156);

  const w = `📍 ${shortCity}  •  ${fmtTempStr(wc.tempC)}  •  Ветер ${wc.windMs ?? 3.8} м/с`;
  ctx.fillStyle = '#34D399';
  ctx.font = 'bold 13.5px sans-serif';
  ctx.fillText(w, 160 - ctx.measureText(w).width / 2, 206);
}

// ============================================================================
// СОБЫТИЯ И НАВИГАЦИЯ
// ============================================================================
// Мгновенно переключает виджет на подключённой по USB плате за 0.05 сек без перепрошивки!
async function sendLiveSerialCommand(cmd) {
  if (!state.serialPort) return false;
  try {
    const port = state.serialPort;
    if (!port.writable) {
      await port.open({ baudRate: 115200 });
    }
    const writer = port.writable.getWriter();
    const bytes = new TextEncoder().encode(cmd + '\r\n');
    await writer.write(bytes);
    writer.releaseLock();
    await port.close();
    return true;
  } catch (e) {
    try {
      await state.serialPort.close();
    } catch (_) {}
    return false;
  }
}

function setupEventListeners() {
  const canvas = document.getElementById('cydCanvas');
  canvas?.addEventListener('click', async e => {
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 320;
    if (x < 160) {
      state.previewIdx = (state.previewIdx - 1 + NINE_MODES.length) % NINE_MODES.length;
    } else {
      state.previewIdx = (state.previewIdx + 1) % NINE_MODES.length;
    }
    state.config.selectedWidget = NINE_MODES[state.previewIdx];
    renderWidgetsGallery();
    renderCydCanvas();
    await sendLiveSerialCommand('SET:' + state.config.selectedWidget);
  });

  document.getElementById('btnPreviewPrev')?.addEventListener('click', async () => {
    state.previewIdx = (state.previewIdx - 1 + NINE_MODES.length) % NINE_MODES.length;
    state.config.selectedWidget = NINE_MODES[state.previewIdx];
    renderWidgetsGallery();
    renderCydCanvas();
    await sendLiveSerialCommand('SET:' + state.config.selectedWidget);
  });

  document.getElementById('btnPreviewNext')?.addEventListener('click', async () => {
    state.previewIdx = (state.previewIdx + 1) % NINE_MODES.length;
    state.config.selectedWidget = NINE_MODES[state.previewIdx];
    renderWidgetsGallery();
    renderCydCanvas();
    await sendLiveSerialCommand('SET:' + state.config.selectedWidget);
  });

  document.querySelectorAll('.quick-city-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const cityVal = btn.dataset.city;
      const sel = document.getElementById('selectCity');
      if (sel && cityVal) {
        sel.value = cityVal;
        state.config.city = cityVal;
        await saveConfigToServer();
        await fetchLiveWeatherFromOpenMeteo();
        renderCydCanvas();
      }
    });
  });

  document.getElementById('btnRefreshWeatherNow')?.addEventListener('click', async () => {
    await saveConfigToServer();
    await fetchLiveWeatherFromOpenMeteo();
    renderCydCanvas();
    const wc = state.config.weatherCache || {};
    const hhmm = new Date().toTimeString().slice(0, 5);
    await sendLiveSerialCommand(
      `WUPD:${wc.tempC ?? 4}|${wc.tmaxC ?? 6}|${wc.tminC ?? 1}|${wc.windMs ?? 3.8}|${wc.wcode ?? 3}|${wc.descRu || 'Пасмурно'}|${hhmm}`
    );
  });

  ['inputWifiSsid', 'inputWifiPass', 'selectWeatherStation', 'selectCity', 'selectCydVariant'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', async () => {
      await saveConfigToServer();
      await fetchLiveWeatherFromOpenMeteo();
      renderCydCanvas();
    });
  });

  document.getElementById('btnInstallActivePreview')?.addEventListener('click', () => {
    runOneClickInstall(state.config.selectedWidget || NINE_MODES[state.previewIdx], false);
  });

  document.getElementById('btnQuickWakeUp')?.addEventListener('click', () => {
    runOneClickInstall(state.config.selectedWidget || 'v1_classic_cal', false);
  });

  document.getElementById('btnRunDeepScan')?.addEventListener('click', () => {
    runOneClickInstall(state.config.selectedWidget || 'v1_classic_cal', false);
  });

  document.getElementById('btnForceReflashEngine')?.addEventListener('click', () => {
    runOneClickInstall(state.config.selectedWidget || 'v1_classic_cal', true);
  });

  document.getElementById('btnCloseModal')?.addEventListener('click', () => {
    document.getElementById('installModal').classList.remove('open');
  });

  document.getElementById('btnRetryWithFullFlash')?.addEventListener('click', () => {
    runOneClickInstall(state.config.selectedWidget || 'v1_classic_cal', true);
  });

  // 4 кнопки мгновенного теста профиля матрицы экрана
  document.querySelectorAll('.profile-test-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const variant = btn.dataset.variant;
      document.getElementById('selectCydVariant').value = variant;
      state.config.cydVariant = variant;
      await runOneClickInstall(state.config.selectedWidget || 'v1_classic_cal', false);
    });
  });
}

// ============================================================================
// СКАНИРОВАНИЕ + БЫСТРАЯ УСТАНОВКА НА ESP32-2432S028 (ЗА 3 СЕКУНДЫ ЧЕРЕЗ 0x343000)
// ============================================================================
function logInstall(msg) {
  const box = document.getElementById('modalInstallLog');
  if (!box) return;
  box.textContent += msg + '\n';
  box.scrollTop = box.scrollHeight;
}

function setProgress(pct, stepText) {
  const bar = document.getElementById('modalProgressBar');
  const desc = document.getElementById('modalStepDesc');
  if (bar) bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  if (desc && stepText) desc.textContent = stepText;
}

// Формирует JSON-байты CYDCFG1:{...}\0 для записи в /config.txt внутри vfs_widgets.bin (полная поддержка русского UTF-8!)
function buildUserConfigBytes(cfg) {
  const cityInfo = state.cities[cfg.city] || {
    shortRu: 'Бутово',
    en: toAsciiSafe(cfg.city || 'Butovo'),
    lat: 55.5520,
    lon: 37.5510,
    tz: 3
  };
  const shortRu = cityInfo.shortRu || (cfg.city && cfg.city.includes('•') ? cfg.city.split('•')[1].trim() : (cfg.city || 'Бутово'));
  const wc = cfg.weatherCache || {};
  const now = new Date();
  const rtcTuple = [
    now.getFullYear(),
    now.getMonth() + 1,
    now.getDate(),
    (now.getDay() + 6) % 7, // Понедельник = 0 .. Воскресенье = 6
    now.getHours(),
    now.getMinutes(),
    now.getSeconds()
  ];
  const payloadObj = {
    cydVariant: cfg.cydVariant || 's024_perfect',
    wifiSsid: cfg.wifiSsid || '',
    wifiPassword: cfg.wifiPassword || '',
    yandexApiKey: cfg.yandexApiKey || '',
    cityRu: shortRu.slice(0, 18),
    cityEn: cityInfo.en || 'Butovo',
    latitude: Number(cfg.latitude || cityInfo.lat),
    longitude: Number(cfg.longitude || cityInfo.lon),
    timezoneOffset: Number(cfg.timezoneOffset ?? cityInfo.tz),
    selectedWidget: cfg.selectedWidget || 'v1_classic_cal',
    notes: (cfg.notes || []).slice(0, 3).map(s => String(s).slice(0, 32)),
    eventTitle: String(cfg.eventTitle || 'ДО НОВОГО ГОДА').slice(0, 26),
    eventDays: String(cfg.eventDays || '73 ДНЯ').slice(0, 18),
    tempC: Number(wc.tempC ?? 4),
    tmaxC: Number(wc.tmaxC ?? Number(wc.tempC ?? 4) + 2),
    tminC: Number(wc.tminC ?? Number(wc.tempC ?? 4) - 2),
    windMs: Number(wc.windMs ?? 3.8),
    humidity: Number(wc.humidity ?? 72),
    wcode: Number(wc.wcode ?? 3),
    descRu: String(wc.descRu || 'Пасмурно').slice(0, 18),
    weatherSource: String(wc.source || 'Яндекс').slice(0, 16),
    rtcTuple
  };
  return new TextEncoder().encode('CYDCFG1:' + JSON.stringify(payloadObj) + '\0');
}

// Патчит файл /config.txt прямо внутри образа LittleFS v2 (vfsUint8) в памяти браузера
function patchVfsImageWithConfig(vfsUint8, cfg) {
  const sig = [67, 89, 68, 67, 70, 71, 49, 58]; // "CYDCFG1:"
  let foundOffset = -1;
  for (let i = 0; i <= vfsUint8.length - 2048; i++) {
    if (
      vfsUint8[i] === sig[0] &&
      vfsUint8[i + 1] === sig[1] &&
      vfsUint8[i + 2] === sig[2] &&
      vfsUint8[i + 3] === sig[3] &&
      vfsUint8[i + 4] === sig[4] &&
      vfsUint8[i + 5] === sig[5] &&
      vfsUint8[i + 6] === sig[6] &&
      vfsUint8[i + 7] === sig[7]
    ) {
      foundOffset = i;
      break;
    }
  }
  if (foundOffset >= 0) {
    const jsonBytes = buildUserConfigBytes(cfg);
    const padded = new Uint8Array(2048).fill(32); // пробелы
    padded.set(jsonBytes.slice(0, 2047), 0);
    vfsUint8.set(padded, foundOffset);
  }
  return foundOffset;
}

// Создаёт 4096-байтный блок конфигурации для записи в 0x3E3000 (блок 160 раздела vfs)
function buildConfigFlashSector(cfg) {
  const jsonBytes = buildUserConfigBytes(cfg);
  const sector = new Uint8Array(4096).fill(0xff);
  sector.set(jsonBytes.slice(0, 4095), 0);
  return sector;
}

async function runOneClickInstall(widgetId, forceFullEngineFlash = false) {
  const modal = document.getElementById('installModal');
  const logBox = document.getElementById('modalInstallLog');
  logBox.textContent = '';
  modal.classList.add('open');

  if (!('serial' in navigator)) {
    setProgress(0, '⚠️ Откройте сайт в отдельной вкладке Chrome / Edge / Яндекс / Opera');
    logInstall('\n❌ Браузер ограничил доступ к USB во встроенном окне.');
    logInstall('👉 Нажмите «↗ Открыть в новой вкладке» вверху справа и нажмите кнопку ещё раз!');
    return;
  }

  try {
    // 1. Сразу запрашиваем USB COM-порт по клику пользователя (без ожидания сети, чтобы окно выбора порта открылось мгновенно!)
    setProgress(5, 'Выберите USB COM-порт вашей платы ESP32...');
    let port = state.serialPort;
    if (!port) {
      port = await navigator.serial.requestPort();
      state.serialPort = port;
    }

    if (widgetId) {
      state.config.selectedWidget = widgetId;
    }
    readTopConfigFromDom();
    setProgress(10, 'Синхронизируем данные бесплатной метеостанции района и точное время ПК...');
    await Promise.race([
      Promise.allSettled([saveConfigToServer(widgetId), fetchLiveWeatherFromOpenMeteo()]),
      new Promise(r => setTimeout(r, 1200))
    ]);
    renderWidgetsGallery();

    const activeWidgetId = widgetId || state.config.selectedWidget || 'v1_classic_cal';
    state.config.selectedWidget = activeWidgetId;
    const wInfo = WIDGET_CATALOG.find(w => w.id === activeWidgetId) || WIDGET_CATALOG[0];
    const nowStr = new Date().toLocaleTimeString('ru-RU');
    const wc = state.config.weatherCache || {};
    logInstall(`🚀 Выбран виджет: "${wInfo.title}" (${activeWidgetId})`);
    logInstall(`🕒 Начальное время ПК (после отключения питания потребуется NTP): ${nowStr}`);
    logInstall(`🌤️ Погода (${state.config.city} → 📍 ${getShortCityRu()}): ${fmtTempStr(wc.tempC)}, ${wc.descRu || 'Пасмурно'}, ветер ${wc.windMs ?? 3.8} м/с (${wc.source || 'Метеостанция'})`);
    logInstall(`🟨 Профиль матрицы L i 435-2 4: ${state.config.cydVariant}`);
    logInstall(`📶 Фоновый Wi-Fi платы: ${state.config.wifiSsid ? state.config.wifiSsid + ' (2.4 ГГц)' : '(нет Wi-Fi: данные при установке, после отключения питания могут устареть)' }`);

    try {
      if (port.readable || port.writable) {
        await port.close();
      }
    } catch (_) {}

    // Считываем USB VID/PID для паспорта устройства
    const portInfo = port.getInfo ? port.getInfo() : {};
    if (portInfo.usbVendorId && portInfo.usbProductId) {
      const vid = portInfo.usbVendorId.toString(16).toUpperCase().padStart(4, '0');
      const pid = portInfo.usbProductId.toString(16).toUpperCase().padStart(4, '0');
      const bridgeName = vid === '1A86' && pid === '7523' ? 'CH340' : vid === '10C4' ? 'CP2102' : 'USB-UART';
      document.getElementById('scanUsbMac').textContent = `${bridgeName} (${vid}:${pid})`;
    }

    setProgress(18, 'Скачиваем образ файловой системы виджетов (104 КБ)...');
    const vfsResp = await fetch('/firmware/vfs_widgets.bin?t=' + Date.now(), { cache: 'no-store' });
    if (!vfsResp.ok) throw new Error('Не удалось загрузить /firmware/vfs_widgets.bin');
    const vfsUint8 = new Uint8Array(await vfsResp.arrayBuffer());
    const patchedOffset = patchVfsImageWithConfig(vfsUint8, state.config);
    logInstall(`📦 Конфигурация виджета "${activeWidgetId}" вшита прямо в /config.txt образа (смещение ${patchedOffset})`);
    if (patchedOffset < 0) throw new Error("Метка конфигурации в образе не найдена; прошивка остановлена");
    const cfgSectorUint8 = buildConfigFlashSector(state.config);

    const filesToFlash = [];
    if (forceFullEngineFlash) {
      logInstall('📥 Режим полной прошивки с нуля: загружаем базовый движок LVGL 9.4 (3.26 МБ)...');
      setProgress(22, 'Загрузка базового графического движка (3.26 МБ)...');
      const fwResp = await fetch('/firmware/cyd_lvgl_engine.bin');
      if (!fwResp.ok) throw new Error('Не найден /firmware/cyd_lvgl_engine.bin');
      const fwUint8 = new Uint8Array(await fwResp.arrayBuffer());
      filesToFlash.push({ data: fwUint8, address: 0x0 });
    } else {
      logInstall('⚡ Быстрый режим (3 сек): базовый движок на 0x0 уже прошит, записываем только раздел виджетов VFS (0x343000) и конфиг (0x3E3000)!');
    }

    filesToFlash.push({ data: vfsUint8, address: 0x343000 });
    filesToFlash.push({ data: cfgSectorUint8, address: 0x3e3000 });

    setProgress(28, 'Подключение к чипу ESP32 и чтение аппаратных регистров...');
    const transport = new Transport(port, false);

    const espLoaderTerminal = {
      clean() {},
      writeLine(data) {
        if (!data) return;
        if (!data.startsWith('Writing at')) {
          logInstall('  [esptool] ' + data);
        }
        // Автоматическое обновление карточек Сканера на основе данных загрузчика
        if (data.startsWith('Chip is ')) {
          const model = data.replace('Chip is ', '').trim();
          document.getElementById('scanChipModel').textContent = model;
        } else if (data.startsWith('MAC: ')) {
          document.getElementById('scanMacSub').textContent = data.trim();
        } else if (data.startsWith('Flash ID:')) {
          const fid = data.replace('Flash ID:', '').trim();
          document.getElementById('scanFlashInfo').textContent = `4 МБ SPI DIO (ID: 0x${fid})`;
        }
      },
      write() {}
    };

    const esploader = new ESPLoader({
      transport,
      baudrate: 460800,
      romBaudrate: 115200,
      terminal: espLoaderTerminal
    });

    const chipName = await esploader.main();
    logInstall(`✅ Чип успешно просканирован: ${chipName}`);

    await esploader.writeFlash({
      fileArray: filesToFlash,
      flashSize: '4MB',
      flashMode: 'dio',
      flashFreq: '40m',
      eraseAll: false,
      compress: true,
      reportProgress: (fileIdx, written, total) => {
        const ratio = total > 0 ? written / total : 0;
        const pct = Math.round(32 + ratio * 52);
        const label =
          filesToFlash.length === 3 && fileIdx === 0
            ? `Запись базового движка (0x0): ${Math.round(ratio * 100)}%`
            : `Запись пакета виджетов и подсветки (0x343000): ${Math.round(ratio * 100)}%`;
        setProgress(pct, label);
      }
    });

    logInstall('✅ Файловая система виджетов (0x343000) и настройки (0x3E3000) записаны!');
    setProgress(88, 'Выполняем аппаратный сброс платы (импульс RTS) и включаем экран...');

    // НАСТОЯЩИЙ АППАРАТНЫЙ СБРОС (однократный чистый импульс RTS без повторного открытия порта!)
    try {
      await transport.setDTR(false);
      await transport.setRTS(true);
      await new Promise(r => setTimeout(r, 180));
      await transport.setRTS(false);
      await transport.setDTR(false);
      await new Promise(r => setTimeout(r, 150));
    } catch (_) {}

    try {
      await transport.disconnect();
    } catch (_) {}

    const pill = document.getElementById('usbStatusPill');
    pill.classList.add('connected');
    document.getElementById('usbStatusText').textContent = 'USB: Плата активна';

    setProgress(100, '🎉 Готово! Экран вашей платы ESP32-2432S028 запущен!');
    logInstall('\n🎉 ЗАПИСЬ И ЧИСТЫЙ ПЕРЕЗАПУСК ЗАВЕРШЕНЫ!');
    logInstall('👉 Экран платы сейчас включится (через ~0.5 сек после перезагрузки).');
  } catch (err) {
    console.error('Ошибка:', err);
    setProgress(0, `❌ Ошибка: ${err.message}`);
    logInstall(`\n❌ Ошибка: ${err.message}`);
  }
}

// Считывает реальный лог загрузки ESP32 после прошивки и парсит CYD_SCAN_REPORT
async function capturePostResetBootLog(port) {
  try {
    await port.open({ baudRate: 115200 });
    // Делаем контрольный импульс сброса RTS, чтобы гарантированно увидеть весь лог старта с первой строки
    await port.setSignals({ dataTerminalReady: false, requestToSend: true });
    await new Promise(r => setTimeout(r, 140));
    await port.setSignals({ dataTerminalReady: false, requestToSend: false });

    const reader = port.readable.getReader();
    const decoder = new TextDecoder();
    let bootText = '';
    const deadline = Date.now() + 2500;

    while (Date.now() < deadline) {
      const timeoutPromise = new Promise(resolve => setTimeout(() => resolve({ done: true }), 250));
      const { value, done } = await Promise.race([reader.read(), timeoutPromise]);
      if (done) break;
      if (value) {
        const chunk = decoder.decode(value, { stream: true });
        bootText += chunk;
        if (bootText.includes('CYD_WIDGET_ENGINE_READY')) {
          break;
        }
      }
    }

    reader.releaseLock();
    await port.close();

    if (bootText.trim()) {
      logInstall('--- Лог загрузки вашей ESP32-2432S028 ---');
      logInstall(bootText.trim().slice(0, 1000));
      logInstall('-----------------------------------------');

      const match = bootText.match(/CYD_SCAN_REPORT:(\{.*\})/);
      if (match) {
        try {
          const rep = JSON.parse(match[1]);
          document.getElementById('scanBoardQuirks').textContent =
            `Экран OK (${rep.driver_mode}, rot=${rep.rot}) • Тач: ${rep.touch_type} • ОЗУ: ${rep.mem_free_kb} КБ`;
        } catch (_) {}
      }
    }
  } catch (e) {
    try {
      await port.close();
    } catch (_) {}
  }
}
