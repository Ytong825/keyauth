/* ============================================================
   KeyAuth 管理后台
   ============================================================ */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };

  /* ---------------------------------------------------------- 导航 */
  var NAV = [
    { group: '运营' },
    { id: 'overview', name: '概览', sub: '系统运行状况', icon: 'grid' },
    { id: 'gen', name: '制卡', sub: '批量生成卡密', icon: 'plus' },
    { id: 'cards', name: '卡密库', sub: '查询与管理全部卡密', icon: 'key' },
    { group: '配置' },
    { id: 'apps', name: '应用', sub: '每个软件一套独立密钥', icon: 'box' },
    { id: 'plans', name: '套餐', sub: '制卡预设', icon: 'tag' },
    { id: 'agents', name: '代理商', sub: '分配应用与制卡配额', icon: 'users' },
    { group: '记录' },
    { id: 'logs', name: '校验日志', sub: '全部验证请求', icon: 'list' },
    { id: 'audits', name: '操作审计', sub: '后台管理动作留痕', icon: 'shield' },
    { group: '集成' },
    { id: 'webhooks', name: 'WebHook', sub: '事件推送到你的服务器', icon: 'zap' },
    { id: 'notices', name: '公告', sub: '随校验下发到客户端', icon: 'bell' },
    { id: 'docs', name: '接入文档', sub: '把验证接进你的软件', icon: 'code' },
    { group: '系统' },
    { id: 'settings', name: '系统设置', sub: '站点与安全策略', icon: 'settings' }
  ];

  var ICONS = {
    grid: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    key: '<circle cx="8" cy="16" r="4"/><path d="M11 13 20 4M17 7l2.5 2.5M19.5 4.5 22 7"/>',
    box: '<path d="M21 16V8a2 2 0 00-1-1.7l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.7l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><path d="M3.3 7L12 12l8.7-5M12 22V12"/>',
    tag: '<path d="M20.6 13.4l-7.2 7.2a2 2 0 01-2.8 0l-7.2-7.2a2 2 0 01-.6-1.4V4a1 1 0 011-1h8a2 2 0 011.4.6l7.2 7.2a2 2 0 010 2.6z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    users: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>',
    zap: '<path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/>',
    bell: '<path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0"/>',
    code: '<path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-2.7 1.1V21a2 2 0 11-4 0v-.1A1.6 1.6 0 006.6 19l-.1.1a2 2 0 11-2.8-2.8l.1-.1A1.6 1.6 0 003 13.6H3a2 2 0 110-4h.1A1.6 1.6 0 004.9 7l-.1-.1a2 2 0 112.8-2.8l.1.1A1.6 1.6 0 0010.4 3V3a2 2 0 114 0v.1A1.6 1.6 0 0017.1 5l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 001.1 2.7H21a2 2 0 110 4h-.1a1.6 1.6 0 00-1.5 1z"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>',
    trash: '<path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>',
    ban: '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>',
    unlock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 019.9-1"/>',
    refresh: '<path d="M21 12a9 9 0 11-3-6.7M21 3v6h-6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    rotate: '<path d="M3 12a9 9 0 019-9 9 9 0 016.7 3M21 3v6h-6M21 12a9 9 0 01-9 9 9 9 0 01-6.7-3M3 21v-6h6"/>',
    edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
    check: '<path d="M20 6L9 17l-5-5"/>',
    x: '<path d="M18 6L6 18M6 6l12 12"/>',
    eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    down: '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    save: '<path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    users: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/>'
  };

  function ic(name, size) {
    var s = size || 24;
    return '<svg viewBox="0 0 24 24" width="' + s + '" height="' + s + '" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      (ICONS[name] || '') + '</svg>';
  }

  /* ---------------------------------------------------------- 状态 */
  /* 支持 /admin?t=令牌 免手填：把 URL 里的令牌落到 localStorage */
  (function(){try{var q=new URLSearchParams(location.search).get('t');
    if(q){localStorage.setItem('ka_token',q);}}catch(e){}})();
  var TOKEN = localStorage.getItem('ka_token') || '';
  var CURRENT = 'overview';
  var cardPage = 1, cardSize = 50, cardSel = {}, lastCodes = [], lastBatch = '';
  // 最近一次列表接口返回的卡密对象，点行看详情时直接查这里，不再发请求
  var CARD_CACHE = {};
  // 最近一次拿到的令牌强度（概览或设置页都会更新），「知道了」按钮按它记忆
  var LAST_TOKEN_CHECK = {};
  var PLAN_CACHE = [], APP_CACHE = [], RESULT_TEXT = {};

  /* ---------------------------------------------------------- 工具 */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function short(s, n) {
    n = n || 14;
    s = String(s || '');
    return s.length > n ? s.slice(0, n - 6) + '…' + s.slice(-4) : (s || '-');
  }

  function api(path, opt) {
    opt = opt || {};
    var h = { 'Content-Type': 'application/json', 'X-Admin-Token': TOKEN };
    if (opt.headers) { for (var k in opt.headers) { h[k] = opt.headers[k]; } }
    return fetch(path, { method: opt.method || 'GET', headers: h, body: opt.body })
      .then(function (r) {
        if (r.status === 401) { throw new Error('NO_AUTH'); }
        return r.json();
      })
      .then(function (d) {
        if (d && d.ok === false && d.err === 'NO_AUTH') { throw new Error('NO_AUTH'); }
        setConn(true, '已连接');
        return d;
      })
      .catch(function (e) {
        if (e && e.message === 'NO_AUTH') { setConn(false, '令牌无效'); login(); }
        else { setConn(false, '无法连接'); }
        throw e;
      });
  }

  function post(path, body) {
    return api(path, { method: 'POST', body: JSON.stringify(body || {}) });
  }

  function setConn(ok, txt) {
    $('connDot').className = 'dot ' + (ok ? 'on' : 'off');
    $('connTxt').textContent = txt;
  }

  var _timers = {};
  function debounced(fn, arg) {
    var key = fn.name || 'd';
    clearTimeout(_timers[key]);
    _timers[key] = setTimeout(function () { fn(arg); }, 320);
  }

  function fmtNum(n) { return String(n == null ? 0 : n); }

  /* ---------------------------------------------------------- Toast */
  function toast(msg, type) {
    var color = type === 'error' ? 'var(--danger)'
      : (type === 'warn' ? 'var(--warn)' : 'var(--success)');
    var icon = type === 'error' ? 'alert' : 'check';
    var el = document.createElement('div');
    el.className = 'toast';
    el.innerHTML = '<span style="color:' + color + '">' + ic(icon, 17) + '</span>' +
      '<span class="body">' + esc(msg) + '</span>';
    $('toasts').appendChild(el);
    setTimeout(function () {
      el.className = 'toast out';
      setTimeout(function () { if (el.parentNode) { el.parentNode.removeChild(el); } }, 200);
    }, 2600);
  }

  /* ---------------------------------------------------------- 复制 */
  function copyText(text, okMsg) {
    var done = function () { toast(okMsg || '已复制'); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, function () { fb(text, done); });
    } else { fb(text, done); }
  }
  function fb(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { toast('复制失败', 'error'); }
    document.body.removeChild(ta);
  }

  /* ---------------------------------------------------------- 弹窗 */
  function modal(opts) {
    closeModal();
    var wrap = document.createElement('div');
    wrap.className = 'mask';
    wrap.onclick = function (e) { if (e.target === wrap) { closeModal(); } };
    var m = document.createElement('div');
    m.className = 'modal';
    if (opts.width) { m.style.maxWidth = opts.width; }
    m.innerHTML =
      '<div class="modal-head"><h3>' + esc(opts.title) + '</h3>' +
      '<button class="x-btn">' + ic('x', 15) + '</button></div>' +
      '<div class="modal-body">' + (opts.body || '') + '</div>' +
      (opts.noFoot ? '' :
        '<div class="modal-foot">' +
        '<button class="btn" data-act="cancel">' + esc(opts.cancelText || '取消') + '</button>' +
        '<button class="btn ' + (opts.danger ? 'danger' : 'primary') + '" data-act="ok">' +
        esc(opts.okText || '确定') + '</button></div>');
    wrap.appendChild(m);
    $('modalRoot').appendChild(wrap);
    m.querySelector('.x-btn').onclick = closeModal;
    var c = m.querySelector('[data-act=cancel]');
    if (c) { c.onclick = closeModal; }
    var o = m.querySelector('[data-act=ok]');
    if (o) {
      o.onclick = function () {
        if (opts.onOk && opts.onOk(m) === false) { return; }
        closeModal();
      };
    }
    if (opts.onMount) { opts.onMount(m); }
    return m;
  }
  function closeModal() { $('modalRoot').innerHTML = ''; }

  function closeMenu() { $('menuRoot').innerHTML = ''; }
  function openMenu(anchor, items) {
    closeMenu();
    var r = anchor.getBoundingClientRect();
    var el = document.createElement('div');
    el.className = 'menu';
    el.innerHTML = items.map(function (it, i) {
      if (it.sep) { return '<div class="menu-sep"></div>'; }
      return '<div class="menu-item' + (it.danger ? ' danger' : '') + '" data-i="' + i + '">' +
        ic(it.icon || 'check', 13.5) + esc(it.label) + '</div>';
    }).join('');
    $('menuRoot').appendChild(el);
    var w = el.offsetWidth || 172, h = el.offsetHeight || 200;
    var left = Math.min(r.right - w, window.innerWidth - w - 12);
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - 12) { top = Math.max(12, r.top - h - 6); }
    el.style.left = Math.max(12, left) + 'px';
    el.style.top = top + 'px';
    el.querySelectorAll('.menu-item').forEach(function (node) {
      node.onclick = function () {
        var it = items[parseInt(node.getAttribute('data-i'), 10)];
        closeMenu();
        if (it.onClick) { it.onClick(); }
      };
    });
    setTimeout(function () { document.addEventListener('click', closeMenu, { once: true }); }, 0);
  }

  /* ---------------------------------------------------------- 主题 */
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('ka_theme', t);
    $('themeBtn').innerHTML = ic(t === 'dark' ? 'sun' : 'moon', 14) +
      '<span>' + (t === 'dark' ? '浅色模式' : '深色模式') + '</span>';
  }
  function toggleThemeCb() {
    applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  }
  function toggleSidebar() { $('sidebar').classList.toggle('open'); }

  /* ---------------------------------------------------------- 路由 */
  function go(id) {
    CURRENT = id;
    document.querySelectorAll('.page').forEach(function (p) {
      p.classList.toggle('active', p.id === 'page-' + id);
    });
    document.querySelectorAll('.nav-item').forEach(function (n) {
      n.classList.toggle('active', n.getAttribute('data-id') === id);
    });
    var item = NAV.filter(function (n) { return n.id === id; })[0];
    if (item) { $('pgTitle').textContent = item.name; $('pgSub').textContent = item.sub; }
    $('sidebar').classList.remove('open');
    loadFor(id);
  }
  function loadFor(id) {
    ({
      overview: loadOverview, gen: loadGenOptions, cards: function () { loadCards(1); },
      apps: loadApps, plans: loadPlans, agents: loadAgents, logs: loadLogs,
      audits: loadAudits, webhooks: loadWebhooks, notices: loadNotices,
      settings: loadSettings, docs: fillDocs
    }[id] || function () {})();
  }

  /* ============================================================
     概览
     ============================================================ */
  function loadOverview() {
    api('/api/admin/overview').then(function (d) {
      if (!d.ok) { return; }
      RESULT_TEXT = d.result_text || {};
      var s = d.stats;
      var cards = [
        { lbl: '卡密总数', val: s.cards_total,
          foot: s.apps + ' 个应用 / ' + s.plans + ' 个套餐 · 已封禁 ' + (s.cards_banned || 0),
          icon: 'key', cls: 'i-primary' },
        { lbl: '未使用', val: s.cards_unused, foot: '等待首次激活', icon: 'shield', cls: 'i-info' },
        { lbl: '使用中', val: s.cards_active, foot: '已激活的卡密', icon: 'check', cls: 'i-success' },
        { lbl: '今日新增', val: s.cards_today || 0, foot: '今天签发的卡密', icon: 'plus', cls: 'i-info' },
        { lbl: '绑定设备', val: s.devices, foot: '近 5 分钟在线 ' + s.online, icon: 'box', cls: 'i-info' },
        { lbl: '今日校验', val: s.checks_today,
          foot: '累计 ' + s.checks_total + ' 次 · 活跃卡 ' + (s.active_today || 0),
          icon: 'activity', cls: 'i-warn' }
      ];
      $('statGrid').innerHTML = cards.map(function (c) {
        return '<div class="stat"><div class="top"><span class="lbl">' + c.lbl + '</span>' +
          '<span class="ico ' + c.cls + '">' + ic(c.icon, 15) + '</span></div>' +
          '<div class="val">' + fmtNum(c.val) + '</div>' +
          '<div class="foot">' + esc(c.foot) + '</div></div>';
      }).join('');

      // 弱令牌提醒：只提示、不阻断，自己人的部署可能是刻意用短口令图方便。
      // 「知道了」按当前令牌长度记忆，令牌一改长度就重新提示。
      var tc = d.token_check || {};
      LAST_TOKEN_CHECK = tc;
      var tw = $('tokenWarn');
      if (tw) {
        var dismissed = tc.length ? localStorage.getItem('ka_tokwarn_' + tc.length) : null;
        if (tc.weak && !dismissed) {
          $('tokenWarnTxt').textContent = '当前令牌' +
            (tc.reasons && tc.reasons.length ? '：' + tc.reasons.join('，') : '偏弱') +
            '。如果后台暴露在公网，建议重置。';
          tw.style.display = '';
        } else {
          tw.style.display = 'none';
        }
      }

      // 对数刻度：校验量一天能差两个数量级（0 / 428 / 22859），线性刻度会把
      // 小值压成看不见的一条线，对数刻度能让每天的相对变化都可读。
      var tmax = Math.max.apply(null, d.trend.map(function (x) { return x.value; }).concat([1]));
      var tden = Math.log10(tmax + 1) || 1;
      $('trendChart').innerHTML = d.trend.map(function (x) {
        var h = x.value === 0 ? 3
          : Math.max(6, Math.round(Math.log10(x.value + 1) / tden * 118));
        return '<div class="bar-col" title="' + esc(x.label) + '：' + x.value + ' 次">' +
          '<span class="v">' + x.value + '</span>' +
          '<div class="bar" style="height:' + h + 'px"></div>' +
          '<span class="l">' + esc(x.label) + '</span></div>';
      }).join('');

      if (!d.result_dist.length) {
        $('resultDist').innerHTML = '<div class="empty" style="padding:30px 10px"><p>暂无数据</p></div>';
      } else {
        // 按「占总量」算比例。原来按最大值算，通过 35703 一出现，其余个位数
        // 结果就全成了 0 长度条，看不出占比。
        var rtotal = d.result_total ||
          d.result_dist.reduce(function (a, x) { return a + x.value; }, 0) || 1;
        $('resultDist').innerHTML = d.result_dist.map(function (x) {
          var pct = x.value / rtotal * 100;
          var w = x.value === 0 ? 0 : Math.max(1.5, pct);
          var bad = x.result !== 'OK';
          var pctText = pct >= 10 ? (Math.round(pct * 10) / 10) + '%'
            : (pct > 0 ? pct.toFixed(2) + '%' : '0%');
          return '<div class="dist-row"><div class="line"><span>' + esc(x.text) + '</span>' +
            '<span>' + x.value + ' · ' + pctText + '</span></div>' +
            '<div class="progress"><i style="width:' + w + '%;' +
            (bad ? 'background:linear-gradient(90deg,#F59E0B,#EF4444)' : '') + '"></i></div></div>';
        }).join('');
      }

      $('recentBody').innerHTML = d.recent.length ? d.recent.map(function (r) {
        return '<tr><td class="dim num">' + esc(r.time) + '</td>' +
          '<td><span class="badge b-gray">' + esc(actionName(r.action)) + '</span></td>' +
          '<td>' + resultBadge(r.result, r.result_text) + '</td>' +
          '<td class="code">' + esc(r.code || '-') + '</td>' +
          '<td class="code dim">' + esc(short(r.machine_id)) + '</td>' +
          '<td class="dim num">' + esc(r.ip) + '</td></tr>';
      }).join('') : '<tr><td colspan="6"><div class="empty"><p>暂无记录</p></div></td></tr>';
    }).catch(function () {});
  }

  function dismissTokenWarn() {
    var n = LAST_TOKEN_CHECK && LAST_TOKEN_CHECK.length;
    if (n) { localStorage.setItem('ka_tokwarn_' + n, '1'); }
    var tw = $('tokenWarn');
    if (tw) { tw.style.display = 'none'; }
  }

  function actionName(a) {    return ({ verify: '验证', heartbeat: '心跳', query: '查询', unbind: '解绑', ban: '封禁' })[a] || a;
  }
  function resultBadge(r, text) {
    var t = text || RESULT_TEXT[r] || r;
    var cls = r === 'OK' ? 'b-success'
      : (r === 'REPLAY' || r === 'BAD_TS' || r === 'RATE_LIMIT' ? 'b-warn' : 'b-danger');
    return '<span class="badge ' + cls + '">' + esc(t) + '</span>';
  }

  /* ============================================================
     制卡
     ============================================================ */
  function loadGenOptions() {
    api('/api/admin/apps').then(function (a) {
      if (!a.ok) { return; }
      APP_CACHE = a.items;
      $('genApp').innerHTML = a.items.map(function (x) {
        return '<option value="' + esc(x.app_id) + '">' + esc(x.name) + '</option>';
      }).join('');
    });
    api('/api/admin/plans').then(function (p) {
      if (!p.ok) { return; }
      PLAN_CACHE = p.items;
      $('genPlan').innerHTML = '<option value="">自定义（用下方参数）</option>' +
        p.items.map(function (x) {
          var desc;
          if (x.card_type === 'time') {
            desc = x.duration_days === 0 ? '永久' : x.duration_days + ' 天';
          } else if (x.card_type === 'hour') {
            desc = x.duration_days + ' 小时';
          } else {
            desc = x.total_value + ' ' + (x.card_type === 'count' ? '次' : '点');
          }
          return '<option value="' + x.id + '">' + esc(x.name) + ' · ' + esc(desc) +
            ' · ' + x.max_devices + ' 设备</option>';
        }).join('');
    });
  }

  function onPlanChange() {
    var v = $('genPlan').value;
    var p = PLAN_CACHE.filter(function (x) { return String(x.id) === String(v); })[0];
    ['genType', 'genDays', 'genValue', 'genDev', 'genUnbind'].forEach(function (id) {
      $(id).disabled = !!p;
    });
    if (p) {
      $('genType').value = p.card_type;
      $('genDays').value = p.duration_days;
      $('genValue').value = p.total_value;
      $('genDev').value = p.max_devices;
      $('genUnbind').value = p.unbind_limit;
      if (p.app_id) { $('genApp').value = p.app_id; }
    }
    onTypeChange();
  }

  function onTypeChange() {
    var t = $('genType').value;
    $('genDays').disabled = !!$('genPlan').value;
    $('genValue').disabled = true;
    // 只剩天数卡/小时卡，额度字段永远用不上，直接整列隐藏，别留个灰框让人以为坏了
    if ($('genValueField')) { $('genValueField').style.display = 'none'; }
    $('genDaysLabel').textContent = t === 'hour' ? '有效小时数（0=永久）' : '有效天数（0=永久）';
    $('genValLabel').textContent = '初始额度（不适用）';
  }

  function doGen() {
    var body = {
      app_id: $('genApp').value,
      plan_id: $('genPlan').value || null,
      card_type: $('genType').value,
      duration_days: parseInt($('genDays').value || '0', 10),
      total_value: parseInt($('genValue').value || '0', 10),
      max_devices: parseInt($('genDev').value || '1', 10),
      unbind_limit: parseInt($('genUnbind').value || '1', 10),
      count: parseInt($('genCount').value || '1', 10),
      prefix: $('genPrefix').value.trim(),
      note: $('genNote').value.trim()
    };
    if (!body.count || body.count < 1) { toast('生成数量至少为 1', 'error'); return; }
    post('/api/admin/cards', body).then(function (d) {
      if (!d.ok) { toast(d.msg || '生成失败', 'error'); return; }
      lastCodes = d.codes;
      lastBatch = d.batch;
      $('genEmpty').classList.add('hidden');
      var out = $('genOut');
      out.classList.remove('hidden');
      out.textContent = d.codes.join('\n');
      $('genMeta').textContent = '批次 ' + d.batch + ' · ' + d.count + ' 张';
      toast('已生成 ' + d.count + ' 张卡密');
    }).catch(function () {});
  }

  function copyGen() {
    if (!lastCodes.length) { toast('还没有生成卡密', 'error'); return; }
    copyText(lastCodes.join('\n'), '已复制 ' + lastCodes.length + ' 张卡密');
  }
  function downloadGen() {
    if (!lastCodes.length) { toast('还没有生成卡密', 'error'); return; }
    download(lastCodes.join('\r\n'), 'cards_' + (lastBatch || Date.now()) + '.txt');
  }
  function download(text, filename) {
    var blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  /* ============================================================
     卡密库
     ============================================================ */
  function loadCards(page) {
    if (!$('cardApp').options.length) {
      api('/api/admin/apps').then(function (a) {
        if (!a.ok) { return; }
        $('cardApp').innerHTML = '<option value="">全部应用</option>' +
          a.items.map(function (x) {
            return '<option value="' + esc(x.app_id) + '">' + esc(x.name) + '</option>';
          }).join('');
        loadCards(page);
      }).catch(function () {});
      return;
    }
    cardPage = Math.max(1, page || 1);
    cardSel = {};
    $('checkAll').checked = false;
    hideBulk();

    var qs = '?page=' + cardPage + '&size=' + cardSize +
      '&q=' + encodeURIComponent($('cardQ').value.trim()) +
      '&status=' + encodeURIComponent($('cardStatus').value) +
      '&app=' + encodeURIComponent($('cardApp').value) +
      '&card_type=' + encodeURIComponent($('cardType').value);

    api('/api/admin/cards' + qs).then(function (d) {
      if (!d.ok) { return; }
      $('cardBody').innerHTML = d.items.length ? d.items.map(cardRow).join('') :
        '<tr><td colspan="11"><div class="empty">' + ic('key', 40) +
        '<p>没有符合条件的卡密</p><div class="sm">换个筛选条件，或先去「制卡」页生成一批</div></div></td></tr>';
      var pages = Math.max(1, Math.ceil(d.total / cardSize));
      $('pageInfo').textContent = '共 ' + d.total + ' 条 · 第 ' + cardPage + ' / ' + pages + ' 页';
      $('prevBtn').disabled = cardPage <= 1;
      $('nextBtn').disabled = cardPage >= pages;
      if ($('cardSize')) { $('cardSize').value = String(cardSize); }
      if ($('cardJump')) { $('cardJump').value = String(cardPage); }
      if ($('cardJump')) { $('cardJump').max = String(pages); }
    }).catch(function () {});
  }

  function changeCardSize() {
    cardSize = parseInt($('cardSize').value, 10) || 50;
    loadCards(1);
  }

  function jumpCardPage() {
    var n = parseInt($('cardJump').value, 10);
    if (isNaN(n) || n < 1) { $('cardJump').value = String(cardPage); return; }
    loadCards(n);
  }

  function statusBadge(it) {
    if (it.status === 'banned') { return '<span class="badge b-danger">已封禁</span>'; }
    if (it.status === 'unused') { return '<span class="badge b-info">未使用</span>'; }
    if (it.status === 'used_up') { return '<span class="badge b-warn">额度用尽</span>'; }
    if (it.expired) { return '<span class="badge b-warn">已过期</span>'; }
    return '<span class="badge b-success">使用中</span>';
  }

  function cardRow(it) {
    CARD_CACHE[it.code] = it;
    var limit = it.card_type === 'time' || it.card_type === 'hour'
      ? esc(it.expires_text)
      : (it.remaining_value + ' / ' + it.total_value);
    return '<tr class="row-click" data-code="' + esc(it.code) + '"' +
      ' onclick="KA.cardDetail(event,\'' + esc(it.code) + '\')">' +
      '<td><input type="checkbox" class="rowck" value="' + esc(it.code) + '" onchange="KA.toggleRow(this)" /></td>' +
      '<td class="code"><span class="copy-cell">' + esc(it.code) +
      '<button class="copy-btn" onclick="KA.copy(\'' + esc(it.code) + '\',\'卡密已复制\')">' +
      ic('copy', 11.5) + '</button></span></td>' +
      '<td>' + esc(it.app_name) + '</td>' +
      '<td>' + (it.plan ? esc(it.plan) : '<span class="dim">-</span>') + '</td>' +
      '<td><span class="badge b-gray plain">' + esc(it.card_type_text) + '</span></td>' +
      '<td>' + statusBadge(it) + '</td>' +
      '<td class="dim num">' + limit + '</td>' +
      '<td class="num">' + it.devices + ' / ' + it.max_devices + '</td>' +
      '<td class="num">' + it.unbind_left + '</td>' +
      '<td>' + (it.note ? esc(it.note) : '<span class="dim">-</span>') + '</td>' +
      '<td><button class="btn ghost icon sm" onclick="KA.cardMenu(event,\'' + esc(it.code) + '\')">' +
      '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.7"/>' +
      '<circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg></button></td></tr>';
  }

  function cardDetail(ev, code) {
    // 行内的复选框 / 复制按钮 / 省略号菜单自己处理点击，不要连带弹出详情
    if (ev && ev.target && ev.target.closest &&
        ev.target.closest('input,button,select,textarea,a')) { return; }
    var it = CARD_CACHE[code];
    if (!it) { return; }
    var limit = (it.card_type === 'time' || it.card_type === 'hour')
      ? it.expires_text
      : (it.remaining_value + ' / ' + it.total_value + ' 额度');
    var rows = [
      ['卡密', '<b class="mono">' + esc(it.code) + '</b>'],
      ['应用', esc(it.app_name)],
      ['套餐', it.plan ? esc(it.plan) : '-'],
      ['类型', esc(it.card_type_text)],
      ['状态', statusBadge(it)],
      ['到期 / 额度', esc(limit)],
      ['设备绑定', it.devices + ' / ' + it.max_devices],
      ['剩余换绑', String(it.unbind_left)],
      ['批次', it.batch ? esc(it.batch) : '-'],
      ['备注', it.note ? esc(it.note) : '-'],
      ['创建时间', esc(it.created_text || '-')],
      ['激活时间', esc(it.activated_text || '-')],
      ['最后校验', esc(it.last_used_text || '-')]
    ];
    modal({
      title: '卡密详情',
      okText: '复制卡密',
      body: '<dl class="kv">' + rows.map(function (r) {
        return '<dt>' + r[0] + '</dt><dd>' + r[1] + '</dd>';
      }).join('') + '</dl>',
      onOk: function () { copyText(code, '卡密已复制'); return false; }
    });
  }

  // 内联 onclick 只能看到 window 上的东西，cardPage 是闭包变量，
  // 直接写 loadCards(cardPage+1) 会抛 ReferenceError（按钮点了没反应）。
  function prevCardPage() { loadCards(cardPage - 1); }
  function nextCardPage() { loadCards(cardPage + 1); }

  function cardMenu(ev, code) {
    ev.stopPropagation();
    openMenu(ev.currentTarget, [
      { label: '封禁', icon: 'ban', onClick: function () { act([code], 'ban'); } },
      { label: '解封', icon: 'unlock', onClick: function () { act([code], 'unban'); } },
      { label: '解绑全部设备', icon: 'rotate', onClick: function () { act([code], 'unbind'); } },
      { label: '重置换绑次数', icon: 'refresh', onClick: function () { act([code], 'unbind_reset'); } },
      { sep: true },
      { label: '续期 / 加额度…', icon: 'clock', onClick: function () { renewOne(code); } },
      { label: '重置为未使用', icon: 'rotate', onClick: function () { act([code], 'reset'); } },
      { sep: true },
      { label: '删除卡密', icon: 'trash', danger: true, onClick: function () { delCards([code]); } }
    ]);
  }

  function act(codes, action, amount) {
    post('/api/admin/cards/action',
      { codes: codes, action: action, amount: amount || 0 }).then(function (d) {
        if (!d.ok) { toast(d.msg || '操作失败', 'error'); return; }
        toast('已处理 ' + d.affected + ' 张卡密');
        loadCards(cardPage);
      }).catch(function () {});
  }

  function renewOne(code) {
    modal({
      title: '续期 / 增加额度',
      body: '<p style="margin:0 0 12px;font-size:12.5px;color:var(--text-3)">' +
        '时间卡按「天」、小时卡按「小时」增加有效期；次数卡/点数卡按「额度」增加可用量。填负数则为减少。</p>' +
        '<label class="pf" style="font-size:12px;color:var(--text-2)">数量</label>' +
        '<input type="number" id="renewAmt" value="30" />',
      okText: '确认',
      onOk: function (m) {
        var n = parseInt(m.querySelector('#renewAmt').value, 10);
        if (isNaN(n)) { toast('请输入数字', 'error'); return false; }
        act([code], 'renew', n);
      }
    });
  }

  function delCards(codes) {
    modal({
      title: '删除卡密', danger: true, okText: '确认删除',
      body: '<p style="margin:0">确定删除 <b>' + codes.length + '</b> 张卡密吗？</p>' +
        '<p style="margin:8px 0 0;font-size:12.5px;color:var(--text-3)">删除不可恢复，对应的设备绑定也会一并清除。</p>',
      onOk: function () { act(codes, 'delete'); }
    });
  }

  function toggleRow(ck) {
    if (ck.checked) { cardSel[ck.value] = 1; } else { delete cardSel[ck.value]; }
    var boxes = document.querySelectorAll('.rowck');
    var on = document.querySelectorAll('.rowck:checked').length;
    $('checkAll').checked = boxes.length > 0 && on === boxes.length;
    renderBulk();
  }
  function toggleAll(ck) {
    document.querySelectorAll('.rowck').forEach(function (b) {
      b.checked = ck.checked;
      if (ck.checked) { cardSel[b.value] = 1; } else { delete cardSel[b.value]; }
    });
    renderBulk();
  }
  function renderBulk() {
    var n = Object.keys(cardSel).length;
    hideBulk();
    if (!n) { return; }
    var el = document.createElement('div');
    el.className = 'bulk';
    el.id = 'bulkBar';
    el.innerHTML = '<span class="n">已选 ' + n + ' 张</span><span class="sep"></span>' +
      '<button class="btn sm" onclick="KA.bulk(\'ban\')">封禁</button>' +
      '<button class="btn sm" onclick="KA.bulk(\'unban\')">解封</button>' +
      '<button class="btn sm" onclick="KA.bulk(\'unbind\')">解绑</button>' +
      '<button class="btn sm" onclick="KA.bulk(\'unbind_reset\')">重置换绑</button>' +
      '<button class="btn sm" onclick="KA.bulkRenew()">续期</button>' +
      '<span class="sep"></span>' +
      '<button class="btn sm danger" onclick="KA.bulkDel()">删除</button>' +
      '<button class="btn ghost icon sm" onclick="KA.clearSel()">' + ic('x', 13) + '</button>';
    document.body.appendChild(el);
  }
  function hideBulk() {
    var b = $('bulkBar');
    if (b && b.parentNode) { b.parentNode.removeChild(b); }
  }
  function clearSel() {
    cardSel = {};
    document.querySelectorAll('.rowck').forEach(function (b) { b.checked = false; });
    $('checkAll').checked = false;
    hideBulk();
  }
  function bulk(action) { act(Object.keys(cardSel), action); }
  function bulkRenew() {
    var n = Object.keys(cardSel).length;
    modal({
      title: '批量续期 / 加额度',
      body: '<p style="margin:0 0 12px;font-size:12.5px;color:var(--text-3)">对选中的 ' + n + ' 张卡密操作。</p>' +
        '<label style="font-size:12px;color:var(--text-2)">数量</label>' +
        '<input type="number" id="renewAmt" value="30" />',
      okText: '确认',
      onOk: function (m) {
        var v = parseInt(m.querySelector('#renewAmt').value, 10);
        if (isNaN(v)) { toast('请输入数字', 'error'); return false; }
        act(Object.keys(cardSel), 'renew', v);
      }
    });
  }
  function bulkDel() {
    var codes = Object.keys(cardSel);
    modal({
      title: '批量删除', danger: true, okText: '确认删除',
      body: '<p style="margin:0">确定删除 <b>' + codes.length + '</b> 张卡密吗？删除不可恢复。</p>',
      onOk: function () { act(codes, 'delete'); }
    });
  }

  function exportCards() {
    var qs = '?status=' + encodeURIComponent($('cardStatus').value) +
      '&app=' + encodeURIComponent($('cardApp').value) +
      '&card_type=' + encodeURIComponent($('cardType').value);
    fetch('/api/admin/cards/export' + qs, { headers: { 'X-Admin-Token': TOKEN } })
      .then(function (r) { return r.text(); })
      .then(function (t) {
        if (!t.trim()) { toast('没有可导出的卡密', 'error'); return; }
        var blob = new Blob(['\ufeff' + t], { type: 'text/csv;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'cards_' + Date.now() + '.csv';
        a.click();
        toast('已导出');
      });
  }

  /* ============================================================
     应用
     ============================================================ */
  function loadApps() {
    api('/api/admin/apps').then(function (d) {
      if (!d.ok) { return; }
      APP_CACHE = d.items;
      if (!d.items.length) {
        $('appGrid').innerHTML = '<div class="card"><div class="empty">' + ic('box', 40) +
          '<p>还没有应用</p><div class="sm">点右上角「新建应用」开始</div></div></div>';
        return;
      }
      $('appGrid').innerHTML = d.items.map(function (x) {
        var off = x.status !== 'active';
        return '<div class="app-card"><div class="h">' +
          '<span class="ico i-primary">' + ic('box', 15) + '</span>' +
          '<b>' + esc(x.name) + '</b>' +
          '<span class="badge ' + (off ? 'b-danger' : 'b-gray') + '">' +
          (off ? '已禁用' : x.cards + ' 张卡') + '</span></div>' +
          '<div class="row"><span class="k">AppID</span><span class="v">' + esc(x.app_id) + '</span>' +
          '<button class="copy-btn always" onclick="KA.copy(\'' + esc(x.app_id) + '\',\'AppID 已复制\')">' + ic('copy', 11.5) + '</button></div>' +
          '<div class="row"><span class="k">AppSecret</span>' +
          '<span class="v" id="sec-' + x.id + '">••••••••••••••••••</span>' +
          '<button class="copy-btn always" onclick="KA.reveal(' + x.id + ',\'' + esc(x.app_secret) + '\')">' + ic('eye', 11.5) + '</button>' +
          '<button class="copy-btn always" onclick="KA.copy(\'' + esc(x.app_secret) + '\',\'AppSecret 已复制\')">' + ic('copy', 11.5) + '</button></div>' +
          '<div class="row"><span class="k">心跳间隔</span><span class="v" style="font-family:inherit">' + x.heartbeat_interval + ' 秒</span></div>' +
          '<div class="row"><span class="k">签名</span><span class="v" style="font-family:inherit">' +
          (x.require_sign ? '强制校验' : '不强制') + '</span></div>' +
          '<div class="foot">' +
          '<button class="btn sm" onclick="KA.editApp(' + x.id + ')">' + ic('edit', 12.5) + '编辑</button>' +
          '<button class="btn sm" onclick="KA.resetSecret(' + x.id + ')">' + ic('refresh', 12.5) + '重置密钥</button>' +
          '<button class="btn sm danger" onclick="KA.delApp(' + x.id + ',\'' + esc(x.name) + '\')" title="删除应用">' + ic('trash', 12.5) + ' 删除</button>' +
          '</div></div>';
      }).join('');
    }).catch(function () {});
  }

  function reveal(id, secret) {
    var el = $('sec-' + id);
    el.textContent = el.textContent.indexOf('•') === 0 ? secret : '••••••••••••••••••';
  }

  function appForm(app, onSave) {
    api('/api/admin/apps').then(function () {});
    var isNew = !app;
    modal({
      title: isNew ? '新建应用' : '编辑应用',
      okText: isNew ? '创建' : '保存',
      body:
        '<div class="grid g2" style="margin-bottom:12px">' +
        '<div class="field"><label>应用名称</label><input type="text" id="apName" value="' +
        esc(app ? app.name : '') + '" placeholder="如 我的桌面助手" /></div>' +
        '<div class="field"><label>状态</label><select id="apStatus">' +
        '<option value="active"' + (app && app.status === 'active' ? ' selected' : '') + '>启用</option>' +
        '<option value="disabled"' + (app && app.status === 'disabled' ? ' selected' : '') + '>禁用</option>' +
        '</select></div></div>' +
        '<div class="grid g2" style="margin-bottom:12px">' +
        '<div class="field"><label>心跳间隔（秒）</label><input type="number" id="apHb" min="30" value="' +
        (app ? app.heartbeat_interval : 180) + '" /></div>' +
        '<div class="field"><label>WebHook 地址（可选）</label><input type="url" id="apHook" value="' +
        esc(app ? app.webhook_url : '') + '" placeholder="https://..." /></div></div>' +
        '<div class="field" style="margin-bottom:12px"><label>备注</label><input type="text" id="apNote" value="' +
        esc(app ? app.note : '') + '" /></div>' +
        '<label class="switch"><input type="checkbox" id="apSign"' +
        (!app || app.require_sign ? ' checked' : '') + ' /><span class="track"></span>' +
        '<span>强制签名校验</span></label>',
      onMount: function (m) {
        var f = m.querySelector('#apName');
        if (isNew) { setTimeout(function () { f.focus(); }, 40); }
      },
      onOk: function (m) {
        var body = {
          action: isNew ? 'create' : 'update',
          id: app ? app.id : undefined,
          name: m.querySelector('#apName').value.trim(),
          status: m.querySelector('#apStatus').value,
          heartbeat_interval: m.querySelector('#apHb').value,
          webhook_url: m.querySelector('#apHook').value.trim(),
          note: m.querySelector('#apNote').value.trim(),
          require_sign: m.querySelector('#apSign').checked
        };
        if (!body.name) { toast('请填写应用名称', 'error'); return false; }
        post('/api/admin/apps', body).then(function (d) {
          if (!d.ok) { toast(d.msg || '保存失败', 'error'); return; }
          toast(isNew ? '应用已创建' : '已保存');
          onSave();
        }).catch(function () {});
      }
    });
  }
  function newApp() { appForm(null, loadApps); }
  function editApp(id) {
    var a = APP_CACHE.filter(function (x) { return x.id === id; })[0];
    if (a) { appForm(a, loadApps); }
  }

  function resetSecret(id) {
    modal({
      title: '重置应用密钥', danger: true, okText: '确认重置',
      body: '<p style="margin:0">重置后<b>旧密钥立即失效</b>，已经发布出去的客户端会全部校验失败，' +
        '需要更新客户端里的 AppSecret 并重新分发。</p>' +
        '<p style="margin:8px 0 0;font-size:12.5px;color:var(--text-3)">仅在该密钥疑似泄露时使用。</p>',
      onOk: function () {
        post('/api/admin/apps', { action: 'reset_secret', id: id }).then(function (d) {
          if (!d.ok) { toast(d.msg || '重置失败', 'error'); return; }
          copyText(d.app_secret, '新密钥已生成并复制');
          loadApps();
        }).catch(function () {});
      }
    });
  }

  function delApp(id, name) {
    modal({
      title: '删除应用', danger: true, okText: '确认删除',
      body: '<p style="margin:0">确定删除应用「' + esc(name) + '」吗？</p>' +
        '<p style="margin:8px 0 0;font-size:12.5px;color:var(--text-3)">若该应用下还有卡密，会再确认一次并一并删除。</p>',
      onOk: function () {
        post('/api/admin/apps', { action: 'delete', id: id }).then(function (d) {
          if (d.err === 'HAS_CARDS') {
            closeModal();
            modal({
              title: '该应用下仍有卡密', danger: true, okText: '一并删除',
              body: '<p style="margin:0">' + esc(d.msg) + '</p>',
              onOk: function () {
                post('/api/admin/apps', { action: 'delete', id: id, force: true })
                  .then(function (r) {
                    if (!r.ok) { toast(r.msg || '删除失败', 'error'); return; }
                    toast('应用及其卡密已删除');
                    loadApps();
                  });
              }
            });
            return false;
          }
          if (!d.ok) { toast(d.msg || '删除失败', 'error'); return; }
          toast('已删除');
          loadApps();
        }).catch(function () {});
      }
    });
  }

  /* ============================================================
     套餐
     ============================================================ */
  function loadPlans() {
    api('/api/admin/plans').then(function (d) {
      if (!d.ok) { return; }
      PLAN_CACHE = d.items;
      $('planBody').innerHTML = d.items.length ? d.items.map(function (p) {
        var amt;
        if (p.card_type === 'time') {
          amt = p.duration_days === 0 ? '永久' : p.duration_days + ' 天';
        } else if (p.card_type === 'hour') {
          amt = p.duration_days + ' 小时';
        } else {
          amt = p.total_value + ' ' + (p.card_type === 'count' ? '次' : '点');
        }
        return '<tr><td><b>' + esc(p.name) + '</b></td>' +
          '<td>' + esc(p.app_name) + '</td>' +
          '<td><span class="badge b-gray plain">' + esc(p.card_type_text) + '</span></td>' +
          '<td class="num">' + amt + '</td>' +
          '<td class="num">' + p.max_devices + '</td>' +
          '<td class="num">' + p.unbind_limit + '</td>' +
          '<td class="num">' + (p.price ? '¥' + p.price : '<span class="dim">未定价</span>') + '</td>' +
          '<td class="num">' + p.cards + '</td>' +
          '<td><button class="btn ghost sm" onclick="KA.editPlan(' + p.id + ')">编辑</button> ' +
          '<button class="btn ghost sm danger" onclick="KA.delPlan(' + p.id + ',\'' + esc(p.name) + '\')">删除</button></td></tr>';
      }).join('') : '<tr><td colspan="9"><div class="empty">' + ic('tag', 40) +
        '<p>还没有套餐</p><div class="sm">套餐能让制卡更快，也便于统一管理不同规格</div></div></td></tr>';
    }).catch(function () {});
  }

  function editPlan(id) {
    var p = id ? PLAN_CACHE.filter(function (x) { return x.id === id; })[0] : null;
    api('/api/admin/apps').then(function (a) {
      var opts = '<option value="">通用（不限定应用）</option>' + (a.items || []).map(function (x) {
        return '<option value="' + esc(x.app_id) + '"' +
          (p && p.app_id === x.app_id ? ' selected' : '') + '>' + esc(x.name) + '</option>';
      }).join('');
      modal({
        title: p ? '编辑套餐' : '新建套餐',
        okText: '保存',
        body:
          '<div class="grid g2" style="margin-bottom:12px">' +
          '<div class="field"><label>套餐名</label><input type="text" id="plName" value="' +
          esc(p ? p.name : '') + '" placeholder="如 月卡" /></div>' +
          '<div class="field"><label>归属应用</label><select id="plApp">' + opts + '</select></div></div>' +
          '<div class="grid g3" style="margin-bottom:12px">' +
          '<div class="field"><label>卡密类型</label><select id="plType" onchange="KA.planType()">' +
          ['time', 'hour', 'count', 'point'].map(function (t) {
            var label = { time: '时间卡', hour: '小时卡', count: '次数卡', point: '点数卡' }[t];
            return '<option value="' + t + '"' + (p && p.card_type === t ? ' selected' : '') + '>' + label + '</option>';
          }).join('') + '</select></div>' +
          '<div class="field"><label id="plDaysL">有效天数</label><input type="number" id="plDays" min="0" value="' +
          (p ? p.duration_days : 30) + '" /></div>' +
          '<div class="field"><label id="plValL">初始额度</label><input type="number" id="plVal" min="0" value="' +
          (p ? p.total_value : 0) + '" /></div></div>' +
          '<div class="grid g3" style="margin-bottom:12px">' +
          '<div class="field"><label>设备数</label><input type="number" id="plDev" min="1" value="' +
          (p ? p.max_devices : 1) + '" /></div>' +
          '<div class="field"><label>换绑次数</label><input type="number" id="plUnb" min="0" value="' +
          (p ? p.unbind_limit : 1) + '" /></div>' +
          '<div class="field"><label>价格（仅展示）</label><input type="number" id="plPrice" min="0" step="0.01" value="' +
          (p ? p.price : 0) + '" /></div></div>' +
          '<div class="field"><label>备注</label><input type="text" id="plNote" value="' +
          esc(p ? p.note : '') + '" /></div>',
        onMount: function () { planType(); },
        onOk: function (m) {
          var body = {
            action: p ? 'update' : 'create',
            id: p ? p.id : undefined,
            name: m.querySelector('#plName').value.trim(),
            app_id: m.querySelector('#plApp').value,
            card_type: m.querySelector('#plType').value,
            duration_days: m.querySelector('#plDays').value,
            total_value: m.querySelector('#plVal').value,
            max_devices: m.querySelector('#plDev').value,
            unbind_limit: m.querySelector('#plUnb').value,
            price: m.querySelector('#plPrice').value,
            note: m.querySelector('#plNote').value.trim()
          };
          if (!body.name) { toast('请填写套餐名', 'error'); return false; }
          post('/api/admin/plans', body).then(function (r) {
            if (!r.ok) { toast(r.msg || '保存失败', 'error'); return; }
            toast('已保存');
            loadPlans();
          }).catch(function () {});
        }
      });
    }).catch(function () {});
  }

  function planType() {
    var t = $('plType') ? $('plType').value : 'time';
    if (!$('plDays')) { return; }
    var isTime = t === 'time' || t === 'hour';
    $('plDays').disabled = !isTime;
    $('plVal').disabled = isTime;
    $('plDaysL').textContent = t === 'time' ? '有效天数（0=永久）'
      : (t === 'hour' ? '有效小时数' : '有效天数（不适用）');
    $('plValL').textContent = t === 'count' ? '初始次数' : (t === 'point' ? '初始点数' : '初始额度');
  }

  function delPlan(id, name) {
    modal({
      title: '删除套餐', danger: true, okText: '确认删除',
      body: '<p style="margin:0">确定删除套餐「' + esc(name) + '」吗？</p>' +
        '<p style="margin:8px 0 0;font-size:12.5px;color:var(--text-3)">已生成的卡密不受影响，只是不再出现在制卡预设里。</p>',
      onOk: function () {
        post('/api/admin/plans', { action: 'delete', id: id }).then(function (d) {
          if (!d.ok) { toast(d.msg || '删除失败', 'error'); return; }
          toast('已删除');
          loadPlans();
        }).catch(function () {});
      }
    });
  }

  /* ============================================================
     日志 / 审计
     ============================================================ */
  var logPage = 1, logSize = 50;
  var auditPage = 1, auditSize = 50;

  function logPrevPage() { loadLogs(logPage - 1); }
  function logNextPage() { loadLogs(logPage + 1); }
  function auditPrevPage() { loadAudits(auditPage - 1); }
  function auditNextPage() { loadAudits(auditPage + 1); }

  function loadLogs(page) {
    var p = parseInt(page, 10);
    logPage = (isNaN(p) || p < 1) ? 1 : p;
    logSize = parseInt($('logSize').value, 10) || 50;

    // 结果码下拉的选项来自后端，只在第一次拉到后填充
    if ($('logResult').options.length <= 1) {
      api('/api/admin/logs?page=1&size=1').then(function (base) {
        if (!base.ok) { return; }
        RESULT_TEXT = base.result_text || {};
        var cur = $('logResult').value;
        $('logResult').innerHTML = '<option value="">全部结果</option>' +
          Object.keys(RESULT_TEXT).map(function (r) {
            return '<option value="' + r + '"' + (r === cur ? ' selected' : '') + '>' +
              esc(RESULT_TEXT[r]) + '</option>';
          }).join('');
        $('logResult').value = cur;
      }).catch(function () {});
    }

    var qs = '?page=' + logPage + '&size=' + logSize +
      '&q=' + encodeURIComponent($('logQ').value.trim()) +
      '&result=' + encodeURIComponent($('logResult').value) +
      '&action=' + encodeURIComponent($('logAction').value) +
      '&from=' + encodeURIComponent($('logFrom').value) +
      '&to=' + encodeURIComponent($('logTo').value);
    api('/api/admin/logs' + qs).then(function (d) {
      if (!d.ok) { return; }
      $('logBody').innerHTML = d.items.length ? d.items.map(function (r) {
        return '<tr><td class="dim num">' + esc(r.time) + '</td>' +
          '<td><span class="badge b-gray">' + esc(actionName(r.action)) + '</span></td>' +
          '<td>' + resultBadge(r.result, r.result_text) + '</td>' +
          '<td class="code">' + esc(r.code || '-') + '</td>' +
          '<td class="code dim">' + esc(short(r.machine_id)) + '</td>' +
          '<td class="dim num">' + esc(r.ip) + '</td>' +
          '<td class="dim">' + esc(r.detail || '-') + '</td></tr>';
      }).join('') : '<tr><td colspan="7"><div class="empty">' + ic('list', 40) +
        '<p>这个时间段没有日志</p><div class="sm">放宽日期范围或清空筛选条件</div></div></td></tr>';
      var pages = Math.max(1, Math.ceil((d.total || 0) / logSize));
      logPage = d.page || logPage;
      $('logInfo').textContent = '共 ' + (d.total || 0) + ' 条 · 第 ' + logPage + ' / ' + pages + ' 页';
      $('logPrev').disabled = logPage <= 1;
      $('logNext').disabled = logPage >= pages;
    }).catch(function () {});
  }

  function loadAudits(page) {
    var p = parseInt(page, 10);
    auditPage = (isNaN(p) || p < 1) ? 1 : p;
    var qs = '?page=' + auditPage + '&size=' + auditSize +
      '&q=' + encodeURIComponent($('auditQ').value.trim()) +
      '&action=' + encodeURIComponent($('auditAction').value);
    api('/api/admin/audits' + qs).then(function (d) {
      if (!d.ok) { return; }
      $('auditBody').innerHTML = d.items.length ? d.items.map(function (r) {
        return '<tr><td class="dim num">' + esc(r.time) + '</td>' +
          '<td><span class="badge b-primary">' + esc(r.action) + '</span></td>' +
          '<td class="code">' + esc(short(r.target, 22)) + '</td>' +
          '<td class="dim">' + esc(r.detail || '-') + '</td>' +
          '<td class="dim num">' + esc(r.ip || '-') + '</td></tr>';
      }).join('') : '<tr><td colspan="5"><div class="empty">' + ic('shield', 40) +
        '<p>暂无操作记录</p></div></td></tr>';
      var pages = Math.max(1, Math.ceil((d.total || 0) / auditSize));
      auditPage = d.page || auditPage;
      $('auditInfo').textContent = '共 ' + (d.total || 0) + ' 条 · 第 ' + auditPage + ' / ' + pages + ' 页';
      $('auditPrev').disabled = auditPage <= 1;
      $('auditNext').disabled = auditPage >= pages;
    }).catch(function () {});
  }

  /* ============================================================
     WebHook
     ============================================================ */
  var HOOK_EVENTS = [
    { v: 'card.activated', t: '卡密激活' },
    { v: 'device.bound', t: '绑定设备' },
    { v: 'device.unbound', t: '解绑设备' },
    { v: 'card.banned', t: '卡密封禁' }
  ];

  function loadWebhooks() {
    api('/api/admin/webhooks').then(function (d) {
      if (!d.ok) { return; }
      $('hookBody').innerHTML = d.items.length ? d.items.map(function (h) {
        var evs = String(h.events).split(',').map(function (e) {
          var f = HOOK_EVENTS.filter(function (x) { return x.v === e.trim(); })[0];
          return '<span class="badge b-info plain">' + (f ? f.t : e) + '</span>';
        }).join(' ');
        return '<tr><td>' + esc(h.app_name) + '</td>' +
          '<td class="code">' + esc(short(h.url, 40)) + '</td>' +
          '<td>' + evs + '</td>' +
          '<td class="code dim">' + esc(short(h.secret, 18)) + '</td>' +
          '<td>' + (h.enabled ? '<span class="badge b-success">启用</span>'
            : '<span class="badge b-gray">停用</span>') + '</td>' +
          '<td><button class="btn ghost sm" onclick="KA.toggleHook(' + h.id + ',' +
          (h.enabled ? 'false' : 'true') + ')">' + (h.enabled ? '停用' : '启用') + '</button> ' +
          '<button class="btn ghost sm danger" onclick="KA.delHook(' + h.id + ')">删除</button></td></tr>';
      }).join('') : '<tr><td colspan="6"><div class="empty">' + ic('zap', 40) +
        '<p>还没有配置回调</p><div class="sm">卡密激活时推送到你的服务器，便于自动发货或通知</div></div></td></tr>';
    }).catch(function () {});
  }

  function newWebhook() {
    modal({
      title: '新建 WebHook', okText: '创建',
      body:
        '<div class="field" style="margin-bottom:12px"><label>归属应用</label>' +
        '<select id="hkApp"><option value="">全部应用</option>' +
        APP_CACHE.map(function (x) {
          return '<option value="' + esc(x.app_id) + '">' + esc(x.name) + '</option>';
        }).join('') + '</select></div>' +
        '<div class="field" style="margin-bottom:12px"><label>回调地址</label>' +
        '<input type="url" id="hkUrl" placeholder="https://your-server.com/hook" /></div>' +
        '<div class="field" style="margin-bottom:12px"><label>订阅事件</label>' +
        HOOK_EVENTS.map(function (e, i) {
          return '<label class="check" style="margin:4px 0"><input type="checkbox" class="hkEv" value="' +
            e.v + '"' + (i === 0 ? ' checked' : '') + ' /> ' + e.t + '</label>';
        }).join('') + '</div>' +
        '<div class="field"><label>签名密钥（留空自动生成）</label>' +
        '<input type="text" id="hkSecret" placeholder="用于校验来源，放在 X-KeyAuth-Signature 头" /></div>',
      onOk: function (m) {
        var evs = Array.prototype.slice.call(m.querySelectorAll('.hkEv:checked'))
          .map(function (x) { return x.value; });
        if (!evs.length) { toast('至少选一个事件', 'error'); return false; }
        post('/api/admin/webhooks', {
          action: 'create', app_id: m.querySelector('#hkApp').value,
          url: m.querySelector('#hkUrl').value.trim(), events: evs,
          secret: m.querySelector('#hkSecret').value.trim()
        }).then(function (d) {
          if (!d.ok) { toast(d.msg || '创建失败', 'error'); return; }
          toast('已创建');
          loadWebhooks();
        }).catch(function () {});
      }
    });
  }

  function toggleHook(id, enabled) {
    post('/api/admin/webhooks', { action: 'toggle', id: id, enabled: enabled })
      .then(function () { loadWebhooks(); });
  }
  function delHook(id) {
    modal({
      title: '删除回调', danger: true, okText: '确认删除',
      body: '<p style="margin:0">确定删除这条回调配置吗？</p>',
      onOk: function () {
        post('/api/admin/webhooks', { action: 'delete', id: id })
          .then(function () { toast('已删除'); loadWebhooks(); });
      }
    });
  }

  /* ============================================================
     公告
     ============================================================ */
  function loadNotices() {
    api('/api/admin/notices').then(function (d) {
      if (!d.ok) { return; }
      $('noticeBox').innerHTML = d.items.length ? d.items.map(function (n) {
        return '<div class="notice ' + esc(n.level) + '">' +
          '<b>' + esc(n.title) + ' <span class="badge b-gray" style="margin-left:6px">' +
          (n.enabled ? '下发中' : '已停用') + '</span></b>' +
          '<div style="color:var(--text-2);white-space:pre-wrap">' + esc(n.content || '') + '</div>' +
          '<div style="margin-top:8px;display:flex;gap:8px;align-items:center">' +
          '<span style="font-size:11.5px;color:var(--text-3)">' + esc(n.created_text) + '</span>' +
          '<button class="btn ghost sm" onclick="KA.editNotice(' + n.id + ')">编辑</button>' +
          '<button class="btn ghost sm danger" onclick="KA.delNotice(' + n.id + ')">删除</button>' +
          '</div></div>';
      }).join('') : '<div class="empty">' + ic('bell', 40) + '<p>还没有公告</p>' +
        '<div class="sm">公告会随客户端校验响应下发</div></div>';
    }).catch(function () {});
  }

  function noticeForm(n) {
    modal({
      title: n ? '编辑公告' : '发布公告', okText: '保存',
      body:
        '<div class="field" style="margin-bottom:12px"><label>标题</label>' +
        '<input type="text" id="ntTitle" value="' + esc(n ? n.title : '') + '" /></div>' +
        '<div class="field" style="margin-bottom:12px"><label>内容</label>' +
        '<textarea id="ntContent" rows="4">' + esc(n ? n.content : '') + '</textarea></div>' +
        '<div class="grid g2">' +
        '<div class="field"><label>级别</label><select id="ntLevel">' +
        ['info', 'warn', 'danger'].map(function (l) {
          var t = { info: '普通', warn: '提醒', danger: '紧急' }[l];
          return '<option value="' + l + '"' + (n && n.level === l ? ' selected' : '') + '>' + t + '</option>';
        }).join('') + '</select></div>' +
        '<div class="field"><label>状态</label><select id="ntEnabled">' +
        '<option value="1"' + (!n || n.enabled ? ' selected' : '') + '>下发</option>' +
        '<option value="0"' + (n && !n.enabled ? ' selected' : '') + '>停用</option>' +
        '</select></div></div>',
      onOk: function (m) {
        post('/api/admin/notices', {
          action: n ? 'update' : 'create', id: n ? n.id : undefined,
          title: m.querySelector('#ntTitle').value.trim(),
          content: m.querySelector('#ntContent').value,
          level: m.querySelector('#ntLevel').value,
          enabled: m.querySelector('#ntEnabled').value === '1'
        }).then(function (d) {
          if (!d.ok) { toast(d.msg || '保存失败', 'error'); return; }
          toast('已保存');
          loadNotices();
        }).catch(function () {});
      }
    });
  }
  function newNotice() { noticeForm(null); }
  function editNotice(id) {
    api('/api/admin/notices').then(function (d) {
      var n = d.items.filter(function (x) { return x.id === id; })[0];
      if (n) { noticeForm(n); }
    }).catch(function () {});
  }
  function delNotice(id) {
    modal({
      title: '删除公告', danger: true, okText: '确认删除',
      body: '<p style="margin:0">确定删除这条公告吗？</p>',
      onOk: function () {
        post('/api/admin/notices', { action: 'delete', id: id })
          .then(function () { toast('已删除'); loadNotices(); });
      }
    });
  }

  /* ============================================================
     设置
     ============================================================ */
  var PUBLIC_BASE = '';

  function loadSettings() {
    api('/api/admin/settings').then(function (d) {
      if (!d.ok) { return; }
      var s = d.settings;
      $('stName').value = s.site_name;
      $('stDesc').value = s.site_desc;
      $('stAnnounce').value = s.announcement;
      $('stMinVer').value = s.min_client_version;
      $('stBase').value = s.public_base_url || '';
      $('stLogDays').value = s.log_retention_days;
      loadBackups();
      loadAdmins();
      $('stSkew').value = s.clock_skew;
      $('stNonce').value = s.nonce_ttl;
      $('stRate').value = s.rate_limit;
      $('stSign').checked = s.require_sign;
      $('stMaint').checked = s.maintenance;
      $('brandName').textContent = s.site_name || 'KeyAuth';
      $('brandDesc').textContent = s.site_desc || '卡密授权验证系统';
      PUBLIC_BASE = s.public_base_url || '';
      var tc = s.token_check || {};
      LAST_TOKEN_CHECK = tc;
      var st = $('tokStrength');
      if (st) {
        st.textContent = tc.weak
          ? '当前令牌强度：偏弱 — ' + (tc.reasons || []).join('，') + '。公网部署建议重置。'
          : '当前令牌强度：正常（' + (tc.length || 0) + ' 位）';
        st.style.color = tc.weak ? 'var(--warn)' : 'var(--text-3)';
      }
    }).catch(function () {});
  }

  function saveSettings() {
    post('/api/admin/settings', {
      site_name: $('stName').value.trim(),
      site_desc: $('stDesc').value.trim(),
      announcement: $('stAnnounce').value,
      min_client_version: $('stMinVer').value.trim(),
      public_base_url: $('stBase').value.trim(),
      log_retention_days: $('stLogDays').value,
      clock_skew: $('stSkew').value,
      nonce_ttl: $('stNonce').value,
      rate_limit: $('stRate').value,
      require_sign: $('stSign').checked,
      maintenance: $('stMaint').checked
    }).then(function (d) {
      if (!d.ok) { toast('保存失败', 'error'); return; }
      toast('设置已保存');
      $('brandName').textContent = d.settings.site_name || 'KeyAuth';
      $('brandDesc').textContent = d.settings.site_desc || '卡密授权验证系统';
      PUBLIC_BASE = d.settings.public_base_url || '';
      fillDocs();
    }).catch(function () {});
  }

  function doBackup() {
    post('/api/admin/backup', {}).then(function (d) {
      if (!d.ok) { toast(d.msg || '备份失败', 'error'); return; }
      toast('已备份：' + d.path);
      loadBackups();
    }).catch(function () {});
  }

  function loadBackups() {
    api('/api/admin/backups').then(function (d) {
      if (!d.ok) { return; }
      $('logStat').value = d.logs_total + ' 条';
      $('dbStat').value = d.db_size_text;
      $('backupBody').innerHTML = d.items.length ? d.items.map(function (b) {
        return '<tr><td class="code">' + esc(b.name) + '</td>' +
          '<td class="num dim">' + esc(b.size_text) + '</td>' +
          '<td class="dim num">' + esc(b.time_text) + '</td>' +
          '<td><button class="btn ghost sm" onclick="downloadBackup(\'' +
          esc(b.name) + '\')">下载</button></td></tr>';
      }).join('') : '<tr><td colspan="4"><div class="empty"><p>还没有备份</p>' +
        '<div class="sm">点上面「立即备份数据库」生成一份</div></div></td></tr>';
    }).catch(function () {});
  }

  // 备份接口要带管理令牌，没法直接给 <a href>，取成 blob 再触发下载
  function downloadBackup(name) {
    fetch('/api/admin/backups/' + encodeURIComponent(name), {
      headers: { 'X-Admin-Token': TOKEN }
    }).then(function (r) {
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.blob();
    }).then(function (blob) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
    }).catch(function (e) { toast('下载失败：' + e.message, 'error'); });
  }

  function cleanupLogs() {
    var days = parseInt($('stLogDays').value, 10);
    if (isNaN(days) || days < 0) { days = 0; }
    modal({
      title: '清理过期日志', okText: '开始清理',
      body: '<p style="margin:0">删除早于 <b>' + days + '</b> 天的校验日志。' +
        (days <= 0
          ? '<br><span style="color:var(--warn)">当前保留天数设为 0（永久），不会删除任何东西。</span>'
          : '') + '</p>' +
        '<p style="margin:8px 0 0;font-size:12.5px;color:var(--text-3)">' +
        '卡密、设备绑定、操作审计都不受影响。</p>',
      onOk: function () {
        post('/api/admin/logs/cleanup', { days: days }).then(function (d) {
          if (!d.ok) { toast(d.msg || '清理失败', 'error'); return; }
          toast(d.deleted ? '已删除 ' + d.deleted + ' 条日志'
                          : (d.msg || '没有需要清理的日志'));
          loadBackups();
        }).catch(function () {});
      }
    });
  }

  function rotateToken() {
    modal({
      title: '重置管理令牌', danger: true, okText: '确认重置',
      body: '<p style="margin:0">重置后当前页面会立即失去访问权限，需要用新令牌重新登录。</p>' +
        '<p style="margin:8px 0 0;font-size:12.5px;color:var(--text-3)">新令牌会直接复制到剪贴板，请妥善保存。</p>',
      onOk: function () {
        post('/api/admin/token/rotate', {}).then(function (d) {
          if (!d.ok) { toast('重置失败', 'error'); return; }
          TOKEN = d.admin_token;
          localStorage.setItem('ka_token', TOKEN);
          copyText(d.admin_token, '新管理令牌已复制');
          toast('令牌已重置', 'warn');
          // 刷新强度显示：改成长令牌后提示条应该自己消失
          loadSettings();
        }).catch(function () {});
      }
    });
  }

  /* ============================================================
     接入文档
     ============================================================ */
  var RESP_ROWS = [
    ['OK', '校验通过', '放行功能'],
    ['BAD_PARAM', '缺少必要参数', '检查调用代码'],
    ['BAD_APP', 'AppID 不存在', '检查配置'],
    ['APP_DISABLED', '应用已被禁用', '联系管理员'],
    ['BAD_SIGN', '签名错误', '检查拼接顺序与密钥'],
    ['BAD_TS', '时间戳超差', '提示用户校准本机时间'],
    ['REPLAY', '重复请求', 'nonce 换新值'],
    ['RATE_LIMIT', '请求过于频繁', '降低频率，稍后重试'],
    ['CARD_NOT_FOUND', '卡密不存在', '提示卡密错误'],
    ['CARD_BANNED', '卡密已封禁', '禁止使用'],
    ['CARD_EXPIRED', '卡密已过期', '提示续费'],
    ['CARD_USED_UP', '额度已用完', '提示充值或换卡'],
    ['DEVICE_LIMIT', '绑定设备数已满', '提示换绑或联系客服'],
    ['DEVICE_MISMATCH', '未绑定当前设备', '提示换绑'],
    ['UNBIND_LIMIT', '换绑次数用尽', '提示联系管理员'],
    ['NOT_ACTIVATED', '尚未激活', '无需解绑']
  ];

  function fillDocs() {
    // 优先用「系统设置」里配的对外地址；没配才退回当前浏览器地址。
    // 否则从内网 / 反向代理 / 隧道访问时，文档里写出去的地址会跟着变。
    var base = PUBLIC_BASE || location.origin;
    $('docBase').textContent = base;
    api('/api/admin/apps').then(function (d) {
      var appId = 'app_xxxxxxxxxxxxxxxx', secret = '你的AppSecret';
      if (d.ok && d.items.length) {
        appId = d.items[0].app_id;
        secret = d.items[0].app_secret;
        $('docAppId').textContent = appId;
        $('docSecret').textContent = secret.slice(0, 12) + '…（完整值在「应用」页复制）';
      }
      renderExamples(base, appId, secret);
    }).catch(function () {});

    $('respBody').innerHTML = RESP_ROWS.map(function (r) {
      var cls = r[0] === 'OK' ? 'b-success' : 'b-danger';
      return '<tr><td><span class="badge ' + cls + ' plain">' + r[0] + '</span></td>' +
        '<td>' + r[1] + '</td><td class="dim">' + r[2] + '</td></tr>';
    }).join('');
  }

  function renderExamples(base, appId, secret) {
    var py = [
      'import hashlib, hmac, json, subprocess, time, urllib.request, uuid',
      '',
      'APP_ID     = "' + appId + '"',
      'APP_SECRET = "' + (secret.length > 16 ? secret.slice(0, 16) + '..."' : secret + '"'),
      'BASE       = "' + base + '"',
      '',
      'def machine_id():',
      '    """硬件指纹：CPU + 主板 + 硬盘序列号 -> SHA256 前 32 位"""',
      '    parts = []',
      '    for cmd in ("wmic csproduct get uuid",',
      '                "wmic baseboard get serialnumber",',
      '                "wmic diskdrive get serialnumber"):',
      '        out = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout',
      '        lines = [x.strip() for x in out.splitlines() if x.strip()]',
      '        if len(lines) > 1:',
      '            parts.append(lines[1])',
      '    raw = "|".join(parts) or "fallback"',
      '    return hashlib.sha256(raw.encode()).hexdigest()[:32].upper()',
      '',
      'def call(path, code, cost=None):',
      '    p = {',
      '        "app_id":     APP_ID,',
      '        "code":       code.strip().upper(),',
      '        "machine_id": machine_id(),',
      '        "ts":         int(time.time()),',
      '        "nonce":      uuid.uuid4().hex[:16],',
      '    }',
      '    if cost is not None:',
      '        p["cost"] = str(cost)',
      '    # 除 sign 外全部参数按 key 升序拼接，空值也保留',
      '    raw = "&".join("%s=%s" % (k, p[k]) for k in sorted(p))',
      '    p["sign"] = hmac.new(APP_SECRET.encode(), raw.encode(),',
      '                         hashlib.sha256).hexdigest()',
      '    body = json.dumps(p).encode()',
      '    req = urllib.request.Request(BASE + path, data=body, method="POST",',
      '                                 headers={"Content-Type": "application/json"})',
      '    with urllib.request.urlopen(req, timeout=8) as r:',
      '        return json.loads(r.read().decode())',
      '',
      '# ---- 激活 / 用户输入卡密 ----',
      'res = call("/api/v1/verify", "ABCD-EFGH-JKLM-NPQR")',
      'if res["ok"]:',
      '    d = res["data"]',
      '    print("通过 |", d["card_type_text"], "|", d["expires_text"],',
      '          "| 剩余额度", d["remaining_value"])',
      'else:',
      '    print("失败：", res["msg"], "(", res["err"], ")")',
      '',
      '# ---- 运行中每 3~5 分钟心跳 ----',
      '# hb = call("/api/v1/heartbeat", code)',
      '# if not hb["ok"]: 提示用户并退出程序'
    ].join('\n');

    var cs = [
      'using System;',
      'using System.Collections.Generic;',
      'using System.Linq;',
      'using System.Management;',
      'using System.Net.Http;',
      'using System.Security.Cryptography;',
      'using System.Text;',
      'using System.Text.Json;',
      'using System.Threading.Tasks;',
      '',
      'static class KeyAuth',
      '{',
      '    const string AppId     = "' + appId + '";',
      '    const string AppSecret = "你的AppSecret";',
      '    const string Base      = "' + base + '";',
      '    static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(8) };',
      '',
      '    public static string MachineId()',
      '    {',
      '        var sb = new StringBuilder();',
      '        foreach (var (cls, prop) in new[] {',
      '            ("Win32_ComputerSystemProduct", "UUID"),',
      '            ("Win32_BaseBoard", "SerialNumber"),',
      '            ("Win32_DiskDrive", "SerialNumber") })',
      '        {',
      '            try {',
      '                using var q = new ManagementObjectSearcher($"SELECT {prop} FROM {cls}");',
      '                foreach (ManagementObject mo in q.Get()) {',
      '                    var v = mo[prop]?.ToString()?.Trim();',
      '                    if (!string.IsNullOrEmpty(v)) sb.Append(v).Append(\'|\');',
      '                    break;',
      '                }',
      '            } catch { }',
      '        }',
      '        using var sha = SHA256.Create();',
      '        var hex = BitConverter.ToString(',
      '            sha.ComputeHash(Encoding.UTF8.GetBytes(sb.ToString()))).Replace("-", "");',
      '        return hex.Substring(0, 32).ToUpperInvariant();',
      '    }',
      '',
      '    public static async Task<JsonElement> Call(string path, string code, int? cost = null)',
      '    {',
      '        var p = new SortedDictionary<string, string>',
      '        {',
      '            ["app_id"]     = AppId,',
      '            ["code"]       = code.Trim().ToUpperInvariant(),',
      '            ["machine_id"] = MachineId(),',
      '            ["ts"]         = DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString(),',
      '            ["nonce"]      = Guid.NewGuid().ToString("N").Substring(0, 16),',
      '        };',
      '        if (cost.HasValue) p["cost"] = cost.Value.ToString();',
      '',
      '        var raw = string.Join("&", p.Select(kv => kv.Key + "=" + kv.Value));',
      '        using (var h = new HMACSHA256(Encoding.UTF8.GetBytes(AppSecret)))',
      '            p["sign"] = BitConverter.ToString(',
      '                h.ComputeHash(Encoding.UTF8.GetBytes(raw)))',
      '                .Replace("-", "").ToLowerInvariant();',
      '',
      '        using var content = new StringContent(JsonSerializer.Serialize(p),',
      '                                              Encoding.UTF8, "application/json");',
      '        using var resp = await Http.PostAsync(Base + path, content);',
      '        var doc = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());',
      '        return doc.RootElement.Clone();',
      '    }',
      '',
      '    // 用法：',
      '    // var r = await KeyAuth.Call("/api/v1/verify", "ABCD-EFGH-JKLM-NPQR");',
      '    // if (!r.GetProperty("ok").GetBoolean()) { MessageBox.Show("授权失败"); return; }',
      '}'
    ].join('\n');

    var js = [
      'import crypto from "crypto";',
      '',
      'const APP_ID     = "' + appId + '";',
      'const APP_SECRET = "你的AppSecret";',
      'const BASE       = "' + base + '";',
      '',
      'async function call(path, code, cost) {',
      '  const params = {',
      '    app_id:     APP_ID,',
      '    code:       code.trim().toUpperCase(),',
      '    machine_id: machineId(),',
      '    ts:         Math.floor(Date.now() / 1000),',
      '    nonce:      crypto.randomBytes(8).toString("hex"),',
      '  };',
      '  if (cost !== undefined) params.cost = String(cost);',
      '',
      '  const raw = Object.keys(params).sort()',
      '    .map(k => `${k}=${params[k]}`).join("&");',
      '  params.sign = crypto.createHmac("sha256", APP_SECRET)',
      '    .update(raw).digest("hex");',
      '',
      '  const res = await fetch(BASE + path, {',
      '    method: "POST",',
      '    headers: { "Content-Type": "application/json" },',
      '    body: JSON.stringify(params),',
      '  });',
      '  return res.json();',
      '}',
      '',
      'call("/api/v1/verify", "ABCD-EFGH-JKLM-NPQR").then(r => {',
      '  if (r.ok) console.log("通过，到期 " + r.data.expires_text);',
      '  else      console.log("失败：" + r.msg);',
      '});',
      '',
      '// 心跳：setInterval(() => call("/api/v1/heartbeat", code), 3 * 60 * 1000);'
    ].join('\n');

    $('tab-py').textContent = py;
    $('tab-cs').textContent = cs;
    $('tab-js').textContent = js;
  }

  /* ============================================================
     登录
     ============================================================ */
  // 一把简洁的钥匙：环形柄 + 45° 直杆 + 两个齿，小尺寸下也能看清
  var SVG_KEY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="8" cy="16" r="4"/><path d="M11 13 20 4"/>' +
    '<path d="M17 7l2.5 2.5"/><path d="M19.5 4.5 22 7"/></svg>';
  var SVG_EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  var SVG_EYE_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.9 17.9A10 10 0 0112 20c-7 0-11-8-11-8a19 19 0 015.1-6M9.9 4.2A11 11 0 0112 4c7 0 11 8 11 8a19 19 0 01-2.2 3.2M1 1l22 22"/></svg>';

  /* ============================================================
     登录页（单屏 + 定稿）
     标记 → 标题 → 一句话 → 密码框 → 登录按钮，一屏走完。
     背景两层，纯 CSS animation 驱动，无 Canvas、无常驻 rAF：
       1. .lg-bg    珠光白底：近白 + 极淡冷暖柔光 + 对角渐变兜底
       2. .lg-fig   双层视差点阵（近景快 / 远景慢），向边缘渐隐
     图案层的硬约束：大间距、低对比、必须渐隐。变小变密变实就会退回
     "满屏纹理"那个坑（点阵 / 波纹 / 扭索纹都栽在这上面）。
     ============================================================ */
  var SVG_MARK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="3.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M11.9 12.1A4.55 4.55 0 1 0 6.1 6.3a4.55 4.55 0 0 0 5.8 5.8Z"/>' +
    '<path d="M11.9 12.1 19.4 19.6"/>' +
    '<path d="M16.6 16.8 18.9 14.5"/>' +
    '<path d="M19.4 19.6 21.7 17.3"/></svg>';
  var SVG_LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="4" y="10.5" width="16" height="10" rx="2.6"/>' +
    '<path d="M8 10.5V7.6a4 4 0 0 1 8 0v2.9"/></svg>';

  /* 定稿：风格 = 珠光白（pearl），图案 = 双层视差点阵（dots）。
     选型期的多风格 / 多图案开关已随 login.css 里的候选一起清掉。
     以后要换风格：改这一行 + login.css 里 .lg[data-bg="..."] 的变量块。 */
  function lgStyle() { return 'pearl'; }

  function login() {
    if ($('loginRoot').querySelector('.lg')) { return; }
    closeModal();

    $('loginRoot').innerHTML = [
      '<div class="lg" id="loginScreen" data-skin="paper" data-bg="pearl">',
      '<div class="lg-bg"></div>',
      '<div class="lg-fig"></div>',
      '<div class="lg-ring" id="lgRing"></div>',

      '<div class="lg-panel" id="lgPanel">',
      '<span class="lg-mark">' + SVG_MARK + '</span>',
      '<h1 class="lg-h">欢迎回来</h1>',
      '<p class="lg-sub">登录以使用完整功能</p>',
      '<div class="lg-field" id="lgUserField" style="display:none">',
      '<div class="lg-input">',
      '<input type="text" id="lgUser" autocomplete="username" ' +
      'autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="账号" />',
      '</div>',
      '</div>',
      '<div class="lg-field">',
      '<div class="lg-input">',
      '<input type="text" id="lgTok" autocomplete="off" autocapitalize="off" ' +
      'autocorrect="off" spellcheck="false" placeholder="请输入密码" value="" />',
      '<button class="lg-eye" id="lgEye" type="button" tabindex="-1" ' +
      'title="隐藏">' + SVG_EYE_OFF + '</button>',
      '</div>',
      '</div>',
      /* 开了两步验证才展开。不用 hidden 是因为 .lg-field 的动画按 display 走 */
      '<div class="lg-field" id="lgCodeField" style="display:none">',
      '<div class="lg-input">',
      '<input type="text" id="lgCode" autocomplete="one-time-code" ' +
      'inputmode="numeric" maxlength="9" spellcheck="false" ' +
      'placeholder="6 位验证码，或恢复码 ABCD-EFGH" />',
      '</div>',
      '</div>',
      '<button class="lg-btn" id="lgBtn">' + SVG_LOCK + '<span>登录</span></button>',
      '<div class="lg-msg" id="lgMsg"></div>',
      '<div style="margin-top:14px;text-align:center;font-size:12px">' +
      '<a id="lgAlt" style="cursor:pointer;opacity:.62;text-decoration:underline">' +
      '用账号密码登录</a></div>',
      '</div>',
      '</div>'
    ].join('');

    var screen = $('loginScreen');
    var panel = $('lgPanel');
    var inp = $('lgTok');
    var btn = $('lgBtn');
    var msg = $('lgMsg');
    var ring = $('lgRing');
    var masked = false;

    /* 密码默认明文（掩码成一排点没法核对粘贴对不对），点眼睛才遮起来 */
    $('lgEye').onclick = function () {
      masked = !masked;
      inp.type = masked ? 'password' : 'text';
      this.innerHTML = masked ? SVG_EYE : SVG_EYE_OFF;
      this.title = masked ? '显示' : '隐藏';
      inp.focus();
    };

    var setMsg = function (text, ok) {
      msg.className = 'lg-msg' + (ok ? ' ok' : '');
      msg.innerHTML = text
        ? ic(ok ? 'check' : 'alert', 13) + '<span>' + esc(text) + '</span>' : '';
    };

    var resetBtn = function () {
      btn.disabled = false;
      btn.innerHTML = SVG_LOCK + '<span>登录</span>';
    };

    // 两种登录方式：令牌（脚本/超级令牌）和账号密码（管理员账号体系）
    // 记住上次用的是哪种：退出后不用每次再点一遍「用账号密码登录」
    var useAccount = localStorage.getItem('ka_mode') === 'account';
    var needCode = false;                 /* 服务端回了 NEED_TOTP 才展开验证码框 */
    var codeField = $('lgCodeField');
    var codeInput = $('lgCode');
    var showCode = function (on) {
      needCode = on;
      codeField.style.display = on ? '' : 'none';
      if (!on) { codeInput.value = ''; }
    };
    var applyMode = function () {
      $('lgUserField').style.display = useAccount ? '' : 'none';
      $('lgAlt').textContent = useAccount ? '改用令牌登录' : '用账号密码登录';
      inp.placeholder = useAccount ? '密码' : '请输入密码';
    };
    applyMode();

    $('lgAlt').onclick = function () {
      useAccount = !useAccount;
      localStorage.setItem('ka_mode', useAccount ? 'account' : 'token');
      showCode(false);
      applyMode();
      setMsg('');
      (useAccount ? $('lgUser') : inp).focus();
    };

    var enter = function (tok) {
      TOKEN = tok;
      localStorage.setItem('ka_token', tok);
      // 顺手记下这次用的方式，退出后登录页直接回到同一种
      localStorage.setItem('ka_mode', useAccount ? 'account' : 'token');
      btn.innerHTML = ic('check', 17) + '<span>正在进入</span>';
      ring.classList.remove('go');
      void ring.offsetWidth;          /* 强制回流，让动画可以重复触发 */
      ring.classList.add('go');
      cloud_init();
      loadFor(CURRENT);
      setTimeout(hideLogin, 760);
    };

    var failWith = function (text) {
      resetBtn();
      setMsg(text);
      panel.classList.remove('shake');
      void panel.offsetWidth;          /* 强制回流，让抖动可以重复触发 */
      panel.classList.add('shake');
      inp.focus();
      inp.select();
    };

    var doLogin = function () {
      if (btn.disabled) { return; }
      var pwd = inp.value;

      if (useAccount) {
        var u = $('lgUser').value.trim();
        if (!u || !pwd) { setMsg('账号和密码都要填'); inp.focus(); return; }
        if (needCode && !codeInput.value.trim()) {
          setMsg('请输入两步验证码'); codeInput.focus(); return;
        }
        btn.disabled = true;
        btn.innerHTML = '<span class="lg-spin"></span><span>正在验证</span>';
        setMsg('');
        post('/api/admin/auth', {
          username: u, password: pwd,
          code: needCode ? codeInput.value.trim() : ''
        }).then(function (d) {
          if (d.ok) { enter(d.token); return; }
          if (d.err === 'NEED_TOTP') {
            showCode(true);
            resetBtn();
            /* 这条不是「成功」，别用绿勾样式 */
            setMsg(d.msg || '请输入两步验证码');
            codeInput.focus();
            return;
          }
          if (d.err === 'BAD_TOTP') {
            showCode(true);
            failWith(d.msg || '验证码不正确');
            codeInput.focus();
            codeInput.select();
            return;
          }
          /* 连错太多次：服务端已经锁了，把剩余时间说清楚，别让人反复试 */
          if (d.err === 'LOCKED') {
            resetBtn();
            setMsg(d.msg || '尝试次数过多，请稍后再试');
            return;
          }
          failWith(d.msg || '登录失败');
        }).catch(function () {
          resetBtn();
          setMsg('连不上服务');
        });
        return;
      }

      var t = pwd.trim();
      if (!t) { setMsg('请输入密码'); inp.focus(); return; }
      btn.disabled = true;
      btn.innerHTML = '<span class="lg-spin"></span><span>正在验证</span>';
      setMsg('');
      TOKEN = t;

      api('/api/admin/settings').then(function (d) {
        if (!d.ok) { failWith('密码不正确'); return; }
        enter(t);
      }).catch(function () {
        resetBtn();
        setMsg('连不上服务');
      });
    };

    btn.onclick = doLogin;
    $('lgUser').onkeydown = function (e) { if (e.key === 'Enter') { inp.focus(); } };
    inp.onkeydown = function (e) { if (e.key === 'Enter') { doLogin(); } };
    $('lgCode').onkeydown = function (e) { if (e.key === 'Enter') { doLogin(); } };

    /* 单屏直接聚焦输入框，省一次点击。JS 触发的是 :focus 而不是 :focus-visible，
       所以不会挂出浏览器那个又粗又黑的焦点环。 */
    setTimeout(function () { (useAccount ? $('lgUser') : inp).focus(); }, 120);

    /* 卡片跟随鼠标做极轻的 3D 倾斜（约 ±3.5°）+ 微位移。
       幅度刻意压得很小：大了会晕，也显廉价。 */
    screen.addEventListener('mousemove', function (e) {
      var r = panel.getBoundingClientRect();
      var cx = (e.clientX - (r.left + r.width / 2)) / r.width;
      var cy = (e.clientY - (r.top + r.height / 2)) / r.height;
      panel.style.transform =
        'perspective(1100px)' +
        ' rotateX(' + (-cy * 3.5).toFixed(2) + 'deg)' +
        ' rotateY(' + (cx * 4).toFixed(2) + 'deg)' +
        ' translate3d(' + (cx * 5).toFixed(2) + 'px,' +
        (cy * 5).toFixed(2) + 'px,0)';
    });
    screen.addEventListener('mouseleave', function () { panel.style.transform = ''; });

  }

  function hideLogin() {
    var s = $('loginScreen');
    if (!s) { return; }
    s.classList.add('out');
    setTimeout(function () { $('loginRoot').innerHTML = ''; }, 660);
  }

  function logout() {
    TOKEN = '';
    localStorage.removeItem('ka_token');
    setConn(false, '未连接');
    login();
    toast('已退出登录');
  }

  /* 进后台的第一批基础数据：品牌名 + 应用缓存。
     删命令面板时被连带删掉过一次，表现为「登录后立刻弹回登录页」——
     cloud_init 不存在 → 抛 ReferenceError → 外层 catch 走了 login()。 */
  function cloud_init() {
    api('/api/admin/settings').then(function (d) {
      if (!d.ok) { return; }
      $('brandName').textContent = d.settings.site_name || 'KeyAuth';
      $('brandDesc').textContent = d.settings.site_desc || '卡密授权验证系统';
    }).catch(function () {});
    api('/api/admin/apps').then(function (d) { if (d.ok) { APP_CACHE = d.items; } })
      .catch(function () {});
    loadWhoami();
  }

  /* ============================================================
     启动
     ============================================================ */
  function initNav() {
    var html = '';
    NAV.forEach(function (n) {
      if (n.group) { html += '<div class="nav-group">' + n.group + '</div>'; return; }
      html += '<div class="nav-item" data-id="' + n.id + '" onclick="KA.go(\'' + n.id + '\')">' +
        ic(n.icon, 16) + '<span>' + n.name + '</span></div>';
    });
    $('nav').innerHTML = html;
  }

  function boot() {
    // 带 ?debug=1 访问时，把运行时报错直接画在页面上，方便排查"按钮点了没反应"
    if (/[?&]debug=1/.test(location.search)) {
      var box = document.createElement('div');
      box.id = 'debugBox';
      box.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;' +
        'background:#1a1d26;color:#f87171;font:11.5px/1.6 ui-monospace,monospace;' +
        'padding:8px 12px;max-height:30vh;overflow:auto;border-top:1px solid #333';
      box.textContent = '[KeyAuth debug] 运行时错误会显示在这里\n';
      document.body.appendChild(box);
      window.addEventListener('error', function (e) {
        box.textContent += '[error] ' + e.message + '  @' +
          String(e.filename || '').split('/').pop() + ':' + e.lineno + '\n';
      });
      window.addEventListener('unhandledrejection', function (e) {
        var r = e.reason;
        box.textContent += '[promise] ' + ((r && r.message) ? r.message : String(r)) + '\n';
      });
    }

    applyTheme(localStorage.getItem('ka_theme') || 'light');
    $('themeBtn').onclick = toggleThemeCb;
    initNav();

    document.querySelectorAll('#docTabs .tab').forEach(function (t) {
      t.onclick = function () {
        document.querySelectorAll('#docTabs .tab').forEach(function (x) {
          x.classList.remove('active');
        });
        t.classList.add('active');
        ['py', 'cs', 'js', 'resp'].forEach(function (k) {
          $('tab-' + k).classList.toggle('hidden', k !== t.getAttribute('data-tab'));
        });
      };
    });
    document.addEventListener('click', function () { closeMenu(); });

    if (TOKEN) {
      api('/api/admin/settings').then(function (d) {
        if (d.ok) { cloud_init(); loadFor('overview'); } else { login(); }
      }).catch(function () { login(); });
    } else {
      login();
    }
  }

  /* ============================================================
     代理商（分销）
     ============================================================ */
  var AGENT_CACHE = [];

  function loadAgents() {
    api('/api/admin/agents').then(function (d) {
      if (!d.ok) { return; }
      AGENT_CACHE = d.items || [];
      if (!AGENT_CACHE.length) {
        $('agentBody').innerHTML = '<tr><td colspan="8"><div class="empty">' +
          ic('users', 40) + '<p>还没有代理商</p>' +
          '<div class="sm">点右上「新建代理商」开一个账号</div></div></td></tr>';
        return;
      }
      $('agentBody').innerHTML = AGENT_CACHE.map(function (a) {
        var used = (a.quotas || []).reduce(function (s, q) { return s + q.quota_used; }, 0);
        var tot = a.quota_total || 0;
        var st = a.status === 'active'
          ? '<span class="badge b-success">启用</span>'
          : '<span class="badge b-gray">停用</span>';
        var qtxt = tot ? used + ' / ' + tot + '　剩 ' + a.quota_left : '<span class="dim">未分配</span>';
        return '<tr>' +
          '<td class="code">' + esc(a.username) + '</td>' +
          '<td>' + esc(a.name) + '</td>' +
          '<td>' + st + '</td>' +
          '<td class="num">' + a.cards_made + '</td>' +
          '<td class="num">' + qtxt + '</td>' +
          '<td class="dim">' + ((a.apps || []).length
            ? (a.apps || []).length + ' 个应用'
            : '<span class="dim">未分配</span>') + '</td>' +
          '<td class="dim num">' + esc(a.last_login_text) + '</td>' +
          '<td><div class="btn-group">' +
          '<button class="btn ghost sm" onclick="editAgentQuotas(' + a.id + ')">配额</button>' +
          '<button class="btn ghost sm" onclick="editAgent(' + a.id + ')">编辑</button>' +
          '<button class="btn ghost sm" onclick="resetAgentPwd(' + a.id + ')">改密</button>' +
          '<button class="btn ghost sm" onclick="toggleAgent(' + a.id + ')">' +
          (a.status === 'active' ? '停用' : '启用') + '</button>' +
          '<button class="btn ghost sm danger" onclick="delAgent(' + a.id + ')">删除</button>' +
          '</div></td></tr>';
      }).join('');
    }).catch(function () {});
  }

  function agentById(id) {
    return AGENT_CACHE.filter(function (a) { return String(a.id) === String(id); })[0];
  }

  function newAgent() {
    modal({
      title: '新建代理商',
      okText: '创建',
      body:
        '<div class="grid g2" style="margin-bottom:12px">' +
        '<div class="field"><label>登录账号</label><input type="text" id="agUser" placeholder="字母数字，如 agent01" /></div>' +
        '<div class="field"><label>显示名称</label><input type="text" id="agNick" placeholder="如 华东-张三" /></div>' +
        '</div>' +
        '<div class="field" style="margin-bottom:12px"><label>初始密码</label>' +
        '<input type="text" id="agPass" placeholder="至少 6 位，建完告诉他" /></div>' +
        '<div class="field"><label>备注</label><input type="text" id="agNote" placeholder="选填" /></div>' +
        '<p class="field" style="margin:12px 0 0"><span class="hint">建完后点「配额」分配他能制哪些应用、每种卡多少张</span></p>',
      onOk: function (m) {
        var body = {
          action: 'create',
          username: m.querySelector('#agUser').value.trim(),
          name: m.querySelector('#agNick').value.trim(),
          password: m.querySelector('#agPass').value,
          note: m.querySelector('#agNote').value.trim()
        };
        if (!body.username) { toast('账号不能空', 'error'); return false; }
        if (body.password.length < 6) { toast('密码至少 6 位', 'error'); return false; }
        post('/api/admin/agents', body).then(function (d) {
          if (!d.ok) { toast(d.msg || '创建失败', 'error'); return; }
          toast('已创建，去分配配额');
          loadAgents();
        }).catch(function () {});
      }
    });
  }

  function editAgent(id) {
    var a = agentById(id);
    if (!a) { return; }
    modal({
      title: '编辑代理商',
      okText: '保存',
      body:
        '<div class="grid g2" style="margin-bottom:12px">' +
        '<div class="field"><label>显示名称</label><input type="text" id="agNick" value="' + esc(a.name) + '" /></div>' +
        '<div class="field"><label>状态</label><select id="agStatus">' +
        '<option value="active"' + (a.status === 'active' ? ' selected' : '') + '>启用</option>' +
        '<option value="disabled"' + (a.status !== 'active' ? ' selected' : '') + '>停用</option>' +
        '</select></div></div>' +
        '<div class="field"><label>备注</label><input type="text" id="agNote" value="' + esc(a.note || '') + '" /></div>',
      onOk: function (m) {
        post('/api/admin/agents', {
          action: 'update', id: id,
          name: m.querySelector('#agNick').value.trim(),
          status: m.querySelector('#agStatus').value,
          note: m.querySelector('#agNote').value.trim()
        }).then(function (d) {
          if (!d.ok) { toast(d.msg || '保存失败', 'error'); return; }
          toast('已保存');
          loadAgents();
        }).catch(function () {});
      }
    });
  }

  function resetAgentPwd(id) {
    var a = agentById(id);
    modal({
      title: '重置密码', okText: '确认重置',
      body: '<p style="margin:0 0 12px;font-size:12.5px;color:var(--text-3)">' +
        '账号「' + esc(a ? a.username : id) + '」的现有会话会立即失效。</p>' +
        '<div class="field"><label>新密码</label><input type="text" id="agNewPwd" placeholder="至少 6 位" /></div>',
      onOk: function (m) {
        var p = m.querySelector('#agNewPwd').value;
        if (p.length < 6) { toast('至少 6 位', 'error'); return false; }
        post('/api/admin/agents', { action: 'reset_password', id: id, password: p })
          .then(function (d) {
            if (!d.ok) { toast(d.msg || '失败', 'error'); return; }
            toast('已重置，把新密码告诉他');
            loadAgents();
          }).catch(function () {});
      }
    });
  }

  function toggleAgent(id) {
    var a = agentById(id);
    if (!a) { return; }
    var next = a.status === 'active' ? 'disabled' : 'active';
    post('/api/admin/agents', { action: 'update', id: id, status: next }).then(function (d) {
      if (!d.ok) { toast(d.msg || '失败', 'error'); return; }
      toast(next === 'active' ? '已启用' : '已停用，他的会话随即失效');
      loadAgents();
    }).catch(function () {});
  }

  function delAgent(id) {
    var a = agentById(id);
    modal({
      title: '删除代理商', danger: true, okText: '确认删除',
      body: '<p style="margin:0">确定删除「' + esc(a ? a.username : id) + '」吗？</p>' +
        '<p style="margin:8px 0 0;font-size:12.5px;color:var(--text-3)">' +
        '他制的卡密会保留在卡密库里，但归属清空；配额和账号一起删除。</p>',
      onOk: function () {
        post('/api/admin/agents', { action: 'delete', id: id }).then(function (d) {
          if (d.err === 'HAS_CARDS') {
            closeModal();
            modal({
              title: '该代理商名下还有卡密', danger: true, okText: '删除并保留卡密',
              body: '<p style="margin:0">' + esc(d.msg) + '</p>',
              onOk: function () {
                post('/api/admin/agents', { action: 'delete', id: id, force: true })
                  .then(function (r2) {
                    if (!r2.ok) { toast(r2.msg || '失败', 'error'); return; }
                    toast('已删除');
                    loadAgents();
                  }).catch(function () {});
              }
            });
            return false;
          }
          if (!d.ok) { toast(d.msg || '失败', 'error'); return false; }
          toast('已删除');
          loadAgents();
        }).catch(function () {});
      }
    });
  }

  // ---- 配额编辑：一行一条「应用 × 卡规格 × 数量」
  function quotaRowHtml(q) {
    var typeOpts = [['time', '天数卡'], ['hour', '小时卡']].map(function (t) {
      return '<option value="' + t[0] + '"' +
        (q && q.card_type === t[0] ? ' selected' : '') + '>' + t[1] + '</option>';
    }).join('');
    var appOpts = APP_CACHE.map(function (a) {
      return '<option value="' + esc(a.app_id) + '"' +
        (q && q.app_id === a.app_id ? ' selected' : '') + '>' + esc(a.name) + '</option>';
    }).join('');
    return '<div class="qrow" style="display:flex;gap:8px;align-items:center;margin-bottom:8px">' +
      '<select class="q-app" style="flex:2">' + appOpts + '</select>' +
      '<select class="q-type" style="width:96px">' + typeOpts + '</select>' +
      '<input class="q-dur" type="number" min="0" style="width:80px" placeholder="天数/小时" value="' +
      (q ? q.duration_days : 30) + '" title="天数卡填天数，小时卡填小时数，0=永久" />' +
      '<input class="q-dev" type="number" min="1" style="width:66px" placeholder="设备" value="' +
      (q ? q.max_devices : 1) + '" title="可绑定设备数" />' +
      '<input class="q-unb" type="number" min="0" style="width:66px" placeholder="换绑" value="' +
      (q ? q.unbind_limit : 1) + '" title="换绑次数" />' +
      '<input class="q-total" type="number" min="0" style="width:80px" placeholder="数量" value="' +
      (q ? q.quota_total : 10) + '" title="这条规格的总配额" />' +
      '<button class="btn ghost sm q-del" type="button" title="删除这一行" style="padding:4px 8px">×</button>' +
      '</div>';
  }

  function editAgentQuotas(id) {
    var a = agentById(id);
    if (!a) { return; }
    var ensure = APP_CACHE.length
      ? Promise.resolve()
      : api('/api/admin/apps').then(function (d) {
          if (d.ok) { APP_CACHE = d.items; }
        });

    ensure.then(function () {
      if (!APP_CACHE.length) { toast('先去「应用」页建一个应用', 'warn'); return; }
      var rows = (a.quotas || []).map(quotaRowHtml).join('') || quotaRowHtml(null);
      var m = modal({
        title: '分配配额 · ' + a.username,
        okText: '保存配额',
        width: '760px',
        body:
          '<p style="margin:0 0 10px;font-size:12.5px;color:var(--text-3)">' +
          '一行 = 一种规格。代理商只能按这里的规格制卡，数量用完为止。' +
          '修改会覆盖原有配额（已用数量保留）。</p>' +
          '<div style="display:flex;gap:8px;font-size:11.5px;color:var(--text-3);' +
          'padding:0 2px 6px"><span style="flex:2">应用</span><span style="width:96px">类型</span>' +
          '<span style="width:80px">时长</span><span style="width:66px">设备</span>' +
          '<span style="width:66px">换绑</span><span style="width:80px">数量</span><span style="width:32px"></span></div>' +
          '<div id="qRows">' + rows + '</div>' +
          '<div style="margin-top:6px"><button class="btn ghost sm" id="qAdd" type="button">+ 再加一行</button></div>',
        onOk: function (mm) {
          var items = [];
          Array.prototype.forEach.call(mm.querySelectorAll('#qRows .qrow'), function (r) {
            items.push({
              app_id: r.querySelector('.q-app').value,
              card_type: r.querySelector('.q-type').value,
              duration_days: parseInt(r.querySelector('.q-dur').value || '0', 10) || 0,
              max_devices: parseInt(r.querySelector('.q-dev').value || '1', 10) || 1,
              unbind_limit: parseInt(r.querySelector('.q-unb').value || '0', 10) || 0,
              quota_total: parseInt(r.querySelector('.q-total').value || '0', 10) || 0
            });
          });
          if (!items.length) { toast('至少保留一行', 'error'); return false; }
          post('/api/admin/agents', { action: 'set_quotas', id: id, items: items })
            .then(function (d) {
              if (!d.ok) { toast(d.msg || '保存失败', 'error'); return; }
              toast('配额已保存');
              loadAgents();
            }).catch(function () {});
        },
        onMount: function (mm) {
          mm.querySelector('#qAdd').onclick = function () {
            var box = mm.querySelector('#qRows');
            var div = document.createElement('div');
            div.innerHTML = quotaRowHtml(null);
            box.appendChild(div.firstChild);
          };
          mm.querySelector('#qRows').onclick = function (e) {
            if (!e.target.classList.contains('q-del')) { return; }
            var rows = mm.querySelectorAll('#qRows .qrow');
            if (rows.length <= 1) { toast('至少保留一行', 'warn'); return; }
            e.target.parentNode.remove();
          };
        }
      });
      return m;
    });
  }

  /* ============================================================
     管理员账号（多账号 + 角色）
     ============================================================ */
  var CURRENT_ADMIN = null;
  var ADMIN_LIST = [];

  var ROLE_TEXT = { owner: '拥有者', admin: '管理员', viewer: '只读' };

  function loadWhoami() {
    api('/api/admin/me').then(function (d) {
      if (!d.ok) { return; }
      CURRENT_ADMIN = d.admin;
      var a = d.admin;
      $('whoami').textContent = (a.name || a.username) +
        '（' + (ROLE_TEXT[a.role] || a.role) + '）' +
        (a.is_super ? ' · 超级令牌' : '') +
        (a.totp_enabled ? ' · 两步验证已开启' : '');
      // 顶栏：谁在用这个后台，一眼能看见，旁边就是退出
      var tu = $('topUser'), tr = $('topRole');
      if (tu) { tu.textContent = a.username; tu.title = a.name || a.username; }
      if (tr) {
        tr.textContent = (ROLE_TEXT[a.role] || a.role) +
          (a.is_super ? ' · 超级令牌' : '');
      }
      // 非拥有者看不到账号表格和「新建账号」，但「我的两步验证」得留着
      var onlyOwner = function (show) {
        ['adminTableWrap', 'btnNewAdmin'].forEach(function (id) {
          var el = $(id);
          if (el) { el.style.display = show ? '' : 'none'; }
        });
      };
      if (a.role === 'owner') { onlyOwner(true); } else { onlyOwner(false); }
    }).catch(function () {});
  }

  function loadAdmins() {
    api('/api/admin/admins').then(function (d) {
      if (!d.ok) {
        // 403 = 不是拥有者：藏掉表格和新建按钮，卡片留着给「我的两步验证」
        ['adminTableWrap', 'btnNewAdmin'].forEach(function (id) {
          var el = $(id);
          if (el) { el.style.display = 'none'; }
        });
        return;
      }
      ['adminTableWrap', 'btnNewAdmin'].forEach(function (id) {
        var el = $(id);
        if (el) { el.style.display = ''; }
      });
      ADMIN_LIST = d.items || [];
      $('adminBody').innerHTML = ADMIN_LIST.map(function (a) {
        var st = a.status === 'active'
          ? '<span class="badge b-success">启用</span>'
          : '<span class="badge b-gray">停用</span>';
        var roleSel = a.is_super
          ? '<span class="badge b-primary plain">' + esc(a.role_text) + '</span>'
          : '<select onchange="setAdminRole(' + a.id + ',this.value)" style="width:96px">' +
            ['owner', 'admin', 'viewer'].map(function (r) {
              return '<option value="' + r + '"' +
                (a.role === r ? ' selected' : '') + '>' + ROLE_TEXT[r] + '</option>';
            }).join('') + '</select>';
        var totpCell = a.is_super
          ? '<span class="dim">—</span>'
          : (a.totp_enabled
            ? '<span class="badge b-success">已开启</span>'
            : '<span class="badge b-gray">未开启</span>');
        var ops = a.is_super
          ? '<span class="dim" style="font-size:12px">配置文件里的令牌，无法在此修改</span>'
          : '<div class="btn-group">' +
            '<button class="btn ghost sm" onclick="resetAdminPwd(' + a.id + ')">改密</button>' +
            '<button class="btn ghost sm" onclick="toggleAdmin(' + a.id + ')">' +
            (a.status === 'active' ? '停用' : '启用') + '</button>' +
            '<button class="btn ghost sm" onclick="kickAdmin(' + a.id + ')">踢下线</button>' +
            (a.totp_enabled
              ? '<button class="btn ghost sm" onclick="offAdminTotp(' + a.id + ')">关两步</button>'
              : '') +
            '<button class="btn ghost sm danger" onclick="delAdmin(' + a.id + ')">删除</button>' +
            '</div>';
        return '<tr' + (a.is_super ? ' style="background:var(--surface-2)"' : '') + '>' +
          '<td class="code">' + esc(a.username) + '</td>' +
          '<td>' + esc(a.name) + '</td>' +
          '<td>' + roleSel + '</td>' +
          '<td>' + st + '</td>' +
          '<td>' + totpCell + '</td>' +
          '<td class="dim num">' + esc(a.last_login_text) + '</td>' +
          '<td>' + ops + '</td></tr>';
      }).join('');
    }).catch(function () {});
  }

  function adminById(id) {
    return ADMIN_LIST.filter(function (a) { return String(a.id) === String(id); })[0];
  }

  function newAdmin() {
    modal({
      title: '新建管理员账号', okText: '创建',
      body:
        '<div class="grid g2" style="margin-bottom:12px">' +
        '<div class="field"><label>登录账号</label><input type="text" id="adUser" placeholder="字母数字，如 zhangsan" /></div>' +
        '<div class="field"><label>显示名称</label><input type="text" id="adNick" placeholder="选填" /></div>' +
        '</div>' +
        '<div class="grid g2">' +
        '<div class="field"><label>初始密码</label><input type="text" id="adPass" placeholder="至少 8 位" /></div>' +
        '<div class="field"><label>角色</label><select id="adRole">' +
        '<option value="admin">管理员（除账号管理外的全部）</option>' +
        '<option value="viewer">只读（不能做任何修改）</option>' +
        '<option value="owner">拥有者（全部权限）</option>' +
        '</select></div></div>' +
        '<p class="field" style="margin:12px 0 0"><span class="hint">' +
        '建完把账号密码给他，他打开登录页点「用账号密码登录」。</span></p>',
      onOk: function (m) {
        var body = {
          action: 'create',
          username: m.querySelector('#adUser').value.trim(),
          name: m.querySelector('#adNick').value.trim(),
          password: m.querySelector('#adPass').value,
          role: m.querySelector('#adRole').value
        };
        if (!body.username) { toast('账号不能空', 'error'); return false; }
        if (body.password.length < 8) { toast('密码至少 8 位', 'error'); return false; }
        post('/api/admin/admins', body).then(function (d) {
          if (!d.ok) { toast(d.msg || '创建失败', 'error'); return; }
          toast('已创建');
          loadAdmins();
        }).catch(function () {});
      }
    });
  }

  function setAdminRole(id, role) {
    post('/api/admin/admins', { action: 'update', id: id, role: role }).then(function (d) {
      if (!d.ok) { toast(d.msg || '修改失败', 'error'); loadAdmins(); return; }
      toast('角色已改为「' + (ROLE_TEXT[role] || role) + '」');
      loadAdmins();
    }).catch(function () {});
  }

  function toggleAdmin(id) {
    var a = adminById(id);
    if (!a) { return; }
    var next = a.status === 'active' ? 'disabled' : 'active';
    post('/api/admin/admins', { action: 'update', id: id, status: next }).then(function (d) {
      if (!d.ok) { toast(d.msg || '操作失败', 'error'); return; }
      toast(next === 'active' ? '已启用' : '已停用，他的会话随即失效');
      loadAdmins();
    }).catch(function () {});
  }

  function kickAdmin(id) {
    post('/api/admin/admins', { action: 'kick', id: id }).then(function (d) {
      if (!d.ok) { toast(d.msg || '操作失败', 'error'); return; }
      toast('已踢下线');
      loadAdmins();
    }).catch(function () {});
  }

  /* 高危操作统一走这个：必须把账号名原样敲一遍。
     前端拦一道是防手滑，服务端还会查 confirm 字段（kauth/staff.py:_confirm_ok），
     这样即使会话被别人拿走，也没法一个请求就把号删掉。 */
  function askName(opt) {
    var need = String(opt.expect || '');
    modal({
      title: opt.title, danger: true, okText: opt.okText || '确认',
      body: '<p style="margin:0 0 12px;font-size:12.5px;line-height:1.7">' +
        (opt.body || '') + '</p>' +
        '<div class="field"><label>输入账号名确认</label>' +
        '<input type="text" id="cfmName" autocomplete="off" spellcheck="false" ' +
        'placeholder="' + esc(need) + '" class="code" /></div>',
      onMount: function (m) {
        var i = m.querySelector('#cfmName');
        i.focus();
        i.onkeydown = function (e) { if (e.key === 'Enter') { m.querySelector('[data-act=ok]').click(); } };
      },
      onOk: function (m) {
        var v = (m.querySelector('#cfmName').value || '').trim();
        if (v.toLowerCase() !== need.toLowerCase()) {
          toast('账号名不对，再输一次', 'error');
          m.querySelector('#cfmName').focus();
          return false;
        }
        opt.onOk(v);
      }
    });
  }

  function resetAdminPwd(id) {
    var a = adminById(id);
    if (!a) { return; }
    modal({
      title: '重置密码', danger: true, okText: '确认重置',
      body: '<p style="margin:0 0 12px;font-size:12.5px;color:var(--text-3);line-height:1.7">' +
        '账号「' + esc(a.username) + '」的现有会话会立即失效，旧密码作废。</p>' +
        '<div class="field"><label>新密码</label>' +
        '<input type="text" id="adNewPwd" placeholder="至少 8 位" /></div>' +
        '<div class="field" style="margin-top:12px"><label>再输一次账号名确认</label>' +
        '<input type="text" id="adCfm" class="code" autocomplete="off" placeholder="' +
        esc(a.username) + '" /></div>',
      onOk: function (m) {
        var p = m.querySelector('#adNewPwd').value;
        var c = (m.querySelector('#adCfm').value || '').trim();
        if (p.length < 8) { toast('至少 8 位', 'error'); return false; }
        if (c.toLowerCase() !== String(a.username).toLowerCase()) {
          toast('账号名不对', 'error');
          m.querySelector('#adCfm').focus();
          return false;
        }
        post('/api/admin/admins',
          { action: 'reset_password', id: id, password: p, confirm: c })
          .then(function (d) {
            if (!d.ok) { toast(d.msg || '失败', 'error'); return; }
            closeModal();
            toast('已重置，把新密码告诉他');
            loadAdmins();
          }).catch(function () {});
        return false;
      }
    });
  }

  function delAdmin(id) {
    var a = adminById(id);
    if (!a) { return; }
    askName({
      title: '删除管理员账号', okText: '确认删除', expect: a.username,
      body: '确定删除「' + esc(a.username) + '」？<br>' +
        '他只是失去登录权限，之前做的操作记录仍留在「操作审计」里。',
      onOk: function (confirm) {
        post('/api/admin/admins', { action: 'delete', id: id, confirm: confirm })
          .then(function (d) {
            if (!d.ok) { toast(d.msg || '删除失败', 'error'); return; }
            toast('已删除');
            loadAdmins();
          }).catch(function () {});
      }
    });
  }

  /* 拥有者关掉别人的两步验证（对方换手机、丢手机时用） */
  function offAdminTotp(id) {
    var a = adminById(id);
    if (!a) { return; }
    askName({
      title: '关闭该账号的两步验证', okText: '确认关闭', expect: a.username,
      body: '「' + esc(a.username) + '」现在登录需要验证码。<br>' +
        '关掉后他只凭密码就能进——确认是他本人丢了手机再操作。',
      onOk: function (confirm) {
        post('/api/admin/admins',
          { action: 'totp_disable', id: id, confirm: confirm })
          .then(function (d) {
            if (!d.ok) { toast(d.msg || '操作失败', 'error'); return; }
            toast('已关闭两步验证');
            loadAdmins();
          }).catch(function () {});
      }
    });
  }

  /* ============================================================
     我自己的两步验证
     ============================================================ */
  function myTotp() {
    api('/api/admin/me/totp').then(function (d) {
      if (!d.ok) { toast(d.msg || '读取失败', 'warn'); return; }
      if (d.enabled) { totpOn(d); } else { totpIntro(); }
    }).catch(function () {});
  }

  function totpIntro() {
    modal({
      title: '开启两步验证', okText: '生成密钥',
      body: '<p style="margin:0 0 10px;font-size:12.5px;line-height:1.75">' +
        '开启后，登录这台后台除了密码还要输一个 30 秒一变的 6 位验证码。' +
        '密码泄露时，对方没有你手机上的码还是进不来。</p>' +
        '<p style="margin:0;font-size:12.5px;line-height:1.75;color:var(--text-3)">' +
        '手机装 Google Authenticator / Microsoft Authenticator / 1Password / Aegis 都行。' +
        '开始前先确认手机时间是「自动同步」。</p>',
      onOk: function () { totpSetup(); }
    });
  }

  function totpSetup() {
    post('/api/admin/me/totp', { action: 'setup' }).then(function (d) {
      if (!d.ok) { toast(d.msg || '生成失败', 'error'); return; }
      modal({
        title: '第 1 步：把密钥加进认证器', width: '540px', okText: '第 2 步：输入验证码',
        body:
          '<p style="margin:0 0 12px;font-size:12.5px;line-height:1.75">' +
          '在 App 里选「手动输入密钥」（或「输入设置密钥」），类型选「基于时间」，' +
          '把下面这串填进去。</p>' +
          '<div class="field"><label>密钥</label>' +
          '<div style="display:flex;gap:8px">' +
          '<input type="text" id="tpSec" readonly class="code" value="' +
          esc(d.secret_grouped) + '" />' +
          '<button class="btn" type="button" id="tpCopySec">复制</button></div></div>' +
          '<div class="field" style="margin-top:10px"><label>或复制链接（部分 App 支持粘贴）</label>' +
          '<div style="display:flex;gap:8px">' +
          '<input type="text" id="tpUri" readonly value="' + esc(d.uri) + '" ' +
          'style="font-family:var(--mono);font-size:11px" />' +
          '<button class="btn" type="button" id="tpCopyUri">复制</button></div></div>' +
          '<div class="field" style="margin-top:14px">' +
          '<label>App 上显示的 6 位验证码</label>' +
          '<input type="text" id="tpCode" inputmode="numeric" maxlength="6" ' +
          'autocomplete="off" placeholder="123456" class="code" /></div>' +
          '<p class="hint" style="margin:10px 0 0">输对了才会真正开启，输错不会改任何设置。</p>',
        onMount: function (m) {
          m.querySelector('#tpCopySec').onclick = function () {
            copyText(d.secret, '密钥已复制');
          };
          m.querySelector('#tpCopyUri').onclick = function () {
            copyText(d.uri, '链接已复制');
          };
          var i = m.querySelector('#tpCode');
          i.focus();
          i.onkeydown = function (e) {
            if (e.key === 'Enter') { m.querySelector('[data-act=ok]').click(); }
          };
        },
        onOk: function (m) {
          var code = (m.querySelector('#tpCode').value || '').trim();
          if (!/^\d{6}$/.test(code)) { toast('请输入 6 位数字', 'error'); return false; }
          // 失败不关窗：密钥就显示在窗里，关掉就得重新生成、App 里再加一遍
          var okBtn = m.querySelector('[data-act=ok]');
          okBtn.disabled = true;
          post('/api/admin/me/totp', { action: 'enable', code: code })
            .then(function (r) {
              if (!r.ok) {
                if (okBtn.isConnected) { okBtn.disabled = false; }
                toast(r.msg || '验证失败', 'error');
                return;
              }
              closeModal();
              totpRecovery(r.recovery || [], true);
              loadAdmins();
            }).catch(function () {
              if (okBtn.isConnected) { okBtn.disabled = false; }
            });
          return false;
        }
      });
    }).catch(function () {});
  }

  function totpRecovery(codes, fresh) {
    var cells = codes.map(function (c) {
      return '<span class="code" style="display:inline-block;padding:5px 9px;margin:0 6px 8px 0;' +
        'border:1px solid var(--border);border-radius:6px;background:var(--surface-2)">' +
        esc(c) + '</span>';
    }).join('');
    modal({
      title: fresh ? '第 3 步：存好恢复码' : '新的恢复码', width: '520px',
      okText: '我已保存', cancelText: '关闭',
      body: '<p style="margin:0 0 12px;font-size:12.5px;line-height:1.75">' +
        '这 ' + codes.length + ' 个码每个能用一次，手机丢了、重装了 App 时拿它登录。' +
        '<b>只显示这一次</b>，关掉就看不到了，请存到密码管理器或打印出来。</p>' +
        '<div style="margin:6px 0 10px">' + cells + '</div>' +
        '<button class="btn ghost sm" type="button" id="tpCopyAll">复制全部</button>' +
        '<p class="hint" style="margin:10px 0 0">用一个少一个，设置页里能看到还剩几个。</p>',
      onMount: function (m) {
        m.querySelector('#tpCopyAll').onclick = function () {
          copyText(codes.join('\n'), '恢复码已复制');
        };
      }
    });
  }

  function totpOn(d) {
    modal({
      title: '两步验证已开启', okText: '关闭两步验证', danger: true,
      body: '<p style="margin:0 0 12px;font-size:12.5px;line-height:1.75">' +
        '当前账号登录需要验证码。恢复码还剩 <b>' + (d.recovery_left || 0) + '</b> 个。</p>' +
        '<p style="margin:0;font-size:12.5px;line-height:1.75;color:var(--text-3)">' +
        '换手机：先在旧手机导出，或用恢复码登录后重新绑定。</p>' +
        '<div style="margin-top:14px"><button class="btn ghost sm" type="button" id="tpRegen">' +
        '重新生成恢复码</button></div>',
      onMount: function (m) {
        m.querySelector('#tpRegen').onclick = function () { totpRegen(); };
      },
      onOk: function () { totpOff(); }
    });
  }

  function totpRegen() {
    modal({
      title: '重新生成恢复码', okText: '确认生成',
      body: '<p style="margin:0 0 12px;font-size:12.5px;line-height:1.7">' +
        '生成后旧的恢复码全部作废。需要验证当前密码。</p>' +
        '<div class="field"><label>当前密码</label>' +
        '<input type="text" id="tpPwd" autocomplete="off" /></div>',
      onMount: function (m) { m.querySelector('#tpPwd').focus(); },
      onOk: function (m) {
        var p = m.querySelector('#tpPwd').value;
        if (!p) { toast('请输入密码', 'error'); return false; }
        var okBtn = m.querySelector('[data-act=ok]');
        okBtn.disabled = true;
        post('/api/admin/me/totp', { action: 'recovery', password: p })
          .then(function (r) {
            if (!r.ok) {
              if (okBtn.isConnected) { okBtn.disabled = false; }
              toast(r.msg || '失败', 'error');
              return;
            }
            closeModal();
            totpRecovery(r.recovery || [], false);
          }).catch(function () {
            if (okBtn.isConnected) { okBtn.disabled = false; }
          });
        return false;
      }
    });
  }

  function totpOff() {
    modal({
      title: '关闭两步验证', danger: true, okText: '确认关闭',
      body: '<p style="margin:0 0 12px;font-size:12.5px;line-height:1.7">' +
        '关掉之后只凭密码就能登录，安全性会下降。需要验证当前密码。</p>' +
        '<div class="field"><label>当前密码</label>' +
        '<input type="text" id="tpPwd2" autocomplete="off" /></div>',
      onMount: function (m) { m.querySelector('#tpPwd2').focus(); },
      onOk: function (m) {
        var p = m.querySelector('#tpPwd2').value;
        if (!p) { toast('请输入密码', 'error'); return false; }
        var okBtn = m.querySelector('[data-act=ok]');
        okBtn.disabled = true;
        post('/api/admin/me/totp', { action: 'disable', password: p })
          .then(function (r) {
            if (!r.ok) {
              if (okBtn.isConnected) { okBtn.disabled = false; }
              toast(r.msg || '失败', 'error');
              return;
            }
            closeModal();
            toast('已关闭两步验证');
            loadAdmins();
          }).catch(function () {
            if (okBtn.isConnected) { okBtn.disabled = false; }
          });
        return false;
      }
    });
  }

  window.KA = {
    go: go, copy: copyText, reveal: reveal,
    logout: logout,
    editPlan: editPlan,
    cardMenu: cardMenu, cardDetail: cardDetail, toggleRow: toggleRow, toggleAll: toggleAll,
    bulk: bulk, bulkRenew: bulkRenew, bulkDel: bulkDel, clearSel: clearSel,
    editApp: editApp, resetSecret: resetSecret, delApp: delApp,
    editPlan: editPlan, delPlan: delPlan, planType: planType,
    toggleHook: toggleHook, delHook: delHook,
    editNotice: editNotice, delNotice: delNotice
  };
  window.toggleSidebar = toggleSidebar;
  // 这三个被 HTML 直接调用（onclick="go(...)" 等），必须挂到 window，
  // 否则点击会报 "xxx is not defined"，按钮看着在、按下去没反应。
  window.go = go;
  window.editPlan = editPlan;
  window.toggleAll = toggleAll;
  window.onPlanChange = onPlanChange;
  window.onTypeChange = onTypeChange;
  window.doGen = doGen;
  window.copyGen = copyGen;
  window.downloadGen = downloadGen;
  window.debounced = debounced;
  window.loadCards = loadCards;
  window.prevCardPage = prevCardPage;
  window.nextCardPage = nextCardPage;
  window.changeCardSize = changeCardSize;
  window.jumpCardPage = jumpCardPage;
  window.logPrevPage = logPrevPage;
  window.logNextPage = logNextPage;
  window.auditPrevPage = auditPrevPage;
  window.auditNextPage = auditNextPage;
  window.dismissTokenWarn = dismissTokenWarn;
  window.exportCards = exportCards;
  window.newApp = newApp;
  window.newWebhook = newWebhook;
  window.newNotice = newNotice;
  window.loadLogs = loadLogs;
  window.loadAudits = loadAudits;
  window.loadAgents = loadAgents;
  window.newAgent = newAgent;
  window.editAgent = editAgent;
  window.editAgentQuotas = editAgentQuotas;
  window.resetAgentPwd = resetAgentPwd;
  window.toggleAgent = toggleAgent;
  window.delAgent = delAgent;
  window.saveSettings = saveSettings;
  window.doBackup = doBackup;
  window.loadBackups = loadBackups;
  window.downloadBackup = downloadBackup;
  window.cleanupLogs = cleanupLogs;
  window.loadAdmins = loadAdmins;
  window.loadWhoami = loadWhoami;
  window.newAdmin = newAdmin;
  window.setAdminRole = setAdminRole;
  window.toggleAdmin = toggleAdmin;
  window.kickAdmin = kickAdmin;
  window.resetAdminPwd = resetAdminPwd;
  window.delAdmin = delAdmin;
  window.offAdminTotp = offAdminTotp;
  window.myTotp = myTotp;
  window.rotateToken = rotateToken;

  boot();
})();
