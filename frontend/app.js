// Handle send button
document.getElementById('send-btn').onclick = sendPrompt;

const promptBox = document.getElementById('prompt-input');

/* ───────────── keyboard handling ─────────────
 * • Enter (without Shift)  → send
 * • Shift+Enter            → newline
 * • auto-expand textarea height
 */
promptBox.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();        // keep the newline out
    sendPrompt();
  }
});
promptBox.addEventListener('input', autoGrow);
function autoGrow() {
  this.style.height = 'auto';
  this.style.height = this.scrollHeight + 'px';
}

/* ---------- add message to history (plain text) ---------- */
function addToChatHistory(sender, message) {
  const chatHistory = document.getElementById('chat-history');
  const entry = document.createElement('div');
  entry.className = `chat-entry ${sender}`;
  entry.textContent = message;
  chatHistory.appendChild(entry);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

/* ---------- markdown / math helpers (unchanged) ---------- */
function fixMathDelimiters(mdText) {
    // Replace \[ ... \] and [ ... ] with $$ ... $$
    mdText = mdText.replace(/\\?\[([\s\S]+?)\\?\]/g, (match, math) => {
        // Avoid markdown links: [text](url)
        if (/\]\(.*?\)/.test(match)) return match;
        return `$$${math.trim()}$$`;
    });
    // Replace \( ... \) and ( ... ) with $ ... $
    mdText = mdText.replace(/\\?\(([\s\S]+?)\\?\)/g, (match, math) => {
        // Avoid normal parentheses with spaces/sentences: only replace if it's likely math (contains =, ^, _, \)
        if (!/[\=\^_\\]/.test(math)) return match;
        return `$${math.trim()}$`;
    });
    return mdText;
}

function mergeMultilineBlockMath(mdText) {
    // Join multi-line $$ ... $$ into a single line for KaTeX to parse correctly
    return mdText.replace(/\$\$([\s\S]*?)\$\$/g, function(match, inner) {
        return '$$' + inner.replace(/\n/g, ' ') + '$$';
    });
}

function renderAIResponse(mdText) {
    mdText = fixMathDelimiters(mdText);   // ADD THIS LINE!
    mdText = mergeMultilineBlockMath(mdText); 
    const chatHistory = document.getElementById('chat-history');
    const html = marked.parse(mdText);
    const entry = document.createElement('div');
    entry.className = 'chat-entry assistant ai-msg';
    entry.innerHTML = html;
    chatHistory.appendChild(entry);

    // Make sure KaTeX renders the math
    renderMathInElement(entry, {
        delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false },
            { left: "\\(", right: "\\)", display: false },
            { left: "\\[", right: "\\]", display: true }
        ]
    });

    chatHistory.scrollTop = chatHistory.scrollHeight;
}

/* ------------------ main send routine ------------------ */


async function sendPrompt() {
    const promptInput = document.getElementById('prompt-input');
    const providerSelect = document.getElementById('provider');
    const prompt = promptInput.value.trim();
    const user_id = "ian";
    if (!prompt) return;

    // Add user's message as plain text
    addToChatHistory('user', prompt);
    promptInput.value = '';

    // Fetch assistant response with user_id for context tracking
    try {
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                prompt: prompt,
                provider: providerSelect.value,
                user_id: user_id  // Use a session ID or user-specific identifier
            })
        });

        if (response.ok) {
            const data = await response.json();
            // Render the assistant's reply as Markdown + math
            console.log("AI raw response:", data.response);
            renderAIResponse(data.response);
        } else {
            renderAIResponse("**Error:** Failed to fetch response from backend.");
        }
    } catch (err) {
        renderAIResponse("**Error:** Unable to connect to backend.");
    }
}

 
