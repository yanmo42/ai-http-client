// Global state for multiple chats
let activeChatId = null;
const chats = {}; // { chatId: [ { sender, content } ] }

// Grab DOM elements and initialize
document.addEventListener('DOMContentLoaded', () => {
  window.promptBox = document.getElementById('prompt-input');
  window.chatHistoryEl = document.getElementById('chat-history');
  window.chatListEl = document.getElementById('chat-list');
  window.newChatBtn = document.getElementById('new-chat-btn');
  window.providerSelect = document.getElementById('provider');
  window.sendBtn = document.getElementById('send-btn');

  // Initialize event handlers
  newChatBtn.onclick = createNewChat;
  sendBtn.onclick = sendPrompt;

  promptBox.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  });
  promptBox.addEventListener('input', autoGrow);

  // Start with an initial chat session
  createNewChat();
});

// Create a new chat session
function createNewChat() {
  const newChatId = `chat-${Date.now()}`;
  chats[newChatId] = [];
  addChatTab(newChatId);
  setActiveChat(newChatId);
}

// Add a tab in the sidebar for a chat
function addChatTab(chatId) {
  const li = document.createElement('li');
  li.textContent = `Chat ${chatListEl.children.length + 1}`;
  li.dataset.chatId = chatId;
  li.onclick = () => setActiveChat(chatId);
  chatListEl.appendChild(li);
}

// Switch active chat and render its history
function setActiveChat(chatId) {
  activeChatId = chatId;
  Array.from(chatListEl.children).forEach(li => {
    li.classList.toggle('active', li.dataset.chatId === chatId);
  });
  chatHistoryEl.innerHTML = '';
  chats[chatId].forEach(msg => renderEntry(msg.sender, msg.content));
}

// Auto-grow textarea height
function autoGrow() {
  this.style.height = 'auto';
  this.style.height = this.scrollHeight + 'px';
}

// Add a plain text entry to the chat history
function addToChatHistory(sender, message) {
  const entry = document.createElement('div');
  entry.className = `chat-entry ${sender}`;
  entry.textContent = message;
  chatHistoryEl.appendChild(entry);
  chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

// Fix math delimiters for KaTeX
function fixMathDelimiters(mdText) {
  mdText = mdText.replace(/\\?\[([\s\S]+?)\\?\]/g, (match, math) => {
    if (/\]\(.*?\)/.test(match)) return match;
    return `$$${math.trim()}$$`;
  });
  mdText = mdText.replace(/\\?\(([\s\S]+?)\\?\)/g, (match, math) => {
    if (!/[=^_\\]/.test(math)) return match;
    return `$${math.trim()}$`;
  });
  return mdText;
}

// Merge multiline $$ blocks into single lines
function mergeMultilineBlockMath(mdText) {
  return mdText.replace(/\$\$([\s\S]*?)\$\$/g, (match, inner) =>
    `$$${inner.replace(/\n/g, ' ')}$$`
  );
}

// Render assistant Markdown + math response
function renderAIResponse(mdText) {
  mdText = fixMathDelimiters(mdText);
  mdText = mergeMultilineBlockMath(mdText);
  const html = marked.parse(mdText);
  const entry = document.createElement('div');
  entry.className = 'chat-entry assistant ai-msg';
  entry.innerHTML = html;
  chatHistoryEl.appendChild(entry);
  renderMathInElement(entry, {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '$', right: '$', display: false },
      { left: '\\(', right: '\\)', display: false },
      { left: '\\[', right: '\\]', display: true },
    ],
  });
  chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

// Dispatch to appropriate rendering function
function renderEntry(sender, content) {
  if (sender === 'assistant') {
    renderAIResponse(content);
  } else {
    addToChatHistory(sender, content);
  }
}

// Send prompt to backend with chat_id context
async function sendPrompt() {
  const prompt = promptBox.value.trim();
  if (!prompt || !activeChatId) return;
  chats[activeChatId].push({ sender: 'user', content: prompt });
  renderEntry('user', prompt);
  promptBox.value = '';

  try {
    const res = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        provider: providerSelect.value,
        user_id: 'ian',
        chat_id: activeChatId,
      }),
    });
    const data = await res.json();
    const aiMsg = data.response;
    chats[activeChatId].push({ sender: 'assistant', content: aiMsg });
    renderEntry('assistant', aiMsg);
  } catch (err) {
    const errMsg = '**Error:** Unable to connect to backend.';
    chats[activeChatId].push({ sender: 'assistant', content: errMsg });
    renderEntry('assistant', errMsg);
  }
}

