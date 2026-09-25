#!/usr/bin/env node
/**
 * LeadChat 挂件构建脚本：拼接源码为单文件 dist/leadchat.min.js
 * 无需任何 npm 依赖，直接 node build.js 运行
 */
const fs = require("fs");
const path = require("path");

const srcDir = path.join(__dirname, "src");
const outFile = path.join(__dirname, "dist", "leadchat.min.js");

function read(name) {
  return fs.readFileSync(path.join(srcDir, name), "utf8");
}

// 去除块注释（不影响字符串内容，源码中不含块注释形式的字符串）
function stripBlockComments(code) {
  return code.replace(/\/\*[\s\S]*?\*\//g, "");
}

const css = read("styles.css").trim();
const js = ["api.js", "md.js", "ui.js", "chat.js", "embed.js"]
  .map(read)
  .map(stripBlockComments)
  .join("\n");

// 版本号取自仓库根目录 VERSION 文件（唯一版本源）
function readVersion() {
  try {
    return fs.readFileSync(path.join(__dirname, "..", "VERSION"), "utf8").trim();
  } catch (e) {
    return "0.6.0";
  }
}
const VERSION = readVersion();
const banner = "/*! LeadChat Widget v" + VERSION + " | AGPL-3.0 License */";
const output =
  banner +
  "\n(function(){\n'use strict';\nvar LC_CSS = " +
  JSON.stringify(css) +
  ";\n" +
  js +
  "\n})();\n";

fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, output);
const size = (Buffer.byteLength(output) / 1024).toFixed(1);
console.log("构建完成: widget/dist/leadchat.min.js (" + size + " KB)");
