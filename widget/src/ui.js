/**
 * LeadChat Widget - UI 渲染（Shadow DOM 隔离）
 */
function lcEscapeHtml(str) {
  return String(str == null ? "" : str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

var LC_SVG_CHAT = '<svg viewBox="0 0 24 24"><path d="M12 3C6.5 3 2 6.9 2 11.7c0 2.8 1.6 5.3 4 6.9V22l3.7-2c.7.1 1.5.2 2.3.2 5.5 0 10-3.9 10-8.7S17.5 3 12 3zm0 14.4c-.7 0-1.5-.1-2.1-.2l-2.9 1.6v-2.9C4.6 14.8 3.6 13.3 3.6 11.7 3.6 7.8 7.4 4.6 12 4.6s8.4 3.2 8.4 7.1-3.8 5.7-8.4 5.7z"/></svg>';
var LC_SVG_SEND = '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

// 浮动按钮预设图标（key 与管理后台"按钮图标"选择器一致）
var LC_ICONS = {
  chat: LC_SVG_CHAT,
  message: '<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zM7 9h10v2H7V9zm6 5H7v-2h6v2z"/></svg>',
  headset: '<svg viewBox="0 0 24 24"><path d="M12 1a9 9 0 0 0-9 9v7a3 3 0 0 0 3 3h3v-8H5v-2a7 7 0 0 1 14 0v2h-4v8h3a3 3 0 0 0 3-3v-7a9 9 0 0 0-9-9z"/></svg>',
  spark: '<svg viewBox="0 0 24 24"><path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"/></svg>',
  smile: '<svg viewBox="0 0 24 24"><path fill-rule="evenodd" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2a8 8 0 1 1 0 16 8 8 0 0 1 0-16zM8.5 9a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm7 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm-8.3 4.6a1 1 0 0 1 1.4.2 4.2 4.2 0 0 0 6.8 0 1 1 0 1 1 1.6 1.2 6.2 6.2 0 0 1-10 0 1 1 0 0 1 .2-1.4z"/></svg>'
};

// 图标值 → HTML：预设 key 直接映射；http/data:/ 以 / 开头视为图片地址
function lcFabIconHtml(icon) {
  var v = String(icon == null ? "" : icon).trim();
  if (v && (v.indexOf("http") === 0 || v.indexOf("data:") === 0 || v.charAt(0) === "/")) {
    return '<img src="' + lcEscapeHtml(v) + '" alt=""/>';
  }
  return LC_ICONS[v] || LC_ICONS.chat;
}

// 由主题色算法计算悬浮色：HSL 色相/饱和度保持不变，仅调亮度——
// 偏亮（L>42%）则加深 12%，偏暗则提亮 14%，保证悬浮态同色系且对比可感知
function lcComputeHoverColor(hex) {
  var m = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
  if (!m) return "";
  var n = parseInt(m[1], 16);
  var r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  var max = Math.max(r, g, b), min = Math.min(r, g, b);
  var h = 0, s = 0, l = (max + min) / 2;
  if (max !== min) {
    var d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = ((b - r) / d + 2) / 6;
    else h = ((r - g) / d + 4) / 6;
  }
  l = l > 0.42 ? l - 0.12 : Math.min(1, l + 0.14);
  function hue2rgb(p, q, t) {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  }
  var r2, g2, b2;
  if (s === 0) { r2 = g2 = b2 = l; }
  else {
    var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    var p = 2 * l - q;
    r2 = hue2rgb(p, q, h + 1 / 3);
    g2 = hue2rgb(p, q, h);
    b2 = hue2rgb(p, q, h - 1 / 3);
  }
  function toHex(v) {
    var x = Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16);
    return x.length === 1 ? "0" + x : x;
  }
  return "#" + toHex(r2) + toHex(g2) + toHex(b2);
}

function initWidget(opts, remote) {
  LC_API = opts.api;
  var theme = opts.theme || (remote && remote.widget_theme) || "#4F46E5";
  var position = opts.position || (remote && remote.widget_position) || "right";
  var title = opts.title || (remote && remote.company_name) || "AI 助手";
  var welcome = opts.welcome || (remote && remote.welcome_message)
    || "你好，我是这个系统的 AI 助手，可以帮你查询信息、回答问题或协助完成相关操作。";
  var popupMessage = (remote && remote.popup_message) || welcome;
  var popupDelay = parseFloat(remote && remote.auto_popup_delay);
  if (isNaN(popupDelay)) popupDelay = 3;
  var icon = opts.icon || (remote && remote.widget_icon) || "chat";
  var footerEnabled = !(remote && remote.footer_enabled === false);
  // 结构化业务字段由后端在对话中自动采集，挂件不渲染任何表单

  // 宿主元素 + Shadow DOM
  var host = document.createElement("div");
  host.id = "leadchat-root";
  var shadow = host.attachShadow({ mode: "open" });
  var style = document.createElement("style");
  style.textContent = LC_CSS;
  shadow.appendChild(style);

  var root = document.createElement("div");
  root.className = "lc-root lc-root--" + (position === "left" ? "left" : "right");
  root.style.setProperty("--lc-primary", theme);
  var hoverColor = lcComputeHoverColor(theme);
  if (hoverColor) root.style.setProperty("--lc-primary-dark", hoverColor);
  root.innerHTML =
    '<button class="lc-fab" aria-label="打开聊天">' + lcFabIconHtml(icon) + "</button>" +
    '<div class="lc-bubble" style="display:none">' +
    '  <button class="lc-bubble-close" aria-label="关闭">×</button>' +
    '  <div class="lc-bubble-text">' + lcEscapeHtml(popupMessage) + "</div>" +
    "</div>" +
    '<div class="lc-window lc-window--hidden">' +
    '  <div class="lc-header">' +
    '    <div><div class="lc-header-title">' + lcEscapeHtml(title) + "</div>" +
    '    <div class="lc-header-status"><span class="lc-dot"></span>在线</div></div>' +
    '    <button class="lc-header-close" aria-label="关闭聊天">×</button>' +
    "  </div>" +
    '  <div class="lc-messages"></div>' +
    '  <div class="lc-footer">' +
    '    <input class="lc-input" type="text" placeholder="输入您的问题..."/>' +
    '    <button class="lc-send" aria-label="发送">' + LC_SVG_SEND + "</button>" +
    "  </div>" +
    (footerEnabled
      ? '<a class="lc-brand" href="https://www.zsoftym.com" target="_blank" rel="noopener noreferrer">' +
        "Powered by 栈上月明 (zsoftym.com) <span class=\"lc-brand-sep\">|</span> " +
        '<span class="lc-brand-icp">陕ICP备2026016303号-1</span></a>'
      : "") +
    "</div>";
  shadow.appendChild(root);
  document.body.appendChild(host);

  // 元素引用
  var ui = {
    root: root,
    fab: root.querySelector(".lc-fab"),
    bubble: root.querySelector(".lc-bubble"),
    window: root.querySelector(".lc-window"),
    headerClose: root.querySelector(".lc-header-close"),
    messages: root.querySelector(".lc-messages"),
    input: root.querySelector(".lc-input"),
    sendBtn: root.querySelector(".lc-send"),
    bubbleClose: root.querySelector(".lc-bubble-close"),
    bubbleText: root.querySelector(".lc-bubble-text")
  };

  // ---------- 行为 ----------
  function scrollBottom() {
    ui.messages.scrollTop = ui.messages.scrollHeight;
  }

  function sourceNamesOf(sources) {
    var names = [];
    for (var i = 0; i < sources.length; i++) {
      var name = sources[i].filename;
      if (name && names.indexOf(name) === -1) names.push(name);
    }
    return names;
  }

  function renderSources(wrap, sources) {
    if (!sources || !sources.length) return;
    var names = sourceNamesOf(sources);
    if (!names.length) return;
    var src = document.createElement("div");
    src.className = "lc-msg-sources";
    src.textContent = "参考来源：" + names.join("、");
    wrap.appendChild(src);
  }

  function appendMessage(isUser, content, sources) {
    var wrap = document.createElement("div");
    wrap.className = "lc-msg " + (isUser ? "lc-msg--user" : "lc-msg--ai");
    var inner = document.createElement("div");
    inner.className = "lc-msg-inner";
    if (isUser) {
      // 用户消息按纯文本渲染；AI 消息走安全 Markdown 渲染器
      inner.textContent = content;
    } else {
      inner.classList.add("lc-md");
      inner.innerHTML = lcRenderMarkdown(content);
    }
    wrap.appendChild(inner);
    if (!isUser) renderSources(wrap, sources);
    ui.messages.appendChild(wrap);
    scrollBottom();
  }

  // 流式 AI 气泡：先创建空气泡，随 token 到达反复渲染增量 Markdown，结束时 setSources
  function appendAIRow() {
    var wrap = document.createElement("div");
    wrap.className = "lc-msg lc-msg--ai";
    var inner = document.createElement("div");
    inner.className = "lc-msg-inner lc-md";
    wrap.appendChild(inner);
    ui.messages.appendChild(wrap);
    return {
      el: wrap,
      setText: function (text) {
        inner.innerHTML = lcRenderMarkdown(text);
        scrollBottom();
      },
      setSources: function (sources) {
        renderSources(wrap, sources);
        scrollBottom();
      }
    };
  }

  function showTyping() {
    var el = document.createElement("div");
    el.className = "lc-msg lc-msg--ai lc-typing-row";
    el.innerHTML =
      '<div class="lc-msg-inner"><div class="lc-typing"><span></span><span></span><span></span></div></div>';
    ui.messages.appendChild(el);
    scrollBottom();
    return el;
  }

  function hideTyping(el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  function showBubble() {
    try {
      if (sessionStorage.getItem("lc_bubble_closed")) return;
    } catch (e) { /* 忽略隐私模式错误 */ }
    ui.bubble.style.display = "block";
  }
  function hideBubble(keep) {
    ui.bubble.style.display = "none";
    if (!keep) {
      try { sessionStorage.setItem("lc_bubble_closed", "1"); } catch (e) { /* 忽略 */ }
    }
  }

  function openWindow() {
    ui.window.classList.remove("lc-window--hidden");
    hideBubble();
    ui.input.focus();
    if (typeof onWindowOpened === "function") onWindowOpened();
  }
  function closeWindow() { ui.window.classList.add("lc-window--hidden"); }
  function toggleWindow() {
    if (ui.window.classList.contains("lc-window--hidden")) openWindow();
    else closeWindow();
  }

  ui.fab.addEventListener("click", toggleWindow);
  ui.headerClose.addEventListener("click", closeWindow);
  ui.bubble.addEventListener("click", openWindow);
  ui.bubbleClose.addEventListener("click", function (e) {
    e.stopPropagation();
    hideBubble();
  });

  // 到达配置秒数后自动弹出欢迎气泡（每次会话一次；delay<=0 关闭）
  if (popupDelay > 0) {
    setTimeout(showBubble, Math.round(popupDelay * 1000));
  }

  // 暴露给 chat.js
  window.__lc_ui = {
    appendMessage: appendMessage,
    appendAIRow: appendAIRow,
    showTyping: showTyping,
    hideTyping: hideTyping,
    openWindow: openWindow,
    welcome: welcome,
    ui: ui
  };
}
