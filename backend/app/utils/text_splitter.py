"""递归字符文本切片工具：优先按段落/句子边界切，保持语义完整"""

SEPARATORS = ["\n\n", "\n", "。", "！", "？", "!", "?", "；", ";", "，", ",", ".", " "]


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """将文本切分为若干片段。

    - chunk_size: 每片最大字符数
    - chunk_overlap: 相邻切片重叠字符数
    """
    if chunk_overlap >= chunk_size:
        chunk_overlap = max(1, chunk_size // 5)
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end >= n:
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        window = text[start:end]
        cut = end  # 找不到分隔符时硬切
        for sep in SEPARATORS:
            idx = window.rfind(sep)
            # 只在窗口后半段找，避免切片过碎
            if idx >= chunk_size // 2:
                cut = start + idx + len(sep)
                break
        chunk = text[start:cut].strip()
        if chunk:
            chunks.append(chunk)
        start = max(cut - chunk_overlap, start + 1)
    return chunks
