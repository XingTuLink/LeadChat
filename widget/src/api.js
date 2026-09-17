/**
 * LeadChat Widget - 后端 API 封装
 */
var LC_API = "";

function lcRequest(method, path, body) {
  return fetch(LC_API + path, {
    method: method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : null
  }).then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  });
}

function fetchWidgetConfig(api, assistantId) {
  var url = api + "/api/widget/config";
  if (assistantId) url += "?assistant=" + encodeURIComponent(assistantId);
  return fetch(url)
    .then(function (r) { return r.ok ? r.json() : null; })
    .catch(function () { return null; });
}

function lcChatPayload(conversationId, message, visitorId, assistantId, context) {
  var body = {
    conversation_id: conversationId || null,
    message: message,
    visitor_id: visitorId
  };
  // v0.4：指定助手 + 宿主业务上下文（均可空，旧后端/旧嵌入方式零影响）
  if (assistantId) body.assistant_id = assistantId;
  if (context && typeof context === "object") body.context = context;
  return body;
}

function apiSendChat(conversationId, message, visitorId, assistantId, context) {
  return lcRequest(
    "POST", "/api/chat/message",
    lcChatPayload(conversationId, message, visitorId, assistantId, context)
  );
}

/**
 * SSE 流式发送消息（POST + fetch ReadableStream；EventSource 不支持 POST，故手工解析）
 * handlers: { onmeta, ondelta, ondone, onerror }
 * Promise 在 done/error 事件或连接结束时 resolve；非 2xx / 不支持流式 / 网络错误时 reject，
 * 由调用方回退到 apiSendChat 非流式链路。
 */
function apiStreamChat(payload, handlers) {
  return fetch(LC_API + "/api/chat/message/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }).then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status);
    if (!r.body || !r.body.getReader) throw new Error("stream unsupported");

    var reader = r.body.getReader();
    var decoder = new TextDecoder("utf-8");
    var buffer = "";

    function dispatch(block) {
      var event = "message";
      var dataLines = [];
      block.split("\n").forEach(function (line) {
        if (line.indexOf("event:") === 0) event = line.slice(6).replace(/^\s+/, "");
        else if (line.indexOf("data:") === 0) dataLines.push(line.slice(5).replace(/^\s+/, ""));
      });
      if (!dataLines.length) return;
      var data;
      try { data = JSON.parse(dataLines.join("\n")); } catch (e) { return; }
      if (event === "meta" && handlers.onmeta) handlers.onmeta(data);
      else if (event === "delta" && handlers.ondelta) handlers.ondelta(data);
      else if (event === "done" && handlers.ondone) handlers.ondone(data);
      else if (event === "error" && handlers.onerror) handlers.onerror(data);
    }

    function pump() {
      return reader.read().then(function (chunk) {
        if (chunk.done) return;
        buffer += decoder.decode(chunk.value, { stream: true });
        var blocks = buffer.split("\n\n");
        buffer = blocks.pop();
        blocks.forEach(dispatch);
        return pump();
      });
    }
    return pump();
  });
}

function apiGetMessages(conversationId) {
  return lcRequest("GET", "/api/chat/conversations/" + conversationId + "/messages");
}
