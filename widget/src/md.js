/**
 * LeadChat Widget - 轻量、安全的 Markdown 渲染器（零依赖）
 *
 * 设计原则：
 * 1. 先对原文整体 HTML 转义，再做格式化——LLM 输出中的 <script> 等不会被执行（防 XSS）；
 * 2. 代码块/行内代码先抽取为占位符，避免内部的 ** # 等被二次格式化；
 * 3. 链接协议白名单（http/https/mailto/站内路径），javascript: 一律不产出可点击链接；
 * 4. 输出紧凑 HTML（块级元素之间不插裸换行），配合 CSS .lc-md 的 white-space:normal 排版。
 */

function lcMdEscape(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function lcMdSafeUrl(u) {
  var v = String(u == null ? "" : u).trim();
  if (/^(?:https?:\/\/|mailto:|\/(?!\/))/i.test(v)) return v.replace(/"/g, "%22");
  return null;
}

function lcRenderMarkdown(src) {
  var TOKEN_B = "\u0001";
  var TOKEN_I = "\u0002";
  var text = lcMdEscape(src).replace(/\r\n?/g, "\n");

  // 1. 抽取围栏代码块 ```lang\n...```
  var blockCodes = [];
  text = text.replace(/```[^\n`]*\n?([\s\S]*?)```/g, function (_all, code) {
    var html =
      '<pre class="lc-md-pre"><code>' +
      String(code).replace(/\n$/, "") +
      "</code></pre>";
    var idx = blockCodes.push(html) - 1;
    return "\n" + TOKEN_B + idx + TOKEN_I + "\n";
  });

  // 2. 行内语法（在非代码内容上执行）
  function inline(s) {
    var inlineCodes = [];
    s = s.replace(/`([^`\n]+?)`/g, function (_all, code) {
      var idx = inlineCodes.push('<code class="lc-md-code">' + code + "</code>") - 1;
      return TOKEN_B + "I" + idx + TOKEN_I;
    });
    // 链接 [文本](URL "可选标题")，URL 必须在白名单协议内
    s = s.replace(
      /\[([^\]]+)\]\(([^)\s("']+)(?:\s+(?:&quot;|")[^&"]*?(?:&quot;|"))?\)/g,
      function (_all, label, url) {
        var safe = lcMdSafeUrl(url);
        return safe
          ? '<a href="' + safe + '" target="_blank" rel="noopener noreferrer">' + label + "</a>"
          : label;
      }
    );
    // 加粗、删除线、斜体（保守匹配，避免误伤 2*3、a_b_c 之类）
    s = s
      .replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+?)__/g, "<strong>$1</strong>")
      .replace(/~~([^~]+?)~~/g, "<del>$1</del>")
      .replace(/(^|[\s(（>])\*([^*\n]+?)\*(?=[\s)）。，！？、：：.!?,:]|$)/g, "$1<em>$2</em>")
      .replace(/(^|[\s(（>])_([^_\n]+?)_(?=[\s)）。，！？、：：.!?,:]|$)/g, "$1<em>$2</em>");
    return s.replace(new RegExp(TOKEN_B + "I(\\d+)" + TOKEN_I, "g"), function (_all, i) {
      return inlineCodes[i];
    });
  }

  // 3. 块级解析
  var lines = text.split("\n");
  var out = [];
  var i = 0;

  function isListMarker(line) {
    return /^\s{0,3}(?:[-*+]|\d+[.)])\s+/.test(line);
  }
  function listTagName(line) {
    return /^\s{0,3}\d+[.)]\s+/.test(line) ? "ol" : "ul";
  }

  while (i < lines.length) {
    var line = lines[i];

    // 代码块占位符独占一行
    var bm = line.match(new RegExp("^" + TOKEN_B + "(\\d+)" + TOKEN_I + "$"));
    if (bm) {
      out.push(blockCodes[Number(bm[1])]);
      i++;
      continue;
    }
    if (!line.trim()) { i++; continue; }

    // 标题
    var hm = line.match(/^(#{1,6})\s+(.*)$/);
    if (hm) {
      var level = Math.min(hm[1].length + 2, 6); // 挂件里 # → h3，避免字号过大
      out.push("<h" + level + ">" + inline(hm[2].trim()) + "</h" + level + ">");
      i++;
      continue;
    }

    // 分隔线
    if (/^\s*(?:-\s*){3,}$|^\s*(?:\*\s*){3,}$|^\s*(?:_\s*){3,}$/.test(line)) {
      out.push("<hr/>");
      i++;
      continue;
    }

    // 引用块（连续 > 行）
    if (/^\s*&gt;\s?/.test(line)) {
      var quote = [];
      while (i < lines.length && /^\s*&gt;\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*&gt;\s?/, ""));
        i++;
      }
      out.push("<blockquote>" + inline(quote.join("<br/>")) + "</blockquote>");
      continue;
    }

    // 表格（表头行 + |---| 分隔行）
    if (line.indexOf("|") !== -1 && i + 1 < lines.length &&
        /^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$/.test(lines[i + 1])) {
      function cells(row) {
        var t = row.trim();
        if (t.charAt(0) === "|") t = t.slice(1);
        if (t.charAt(t.length - 1) === "|") t = t.slice(0, -1);
        return t.split("|").map(function (c) { return c.trim(); });
      }
      var head = cells(line);
      var aligns = cells(lines[i + 1]).map(function (c) {
        var l = c.charAt(0) === ":";
        var r = c.charAt(c.length - 1) === ":";
        return l && r ? "center" : (r ? "right" : (l ? "left" : ""));
      });
      var thead = "<tr>" + head.map(function (c, k) {
        var st = aligns[k] ? ' style="text-align:' + aligns[k] + '"' : "";
        return "<th" + st + ">" + inline(c) + "</th>";
      }).join("") + "</tr>";
      var tb = [];
      i += 2;
      while (i < lines.length && lines[i].indexOf("|") !== -1 && lines[i].trim()) {
        (function (row) {
          tb.push("<tr>" + cells(row).map(function (c, k) {
            var st = aligns[k] ? ' style="text-align:' + aligns[k] + '"' : "";
            return "<td" + st + ">" + inline(c) + "</td>";
          }).join("") + "</tr>");
        })(lines[i]);
        i++;
      }
      out.push('<div class="lc-md-table"><table><thead>' + thead + "</thead><tbody>" +
        tb.join("") + "</tbody></table></div>");
      continue;
    }

    // 列表（连续列表行；缩进 2~4 空格视为一层嵌套）
    if (isListMarker(line)) {
      var tag = listTagName(line);
      var items = [];
      while (i < lines.length && isListMarker(lines[i])) {
        var cur = lines[i];
        var nested = /^\s{2,}/.test(cur);
        var content = cur.replace(/^\s{0,3}(?:[-*+]|\d+[.)])\s+/, "");
        if (nested && items.length) {
          items[items.length - 1].push(inline(content));
        } else {
          items.push([inline(content)]);
        }
        i++;
      }
      out.push("<" + tag + ">" + items.map(function (parts) {
        return "<li>" + parts.join("<br/>") + "</li>";
      }).join("") + "</" + tag + ">");
      continue;
    }

    // 普通段落：连续非空、非特殊行合并，段内换行用 <br/>
    var para = [];
    while (i < lines.length && lines[i].trim() &&
           !/^(#{1,6})\s+/.test(lines[i]) &&
           !/^\s*&gt;/.test(lines[i]) && !isListMarker(lines[i])) {
      var pl = lines[i];
      var pm = pl.match(new RegExp("^" + TOKEN_B + "(\\d+)" + TOKEN_I + "$"));
      if (pm) break;
      if (pl.indexOf("|") !== -1 && i + 1 < lines.length &&
          /^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$/.test(lines[i + 1])) break;
      para.push(pl.trim());
      i++;
    }
    if (para.length) out.push("<p>" + inline(para.join("<br/>")) + "</p>");
  }

  // 4. 还回围栏代码块
  var html = out.join("");
  return html.replace(new RegExp(TOKEN_B + "(\\d+)" + TOKEN_I, "g"), function (_all, idx) {
    return blockCodes[Number(idx)] || "";
  });
}
