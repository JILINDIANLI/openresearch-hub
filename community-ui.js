(() => {
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
  }

  function inlineMarkdown(value) {
    let text = escapeHtml(value);
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    text = text.replace(/_([^_]+)_/g, '<em>$1</em>');
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return text;
  }

  function renderMarkdown(value) {
    const lines = String(value ?? '').replace(/\r\n?/g, '\n').split('\n');
    const output = [];
    let inCode = false;
    let code = [];
    for (const line of lines) {
      if (line.trim().startsWith('```')) {
        if (inCode) {
          output.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`);
          code = [];
        }
        inCode = !inCode;
        continue;
      }
      if (inCode) { code.push(line); continue; }
      if (!line.trim()) { output.push('<br>'); continue; }
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      if (heading) { output.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`); continue; }
      output.push(`<p>${inlineMarkdown(line)}</p>`);
    }
    if (inCode) output.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`);
    return output.join('');
  }

  function setBusy(button, busy) { if (button) { button.disabled = busy; button.dataset.busy = busy ? '1' : ''; } }
  async function jsonRequest(url, options = {}) {
    const response = await OpenResearchAuth.request(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '请求失败');
    return data;
  }

  window.OpenResearchCommunity = { escapeHtml, renderMarkdown, jsonRequest, setBusy };
})();
