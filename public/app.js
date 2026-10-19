import { ESPLoader, Transport } from '/esptool-bundle.js';

const WIDGET_CATALOG = [
  {
    id: 'v1_classic_cal',
    num: 1,
    icon: '📅',
    tag: 'Вариант 1 • Классика',
    title: 'Настольный Календарь на Месяц + Часы + Погода',
    desc: 'Сетка текущего месяца с выделением сегодняшнего дня, крупные часы, день недели и погода за окном по Wi-Fi.'
  },
  {
    id: 'v2_flip_clock',
    num: 2,
    icon: '🕰️',
    tag: 'Вариант 2 • Крупные цифры',
    title: 'Гигантские Flip-Часы во весь экран + Погода',
    desc: 'Две огромные контрастные карточки часов и минут (отлично видно издалека), дата и температура внизу экрана.'
  },
  {
    id: 'v3_tear_cal',
    num: 3,
    icon: '📆',
    tag: 'Вариант 3 • Ретро-стиль',
    title: 'Отрывной Календарь Дня (Крупное число)',
    desc: 'Стиль бумажного отрывного календаря с красной шапкой месяца, огромным числом дня, часами и сводкой погоды.'
  },
  {
    id: 'v4_weather_pro',
    num: 4,
    icon: '🌤️',
    tag: 'Вариант 4 • Погода Open-Meteo',
    title: 'Домашняя Метеостанция + Мин/Макс за день',
    desc: 'Крупная температура на улице, максимум и минимум за сутки, скорость ветра, влажность и часы по Wi-Fi.'
  },
  {
    id: 'v5_day_planner',
    num: 5,
    icon: '📝',
    tag: 'Вариант 5 • С вашими задачами',
    title: 'Органайзер Дня: Часы + Погода + 3 Главных Дела',
    desc: 'Настольные часы с погодой в шапке и 3 ваших напоминания или дела на день, которые вы вписываете прямо здесь:',
    hasNotesInput: true
  },
  {
    id: 'v6_world_clock',
    num: 6,
    icon: '🌍',
    tag: 'Вариант 6 • 3 Часовых пояса',
    title: 'Мировое Время (Ваш город + Лондон + Токио)',
    desc: 'Три стильных горизонтальных блока времени для разных часовых поясов мира с синхронизацией по NTP.'
  },
  {
    id: 'v7_countdown',
    num: 7,
    icon: '⏳',
    tag: 'Вариант 7 • Обратный отсчёт',
    title: 'Счётчик Дней до События / Праздника + Часы',
    desc: 'Настройте название события (например: «До Отпуска» или «До Нового Года») и количество дней:',
    hasEventInput: true
  },
  {
    id: 'v8_pomodoro',
    num: 8,
    icon: '🍅',
    tag: 'Вариант 8 • Сенсорный таймер',
    title: 'Таймер Фокуса Помодоро (25:00) + Настольные Часы',
    desc: 'Крупный таймер с большими сенсорными кнопками START и RESET прямо на экране вашей ESP32-2432S028 + часы и погода.'
  },
  {
    id: 'v9_night_clock',
    num: 9,
    icon: '🌙',
    tag: 'Вариант 9 • Ночной режим',
    title: 'Прикроватные Ночные Часы (Мягкий Янтарь)',
    desc: 'Тёплое янтарное свечение цифр на глубоком тёмном фоне — не слепит глаза ночью, показывает время, дату и погоду.'
  },
  {
    id: 'v10_carousel',
    num: 10,
    icon: '🔄',
    tag: 'Вариант 10 • Автосмена всех экранов',
    title: 'Карусель «Все 9 Часов и Календарей по кругу»',
    desc: 'Автоматически плавно переключает все 9 дизайнов часов, календарей и погоды каждые 12 секунд (плюс ручное переключение пальцем)!'
  }
];

const NINE_MODES = [
  'v1_classic_cal',
  'v2_flip_clock',
  'v3_tear_cal',
  'v4_weather_pro',
  'v5_day_planner',
  'v6_world_clock',
  'v7_countdown',
  'v8_pomodoro',
  'v9_night_clock'
];

let state = {
  cities: {},
  config: {
    cydVariant: 'standard',
    wifiSsid: '',
    wifiPassword: '',
    city: 'Москва',
    latitude: 55.7558,
    longitude: 37.6173,
    timezoneOffset: 3,
    selectedWidget: 'v1_classic_cal',
    notes: [
      'Утренняя разминка и кофе',
      'Посмотреть задачи на день',
      'Вечерняя прогулка в 19:00'
    ],
    eventTitle: 'До Нового Года',
    eventDays: '73 DAYS',
    weatherCache: { tempC: 14, windMs: 3.5 }
  },
  previewIdx: 0,
  pomoSec: 25 * 60,
  pomoRun: false,
  serialPort: null,
  mainPyCode: ''
};

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

  setInterval(() => {
    if (state.pomoRun && state.pomoSec > 0) {
      state.pomoSec--;
    }
    renderCydCanvas();
  }, 500);
});

async function loadInitialStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.ok) {
      state.cities = data.cities || {};
      state.config = { ...state.config, ...data.config };
      state.mainPyCode = data.mainPy || '';

      const idx = NINE_MODES.indexOf(state.config.selectedWidget);
      state.previewIdx = idx >= 0 ? idx : 0;

      populateCitiesSelect();
      document.getElementById('inputWifiSsid').value = state.config.wifiSsid || '';
      document.getElementById('inputWifiPass').value = state.config.wifiPassword || '';
      document.getElementById('selectCydVariant').value = state.config.cydVariant || 'standard';
    }
  } catch (err) {
    console.error('Ошибка загрузки статуса:', err);
  }
}

function populateCitiesSelect() {
  const sel = document.getElementById('selectCity');
  if (!sel) return;
  sel.innerHTML = '';
  Object.keys(state.cities).forEach(cityName => {
    const c = state.cities[cityName];
    const opt = document.createElement('option');
    opt.value = cityName;
    opt.textContent = `${cityName} (UTC+${c.tz})`;
    if (state.config.city === cityName) opt.selected = true;
    sel.appendChild(opt);
  });
}

function readTopConfigFromDom() {
  state.config.wifiSsid = document.getElementById('inputWifiSsid').value.trim();
  state.config.wifiPassword = document.getElementById('inputWifiPass').value;
  state.config.city = document.getElementById('selectCity').value || 'Москва';
  state.config.cydVariant = document.getElementById('selectCydVariant').value || 'standard';

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
  if (eDaysEl) state.config.eventDays = eDaysEl.value.trim() || '73 DAYS';
}

async function saveConfigToServer(widgetId) {
  readTopConfigFromDom();
  if (widgetId) {
    state.config.selectedWidget = widgetId;
  }
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state.config)
  });
  const data = await res.json();
  if (data.ok) {
    state.config = data.config;
    state.mainPyCode = data.mainPy;
  }
  return data;
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
          👁️ Посмотреть на экране слева
        </button>
        <button class="btn btn-install" data-install="${item.id}">
          ⚡ Установить на мой ESP32-2432S028
        </button>
      </div>
    `;

    container.appendChild(card);
  });

  container.querySelectorAll('[data-preview]').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.preview;
      readTopConfigFromDom();
      state.config.selectedWidget = id;
      const idx = NINE_MODES.indexOf(id);
      state.previewIdx = idx >= 0 ? idx : 0;
      renderWidgetsGallery();
      renderCydCanvas();
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
// ОТРИСОВКА ВСЕХ 10 ВАРИАЦИЙ НА ЭКРАНЕ 320x240
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
    badge.textContent = `Стиль ${state.previewIdx + 1} из 9 (Переключение касанием)`;
  }

  ctx.fillStyle = '#070B14';
  ctx.fillRect(0, 0, W, H);

  // Верхняя шапка (320x24)
  ctx.fillStyle = '#101C33';
  ctx.fillRect(0, 0, W, 24);

  const topTitles = [
    '1/9 CLASSIC CALENDAR',
    '2/9 GIANT FLIP CLOCK',
    '3/9 TEAR-OFF DAY CALENDAR',
    '4/9 WEATHER STATION',
    '5/9 DAILY PLANNER',
    '6/9 WORLD CLOCK (3 ZONES)',
    '7/9 EVENT COUNTDOWN',
    '8/9 POMODORO & CLOCK',
    '9/9 NIGHT AMBER CLOCK'
  ];

  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 11px sans-serif';
  ctx.fillText(topTitles[state.previewIdx] || 'ESP32-2432S028', 8, 16);

  ctx.fillStyle = '#10B981';
  ctx.font = 'bold 11px monospace';
  const rightTxt = `${state.config.city || 'Москва'} OK`;
  ctx.fillText(rightTxt, W - ctx.measureText(rightTxt).width - 8, 16);

  const now = new Date();
  if (modeId === 'v1_classic_cal') drawV1ClassicCal(ctx, now);
  else if (modeId === 'v2_flip_clock') drawV2FlipClock(ctx, now);
  else if (modeId === 'v3_tear_cal') drawV3TearCal(ctx, now);
  else if (modeId === 'v4_weather_pro') drawV4WeatherPro(ctx, now);
  else if (modeId === 'v5_day_planner') drawV5DayPlanner(ctx, now);
  else if (modeId === 'v6_world_clock') drawV6WorldClock(ctx, now);
  else if (modeId === 'v7_countdown') drawV7Countdown(ctx, now);
  else if (modeId === 'v8_pomodoro') drawV8Pomodoro(ctx, now);
  else drawV9NightClock(ctx, now);

  // Нижняя сенсорная панель [< PREV] [TOUCH TO SWITCH] [NEXT >]
  ctx.fillStyle = '#0E172A';
  ctx.fillRect(0, 206, W, 34);

  // Кнопка < PREV
  ctx.fillStyle = '#0284C7';
  ctx.beginPath();
  ctx.roundRect(8, 210, 88, 26, 6);
  ctx.fill();
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 11px sans-serif';
  ctx.fillText('< PREV', 30, 227);

  ctx.fillStyle = '#94A3B8';
  ctx.font = 'bold 10px sans-serif';
  ctx.fillText('TOUCH TO SWITCH', 114, 226);

  // Кнопка NEXT >
  ctx.fillStyle = '#0284C7';
  ctx.beginPath();
  ctx.roundRect(224, 210, 88, 26, 6);
  ctx.fill();
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 11px sans-serif';
  ctx.fillText('NEXT >', 248, 227);
}

function drawV1ClassicCal(ctx, now) {
  const hhmm = now.toTimeString().slice(0, 5);
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 34px monospace';
  ctx.fillText(hhmm, 10, 62);

  const daysRu = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 11px sans-serif';
  ctx.fillText(daysRu[now.getDay()], 10, 82);

  const dStr = `${String(now.getDate()).padStart(2, '0')}.${String(now.getMonth() + 1).padStart(2, '0')}.${now.getFullYear()}`;
  ctx.fillStyle = '#94A3B8';
  ctx.fillText(dStr, 10, 98);

  ctx.fillStyle = '#111E36';
  ctx.beginPath();
  ctx.roundRect(8, 110, 126, 82, 8);
  ctx.fill();

  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 12px sans-serif';
  ctx.fillText(`📍 ${state.config.city}`, 16, 132);
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText(`+14 °C`, 16, 154);
  ctx.fillStyle = '#10B981';
  ctx.fillText(`Ветер 3.5 м/с`, 16, 174);

  // Сетка календаря
  ctx.fillStyle = '#0D1526';
  ctx.strokeStyle = '#1E3A5F';
  ctx.beginPath();
  ctx.roundRect(142, 30, 172, 168, 8);
  ctx.fill();
  ctx.stroke();

  const year = now.getFullYear();
  const month = now.getMonth();
  const today = now.getDate();
  const monthsRu = ['ЯНВАРЬ', 'ФЕВРАЛЬ', 'МАРТ', 'АПРЕЛЬ', 'МАЙ', 'ИЮНЬ', 'ИЮЛЬ', 'АВГУСТ', 'СЕНТЯБРЬ', 'ОКТЯБРЬ', 'НОЯБРЬ', 'ДЕКАБРЬ'];
  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 10px sans-serif';
  ctx.fillText(`${monthsRu[month]} ${year}`, 152, 46);

  const hdr = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  ctx.font = 'bold 9px sans-serif';
  hdr.forEach((h, i) => {
    ctx.fillStyle = i >= 5 ? '#FB7185' : '#94A3B8';
    ctx.fillText(h, 149 + i * 23, 62);
  });

  const firstDow = (new Date(year, month, 1).getDay() + 6) % 7;
  const totalDays = new Date(year, month + 1, 0).getDate();
  let r = 0, c = firstDow;
  ctx.font = 'bold 10px monospace';
  for (let d = 1; d <= totalDays; d++) {
    const x = 149 + c * 23;
    const y = 78 + r * 20;
    if (d === today) {
      ctx.fillStyle = '#00E5FF';
      ctx.beginPath();
      ctx.roundRect(x - 3, y - 10, 19, 14, 3);
      ctx.fill();
      ctx.fillStyle = '#000000';
    } else if (c >= 5) {
      ctx.fillStyle = '#FB7185';
    } else {
      ctx.fillStyle = '#FFFFFF';
    }
    ctx.fillText(d < 10 ? ` ${d}` : `${d}`, x, y);
    c++;
    if (c >= 7) {
      c = 0;
      r++;
    }
  }
}

function drawV2FlipClock(ctx, now) {
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');

  [hh, mm].forEach((val, i) => {
    ctx.fillStyle = '#142038';
    ctx.strokeStyle = '#243B61';
    ctx.beginPath();
    ctx.roundRect(16 + i * 152, 36, 136, 118, 14);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = i === 0 ? '#00E5FF' : '#FFFFFF';
    ctx.font = 'bold 64px monospace';
    ctx.fillText(val, 44 + i * 152, 116);
  });

  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 14px sans-serif';
  const dStr = `${now.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'short' })}  |  ${state.config.city} +14°C`;
  ctx.fillText(dStr, 22, 184);
}

function drawV3TearCal(ctx, now) {
  // Лист отрывного календаря слева
  ctx.fillStyle = '#F8FAFC';
  ctx.beginPath();
  ctx.roundRect(12, 34, 154, 162, 12);
  ctx.fill();

  ctx.fillStyle = '#EF4444';
  ctx.beginPath();
  ctx.roundRect(12, 34, 154, 34, [12, 12, 0, 0]);
  ctx.fill();

  const monthsRu = ['ЯНВАРЬ', 'ФЕВРАЛЬ', 'МАРТ', 'АПРЕЛЬ', 'МАЙ', 'ИЮНЬ', 'ИЮЛЬ', 'АВГУСТ', 'СЕНТЯБРЬ', 'ОКТЯБРЬ', 'НОЯБРЬ', 'ДЕКАБРЬ'];
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 13px sans-serif';
  ctx.fillText(`${monthsRu[now.getMonth()]} ${now.getFullYear()}`, 32, 56);

  ctx.fillStyle = '#0F172A';
  ctx.font = 'bold 64px sans-serif';
  const dayTxt = String(now.getDate());
  ctx.fillText(dayTxt, 89 - ctx.measureText(dayTxt).width / 2, 136);

  const daysRu = ['ВОСКРЕСЕНЬЕ', 'ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА'];
  ctx.fillStyle = '#475569';
  ctx.font = 'bold 12px sans-serif';
  const wTxt = daysRu[now.getDay()];
  ctx.fillText(wTxt, 89 - ctx.measureText(wTxt).width / 2, 180);

  // Правая карточка с часами и погодой
  ctx.fillStyle = '#101C33';
  ctx.beginPath();
  ctx.roundRect(176, 34, 132, 162, 12);
  ctx.fill();

  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 28px monospace';
  ctx.fillText(now.toTimeString().slice(0, 5), 198, 76);

  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 15px sans-serif';
  ctx.fillText(state.config.city, 192, 116);

  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 22px monospace';
  ctx.fillText('+14 °C', 192, 148);

  ctx.fillStyle = '#10B981';
  ctx.font = '12px sans-serif';
  ctx.fillText('Ветер 3.5 м/с', 192, 174);
}

function drawV4WeatherPro(ctx, now) {
  ctx.fillStyle = '#101C33';
  ctx.beginPath();
  ctx.roundRect(10, 32, 300, 164, 12);
  ctx.fill();

  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 17px sans-serif';
  ctx.fillText(`📍 ${state.config.city}   |   ${now.toTimeString().slice(0, 5)}`, 22, 58);

  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 48px monospace';
  ctx.fillText('+14 °C', 22, 114);

  ctx.fillStyle = '#10B981';
  ctx.font = 'bold 13px sans-serif';
  ctx.fillText('Макс: +17°C   Мин: +12°C', 22, 148);
  ctx.fillStyle = '#FBBF24';
  ctx.fillText('Ветер: 3.5 м/с   Влажность: 64%', 22, 174);
}

function drawV5DayPlanner(ctx, now) {
  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 16px sans-serif';
  ctx.fillText(`🕒 ${now.toTimeString().slice(0, 5)}  |  ${state.config.city} +14°C`, 14, 50);

  const notes = state.config.notes || [];
  for (let i = 0; i < 3; i++) {
    ctx.fillStyle = '#111E36';
    ctx.beginPath();
    ctx.roundRect(12, 64 + i * 44, 296, 36, 8);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '13px sans-serif';
    ctx.fillText(`[${i + 1}] ${(notes[i] || 'Свободное время').slice(0, 34)}`, 22, 87 + i * 44);
  }
}

function drawV6WorldClock(ctx, now) {
  const utcH = (now.getUTCHours() + 24) % 24;
  const tokyoH = (now.getUTCHours() + 9) % 24;
  const mm = String(now.getMinutes()).padStart(2, '0');

  const zones = [
    { name: `${state.config.city} (Дом)`, time: now.toTimeString().slice(0, 5), color: '#00E5FF' },
    { name: 'London / UTC', time: `${String(utcH).padStart(2, '0')}:${mm}`, color: '#10B981' },
    { name: 'Tokyo (JST)', time: `${String(tokyoH).padStart(2, '0')}:${mm}`, color: '#FBBF24' }
  ];

  zones.forEach((z, i) => {
    ctx.fillStyle = '#111E36';
    ctx.beginPath();
    ctx.roundRect(12, 34 + i * 54, 296, 46, 10);
    ctx.fill();

    ctx.fillStyle = z.color;
    ctx.font = 'bold 15px sans-serif';
    ctx.fillText(z.name, 24, 62 + i * 54);

    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 24px monospace';
    ctx.fillText(z.time, 224, 65 + i * 54);
  });
}

function drawV7Countdown(ctx, now) {
  ctx.fillStyle = '#111E36';
  ctx.beginPath();
  ctx.roundRect(12, 34, 296, 162, 14);
  ctx.fill();

  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 17px sans-serif';
  const title = (state.config.eventTitle || 'ДО НОВОГО ГОДА').toUpperCase();
  ctx.fillText(title, 160 - ctx.measureText(title).width / 2, 66);

  ctx.fillStyle = '#10B981';
  ctx.font = 'bold 42px monospace';
  const days = state.config.eventDays || '73 DAYS';
  ctx.fillText(days, 160 - ctx.measureText(days).width / 2, 124);

  ctx.fillStyle = '#FBBF24';
  ctx.font = 'bold 13px sans-serif';
  const sub = `Сейчас: ${now.toTimeString().slice(0, 5)}  |  ${state.config.city} +14°C`;
  ctx.fillText(sub, 160 - ctx.measureText(sub).width / 2, 174);
}

function drawV8Pomodoro(ctx, now) {
  const mins = String(Math.floor(state.pomoSec / 60)).padStart(2, '0');
  const secs = String(state.pomoSec % 60).padStart(2, '0');

  ctx.fillStyle = '#F59E0B';
  ctx.font = 'bold 46px monospace';
  ctx.fillText(`${mins}:${secs}`, 92, 82);

  // Кнопки START и RESET
  ctx.fillStyle = state.pomoRun ? '#EF4444' : '#10B981';
  ctx.beginPath();
  ctx.roundRect(30, 104, 120, 42, 8);
  ctx.fill();
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 14px sans-serif';
  ctx.fillText(state.pomoRun ? 'PAUSE' : 'START', 66, 130);

  ctx.fillStyle = '#1E293B';
  ctx.beginPath();
  ctx.roundRect(170, 104, 120, 42, 8);
  ctx.fill();
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText('RESET 25:00', 188, 130);

  ctx.fillStyle = '#00E5FF';
  ctx.font = 'bold 13px sans-serif';
  ctx.fillText(`Часы: ${now.toTimeString().slice(0, 5)}  |  ${state.config.city} +14°C`, 54, 184);
}

function drawV9NightClock(ctx, now) {
  ctx.fillStyle = '#FFB000';
  ctx.font = 'bold 58px monospace';
  ctx.fillText(now.toTimeString().slice(0, 5), 76, 114);

  ctx.fillStyle = '#B45309';
  ctx.font = 'bold 15px sans-serif';
  const dStr = `${now.toLocaleDateString('ru-RU')}  •  ${state.config.city} +14°C`;
  ctx.fillText(dStr, 160 - ctx.measureText(dStr).width / 2, 162);
}

// ============================================================================
// СОБЫТИЯ И НАВИГАЦИЯ
// ============================================================================
function setupEventListeners() {
  const canvas = document.getElementById('cydCanvas');
  canvas?.addEventListener('click', e => {
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 320;
    const y = ((e.clientY - rect.top) / rect.height) * 240;

    // Кнопка < PREV
    if (y >= 206 && x <= 104) {
      state.previewIdx = (state.previewIdx - 1 + NINE_MODES.length) % NINE_MODES.length;
      state.config.selectedWidget = NINE_MODES[state.previewIdx];
      renderWidgetsGallery();
      renderCydCanvas();
      return;
    }
    // Кнопка NEXT >
    if (y >= 206 && x >= 216) {
      state.previewIdx = (state.previewIdx + 1) % NINE_MODES.length;
      state.config.selectedWidget = NINE_MODES[state.previewIdx];
      renderWidgetsGallery();
      renderCydCanvas();
      return;
    }

    // Кнопки Помодоро в Варианте 8
    if (NINE_MODES[state.previewIdx] === 'v8_pomodoro' && y >= 104 && y <= 146) {
      if (x >= 30 && x <= 150) {
        state.pomoRun = !state.pomoRun;
        renderCydCanvas();
      } else if (x >= 170 && x <= 290) {
        state.pomoRun = false;
        state.pomoSec = 25 * 60;
        renderCydCanvas();
      }
    }
  });

  ['inputWifiSsid', 'inputWifiPass', 'selectCity', 'selectCydVariant'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => {
      saveConfigToServer();
      renderCydCanvas();
    });
  });

  document.getElementById('btnInstallActivePreview')?.addEventListener('click', () => {
    runOneClickInstall(state.config.selectedWidget || NINE_MODES[state.previewIdx], false);
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

  document.getElementById('btnCopyQuickStart')?.addEventListener('click', async () => {
    const cmd = 'git clone -b arena/0c74c634-esp32 https://github.com/e6six/esp32.git && cd esp32 && node server.js';
    await navigator.clipboard.writeText(cmd);
    const btn = document.getElementById('btnCopyQuickStart');
    const orig = btn.textContent;
    btn.textContent = '✅ Скопировано!';
    setTimeout(() => (btn.textContent = orig), 2200);
  });
}

// ============================================================================
// УСТАНОВКА В 1 КЛИК НА ESP32-2432S028
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

async function runOneClickInstall(widgetId, forceFullFlash = false) {
  const modal = document.getElementById('installModal');
  const logBox = document.getElementById('modalInstallLog');
  logBox.textContent = '';
  modal.classList.add('open');

  setProgress(5, 'Сохраняем выбранный вариант часов/календаря, Wi-Fi и город...');
  await saveConfigToServer(widgetId);
  renderWidgetsGallery();

  const wInfo = WIDGET_CATALOG.find(w => w.id === widgetId) || WIDGET_CATALOG[0];
  logInstall(`🚀 Выбран дизайн: "${wInfo.title}"`);
  logInstall(`📶 Wi-Fi: ${state.config.wifiSsid ? state.config.wifiSsid : '(не указан)'}`);
  logInstall(`🌤️ Город погоды: ${state.config.city} (Lat ${state.config.latitude}, Lon ${state.config.longitude})`);

  if (!('serial' in navigator)) {
    setProgress(0, '⚠️ Откройте сайт в отдельной вкладке Chrome / Edge / Яндекс / Opera');
    logInstall('\n❌ Браузер ограничил доступ к USB во встроенном окне.');
    logInstall('👉 Нажмите «↗ Открыть в новой вкладке» вверху справа и нажмите «Установить» ещё раз!');
    return;
  }

  try {
    setProgress(10, 'Выберите USB COM-порт вашей платы ESP32-2432S028...');
    let port = state.serialPort;
    if (!port) {
      port = await navigator.serial.requestPort();
      state.serialPort = port;
    }

    try {
      if (port.readable || port.writable) {
        await port.close();
      }
    } catch (_) {}

    let hasWidgetEngine = false;
    if (!forceFullFlash) {
      setProgress(15, 'Проверяем текущую прошивку на вашей ESP32-2432S028...');
      logInstall('🔍 Проверяем, установлен ли уже графический движок или на плате сейчас Bruce 1.11.1...');
      hasWidgetEngine = await probeMicroPythonRepl(port);
    }

    if (!hasWidgetEngine || forceFullFlash) {
      logInstall('⚡ Заменяем Bruce 1.11.1 на графический движок LVGL 9.4 для ESP32-2432S028...');
      setProgress(20, 'Загрузка графического движка ESP32-2432S028...');

      const fwResp = await fetch('/firmware/cyd_lvgl_engine.bin');
      if (!fwResp.ok) throw new Error('Не найден файл /firmware/cyd_lvgl_engine.bin');
      const fwUint8 = new Uint8Array(await fwResp.arrayBuffer());
      logInstall(`✅ Движок загружен (${(fwUint8.length / (1024 * 1024)).toFixed(2)} МБ). Начинаем прошивку...`);

      const transport = new Transport(port, false);
      const espLoaderTerminal = {
        clean() {},
        writeLine(data) {
          if (data && !data.startsWith('Writing at')) logInstall('  [esptool] ' + data);
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
      logInstall(`✅ Подключено к чипу: ${chipName}`);

      await esploader.writeFlash({
        fileArray: [{ data: fwUint8, address: 0x0 }],
        flashSize: '4MB',
        flashMode: 'dio',
        flashFreq: '40m',
        eraseAll: false,
        compress: true,
        reportProgress: (fileIdx, written, total) => {
          const ratio = total > 0 ? written / total : 0;
          const pct = Math.round(30 + ratio * 52);
          setProgress(pct, `Прошивка движка ESP32-2432S028: ${Math.round(ratio * 100)}%`);
        }
      });

      logInstall('✅ Графический движок успешно прошит! Перезагружаем плату...');
      await esploader.after('hard_reset');
      try {
        await transport.disconnect();
      } catch (_) {}

      setProgress(85, 'Запуск графического движка (2.5 сек)...');
      await new Promise(r => setTimeout(r, 2600));
    } else {
      logInstall('✅ Графический движок уже стоит на плате! Обновляем дизайн за 2 секунды.');
    }

    setProgress(88, 'Записываем выбранный календарь/часы, Wi-Fi и город в память платы...');
    logInstall('📤 Загружаем все 10 вариаций часов/календарей и ваши настройки Wi-Fi в /main.py...');

    await uploadMainPyOverRawRepl(port, state.mainPyCode, pct => {
      setProgress(88 + Math.round(pct * 0.11), `Запись виджета и Wi-Fi: ${pct}%`);
    });

    const pill = document.getElementById('usbStatusPill');
    pill.classList.add('connected');
    document.getElementById('usbStatusText').textContent = 'USB: ESP32-2432S028 Готов';

    setProgress(100, '🎉 Готово! Часы, календарь и погода запущены на вашей ESP32-2432S028!');
    logInstall('\n🎉 УСПЕШНО УСТАНОВЛЕНО!');
    logInstall('👉 Вы также можете переключать все 9 стилей часов и календарей прямо пальцем по кнопкам [< PREV] и [NEXT >] на экране вашей платы!');
  } catch (err) {
    console.error('Ошибка установки:', err);
    setProgress(0, `❌ Ошибка: ${err.message}`);
    logInstall(`\n❌ Ошибка: ${err.message}`);
  }
}

async function probeMicroPythonRepl(port) {
  try {
    await port.open({ baudRate: 115200 });
    const writer = port.writable.getWriter();
    const reader = port.readable.getReader();

    await writer.write(new Uint8Array([0x03, 0x03, 0x0d, 0x0a]));
    await new Promise(r => setTimeout(r, 180));
    await writer.write(new TextEncoder().encode('\r\nprint("CYD_MPY_OK")\r\n'));

    let collected = '';
    const decoder = new TextDecoder();
    const deadline = Date.now() + 850;

    while (Date.now() < deadline) {
      const timeoutPromise = new Promise(resolve => setTimeout(() => resolve({ done: true }), 220));
      const { value, done } = await Promise.race([reader.read(), timeoutPromise]);
      if (done) break;
      if (value) {
        collected += decoder.decode(value, { stream: true });
        if (collected.includes('CYD_MPY_OK') || collected.includes('>>> ')) {
          reader.releaseLock();
          writer.releaseLock();
          await port.close();
          return true;
        }
      }
    }

    reader.releaseLock();
    writer.releaseLock();
    await port.close();
    return false;
  } catch (_) {
    try {
      await port.close();
    } catch (_) {}
    return false;
  }
}

async function uploadMainPyOverRawRepl(port, pythonCode, onProgress) {
  await port.open({ baudRate: 115200 });
  const writer = port.writable.getWriter();

  const sendRaw = async str => {
    await writer.write(new TextEncoder().encode(str));
  };

  await writer.write(new Uint8Array([0x03, 0x03]));
  await new Promise(r => setTimeout(r, 250));
  await writer.write(new Uint8Array([0x01]));
  await new Promise(r => setTimeout(r, 200));

  const utf8Bytes = new TextEncoder().encode(pythonCode);
  let binaryStr = '';
  for (let i = 0; i < utf8Bytes.length; i++) {
    binaryStr += String.fromCharCode(utf8Bytes[i]);
  }
  const b64 = btoa(binaryStr);

  await sendRaw("import binascii\nf = open('main.py', 'wb')\n");
  const chunkSize = 256;
  for (let offset = 0; offset < b64.length; offset += chunkSize) {
    const slice = b64.slice(offset, offset + chunkSize);
    await sendRaw(`f.write(binascii.a2b_base64('${slice}'))\n`);
    await new Promise(r => setTimeout(r, 25));
    if (onProgress) {
      onProgress(Math.min(99, Math.round(((offset + chunkSize) / b64.length) * 100)));
    }
  }

  await sendRaw("f.close()\n");
  await writer.write(new Uint8Array([0x04]));
  await new Promise(r => setTimeout(r, 450));

  await sendRaw("import machine\nmachine.reset()\n");
  await writer.write(new Uint8Array([0x04]));
  await new Promise(r => setTimeout(r, 150));

  try {
    await port.setSignals({ dataTerminalReady: false, requestToSend: true });
    await new Promise(r => setTimeout(r, 120));
    await port.setSignals({ dataTerminalReady: false, requestToSend: false });
  } catch (_) {}

  writer.releaseLock();
  if (onProgress) onProgress(100);
}
