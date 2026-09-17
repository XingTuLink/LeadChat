/**
 * LeadChat Widget - 聊天核心逻辑
 */
var LC_CONVERSATION_KEY = "leadchat_conversation_id";
var LC_VISITOR_KEY = "leadchat_visitor_id";

var LC_STATE = {
  conversationId: null,
  visitorId: null,
  assistantId: null,
  context: null,
  sending: false,
  greeted: false
};

function lcUUID() {
  if (window.crypto && crypto.randomUUID) {
    try { return crypto.randomUUID(); } catch (e) { /* 降级 */ }
  }
  return "lc-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
}

function lcStorageGet(key) {
  try { return localStorage.getItem(key); } catch (e) { return null; }
}
function lcStorageSet(key, value) {
  try { localStorage.setItem(key, value); } catch (e) { /* 忽略 */ }
}

function onWindowOpened() {
  // 仅在首次打开窗口时执行（幂等守卫）
  if (LC_STATE.greeted) return;
  LC_STATE.greeted = true;
  var welcome = (__lc_ui && __lc_ui.welcome) || "您好，请问有什么可以帮您吗？";

  if (!LC_STATE.conversationId) {
    // 全新访客：直接展示欢迎语
    __lc_ui.appendMessage(false, welcome);
    return;
  }
  apiGetMessages(LC_STATE.conversationId)
    .then(function (res) {
      var msgs = res.messages || [];
      if (!msgs.length) {
        // 新会话无历史：第一条自动显示欢迎语
        __lc_ui.appendMessage(false, welcome);
      } else {
        msgs.forEach(function (m) {
          if (m.role === "user") __lc_ui.appendMessage(true, m.content);
          else if (m.role === "assistant") __lc_ui.appendMessage(false, m.content, m.sources || []);
        });
      }
    })
    .catch(function () { __lc_ui.appendMessage(false, welcome); });
}

function lcSendMessage() {
  var ui = __lc_ui.ui;
  var text = ui.input.value.trim();
  if (!text || LC_STATE.sending) return;
  LC_STATE.sending = true;
  ui.sendBtn.disabled = true;
  ui.input.value = "";

  __lc_ui.appendMessage(true, text);
  var typing = __lc_ui.showTyping();
  var typingVisible = true;
  var streamRow = null;
  var acc = "";
  var settled = false;

  function hideTypingOnce() {
    if (typingVisible) { __lc_ui.hideTyping(typing); typingVisible = false; }
  }
  function showTypingAgain() {
    if (!typingVisible) { typing = __lc_ui.showTyping(); typingVisible = true; }
  }
  function rememberConv(res) {
    if (res.conversation_id) {
      LC_STATE.conversationId = res.conversation_id;
      lcStorageSet(LC_CONVERSATION_KEY, res.conversation_id);
    }
    if (res.assistant_id) LC_STATE.assistantId = res.assistant_id;
  }
  // 非流式兜底：旧后端 / 代理不支持 SSE / 流式中途断开 时走原链路
  function fallbackNonStream() {
    return apiSendChat(
      LC_STATE.conversationId, text, LC_STATE.visitorId, LC_STATE.assistantId, LC_STATE.context
    )
      .then(function (res) {
        rememberConv(res);
        // 业务数据在对话中由 AI 自动收集，无需弹窗表单；收集成功时回复中已含确认话术
        __lc_ui.appendMessage(false, res.reply, res.sources || []);
      })
      .catch(function () {
        __lc_ui.appendMessage(false, "网络异常，请稍后再试。");
      });
  }

  var payload = lcChatPayload(
    LC_STATE.conversationId, text, LC_STATE.visitorId, LC_STATE.assistantId, LC_STATE.context
  );
  apiStreamChat(payload, {
    onmeta: function (d) { rememberConv(d); },
    ondelta: function (d) {
      if (!streamRow) {
        hideTypingOnce();
        streamRow = __lc_ui.appendAIRow();
      }
      acc += d.content || "";
      streamRow.setText(acc);
    },
    ondone: function (d) {
      settled = true;
      hideTypingOnce();
      rememberConv(d);
      if (streamRow) {
        streamRow.setText(d.reply || acc);
        streamRow.setSources(d.sources || []);
      } else {
        // 极短回复可能整段在一个 chunk 后直接 done，也可能无 delta
        __lc_ui.appendMessage(false, d.reply || "", d.sources || []);
      }
    },
    onerror: function () { throw new Error("stream error event"); }
  })
    .then(function () {
      // 连接正常结束但没收到 done（被代理截断等）：按失败处理，回退非流式
      if (!settled) throw new Error("stream ended without done");
    })
    .catch(function () {
      if (settled) return;
      if (streamRow && streamRow.el.parentNode) {
        streamRow.el.parentNode.removeChild(streamRow.el);
      }
      streamRow = null;
      acc = "";
      showTypingAgain();
      return fallbackNonStream().then(function () { hideTypingOnce(); });
    })
    .then(function () {
      hideTypingOnce();
      LC_STATE.sending = false;
      ui.sendBtn.disabled = false;
      ui.input.focus();
    });
}

function initChat() {
  LC_STATE.conversationId = lcStorageGet(LC_CONVERSATION_KEY);
  LC_STATE.visitorId = lcStorageGet(LC_VISITOR_KEY);
  // v0.4：嵌入初始化传入的助手 ID 与宿主业务上下文
  var bootOpts = window.__lc_opts || {};
  LC_STATE.assistantId = bootOpts.assistant || null;
  LC_STATE.context = bootOpts.context && typeof bootOpts.context === "object" ? bootOpts.context : null;
  if (!LC_STATE.visitorId) {
    LC_STATE.visitorId = lcUUID();
    lcStorageSet(LC_VISITOR_KEY, LC_STATE.visitorId);
  }

  var ui = __lc_ui.ui;
  ui.sendBtn.addEventListener("click", lcSendMessage);
  ui.input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      lcSendMessage();
    }
  });
}
