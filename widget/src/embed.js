/**
 * LeadChat Widget - 入口
 *
 * 两种嵌入配置方式（可混用，程序化 init 优先级高于 script data-* 属性）：
 *
 * 1) 旧版自动引导（继续支持）：
 *    <script src=".../leadchat.min.js" data-api="https://host" data-assistant="support"></script>
 *
 * 2) v0.5 Embed API（脚本加载前用队列，加载后直接调用）：
 *    window.LeadChat = window.LeadChat || [];
 *    LeadChat.init({
 *      api: "https://host",            // 可省略，默认按脚本地址推导
 *      assistant: "support",           // 助手 ID（或 { id: "support" }），省略=默认助手（纯问答）
 *      context: { page: "detail", order_id: "O-123" }, // 宿主业务上下文（扁平键值）
 *      theme: "dark", position: "right", title: "售后助手",
 *      welcome: "你好", icon: "https://.../icon.png"
 *    });
 *    // 运行时：LeadChat.setContext({...})、LeadChat.open()、LeadChat.close()
 */
(function boot() {
  var script = document.currentScript;
  var ownSrc = script && script.src;
  // async/defer 或动态插入执行时 document.currentScript 可能为 null，
  // 此时不能简单取"最后一个 script"（可能是无 src 的内联脚本），需按文件名特征反查自身
  if (!ownSrc) {
    var scripts = document.getElementsByTagName("script");
    for (var i = scripts.length - 1; i >= 0; i--) {
      var s = scripts[i];
      if (s.src && /leadchat(?:\.min)?\.js(?:[?#]|$)/i.test(s.src)) {
        script = s;
        ownSrc = s.src;
        break;
      }
    }
  }
  // data-api 可省略：默认从挂件脚本自身地址推导后端根地址
  //   https://chat.example.com/widget/leadchat.min.js      → https://chat.example.com
  //   https://www.example.com/leadchat/widget/leadchat.min.js → https://www.example.com/leadchat
  // 仅当后端地址与挂件脚本地址不在一起时，才需显式指定 data-api
  var scriptBase = "";
  if (ownSrc) {
    try {
      var u = new URL(ownSrc, location.href);
      scriptBase = u.origin + u.pathname.replace(/\/widget\/[^/]*$/, "").replace(/\/+$/, "");
    } catch (e) { scriptBase = ""; }
  }
  if (!scriptBase) scriptBase = location.origin;
  function dataAttr(name) {
    try { return (script && script.getAttribute && script.getAttribute(name)) || ""; }
    catch (e) { return ""; }
  }
  var api = dataAttr("data-api") || scriptBase;

  var opts = {
    api: api.replace(/\/+$/, ""),
    assistant: dataAttr("data-assistant"),
    theme: dataAttr("data-theme"),
    position: dataAttr("data-position"),
    welcome: dataAttr("data-welcome"),
    title: dataAttr("data-title"),
    icon: dataAttr("data-icon"),
    context: null
  };

  // ---- 收集脚本加载前通过 LeadChat.init(...) 排队的配置 ----
  var prev = window.LeadChat;
  var queued = [];
  if (Array.isArray(prev)) {
    for (var j = 0; j < prev.length; j++) {
      var item = prev[j];
      if (Array.isArray(item) && item[0] === "init" && item[1]) queued.push(item[1]);
      else if (item && typeof item === "object" && !Array.isArray(item)) queued.push(item);
    }
  } else if (prev && typeof prev === "object" && !prev.__lcReady) {
    // window.LeadChat = { assistant: "x", context: {...} } 形式的预配置
    queued.push(prev);
  }

  function pickAssistant(v) {
    if (!v) return "";
    if (typeof v === "string") return v;
    if (typeof v === "object") return v.id || v.assistantId || "";
    return "";
  }

  function applyInit(o, live) {
    if (!o || typeof o !== "object") return;
    if (o.api) opts.api = String(o.api).replace(/\/+$/, "");
    var aid = pickAssistant(o.assistant || o.assistantId);
    if (aid) opts.assistant = aid;
    if (o.context && typeof o.context === "object") opts.context = o.context;
    ["theme", "position", "welcome", "title", "icon"].forEach(function (k) {
      if (o[k]) opts[k] = o[k];
    });
    if (live) {
      // 挂件启动后仅 assistant/context 可热更新（外观与 API 地址启动时已定）
      LC_STATE.assistantId = opts.assistant || null;
      LC_STATE.context = opts.context || null;
    } else {
      window.__lc_opts = opts;
    }
  }

  queued.forEach(function (o) { applyInit(o, false); });
  window.__lc_opts = opts;

  // ---- 对外 Embed API ----
  window.LeadChat = {
    __lcReady: true,
    version: "0.5.2",
    init: function (o) { applyInit(o, true); },
    setContext: function (ctx) {
      opts.context = ctx && typeof ctx === "object" ? ctx : null;
      LC_STATE.context = opts.context;
    },
    getContext: function () { return LC_STATE.context; },
    open: function () { if (window.__lc_ui) __lc_ui.openWindow(); },
    close: function () { if (window.__lc_ui && __lc_ui.ui) __lc_ui.ui.root.style.display = "none"; }
  };

  function start() {
    fetchWidgetConfig(opts.api, opts.assistant).then(function (remote) {
      remote = remote || {};
      if (remote.assistant_id) {
        opts.assistant = remote.assistant_id;
        LC_STATE.assistantId = remote.assistant_id;
      }
      initWidget(opts, remote);
      initChat();
    }).catch(function () {
      initWidget(opts, {});
      initChat();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
