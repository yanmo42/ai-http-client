// ─── DOM refs ──────────────────────────────────────────────────────────────────
const sessionSelect = document.getElementById("session-select");
const newSessionBtn = document.getElementById("new-session-btn");
const newChatBtn    = document.getElementById("new-chat-btn");
const chatList      = document.getElementById("chat-list");
const chatHistory   = document.getElementById("chat-history");
const providerSel   = document.getElementById("provider");
const promptBox     = document.getElementById("prompt-input");
const sendBtn       = document.getElementById("send-btn");

// ─── State ─────────────────────────────────────────────────────────────────────
let currentSessionId = "";   // empty = Quick Chat
let currentChatId    = "";   // set when you select a persistent chat
let ephemeralMsgs    = [];




 // ─── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  
 
  loadSessions();
  promptBox.addEventListener("keydown", e => {
    if (e.key==="Enter" && !e.shiftKey){ e.preventDefault(); sendPrompt(); }
  });
  promptBox.addEventListener("input", function(){ this.style.height="auto"; this.style.height=this.scrollHeight+"px"; });
  sendBtn.addEventListener("click", sendPrompt);
  newSessionBtn.addEventListener("click", createSession);
  newChatBtn.addEventListener("click", createChat);
  sessionSelect.addEventListener("change", onSessionChange);
});

// ─── Sessions ──────────────────────────────────────────────────────────────────
async function loadSessions(){
  const res = await fetch("/sessions");
  const sessions = await res.json();
  sessionSelect.innerHTML = `<option value="">Quick Chat (ephemeral)</option>`;
  sessions.forEach(s=>{
    let o = document.createElement("option");
    o.value=s.id; o.textContent=s.name;
    sessionSelect.append(o);
  });
}

async function createSession(){
  const name = prompt("New session name?");
  if(!name) return;
  const res = await fetch("/sessions", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name})
  });
  const sess = await res.json();
  await loadSessions();
  sessionSelect.value = sess.id;
  onSessionChange();
}

async function onSessionChange(){
  currentSessionId = sessionSelect.value;
  currentChatId = "";
  chatList.innerHTML = "";
  chatHistory.innerHTML = "";
  ephemeralMsgs = [];
  if(currentSessionId){
    const res = await fetch(`/sessions/${currentSessionId}/chats`);
    const chats = await res.json();
    chats.forEach(c=> addChatToSidebar(c.id,c.title));
  }
}

// ─── Chats ─────────────────────────────────────────────────────────────────────
function addChatToSidebar(id,title){
  const li = document.createElement("li");
  li.textContent=title;
  li.addEventListener("click",()=> selectChat(id));
  chatList.append(li);
}

async function createChat(){
  if(!currentSessionId){
    ephemeralMsgs=[]; chatHistory.innerHTML="";
    return;
  }
  const res = await fetch(`/sessions/${currentSessionId}/chats`, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({title:"New Chat"})
  });
  const chat = await res.json();
  addChatToSidebar(chat.id,chat.title);
  selectChat(chat.id);
}

async function selectChat(id){
  currentChatId=id;
  chatHistory.innerHTML="";
  const res = await fetch(`/chats/${id}/messages`);
  const msgs = await res.json();
  msgs.forEach(m=> addToChatHistory(m.role,m.content));
}

// ─── Sending ───────────────────────────────────────────────────────────────────
async function sendPrompt(){
  const text = promptBox.value.trim();
  if(!text) return;
  addToChatHistory("user", text);

  let reply;
  const payload = {role:"user",content:text};
  if(currentSessionId && currentChatId){
    reply = await fetch(`/chats/${currentChatId}/messages`,{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload),
    }).then(r=>r.json());
  } else {
    ephemeralMsgs.push(payload);
    reply = await fetch("/chat/ephemeral",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({messages:ephemeralMsgs}),
    }).then(r=>r.json());
    ephemeralMsgs.push(reply);
  }

  addToChatHistory(reply.role, reply.content);
  promptBox.value=""; promptBox.style.height="auto";
  promptBox.focus();
}

// ─── Rendering ─────────────────────────────────────────────────────────────────


function normalizeMathDelimiters(s) {
  // turn "(<latex>)" into "\(<latex>\)"
  return s.replace(/\(\\([^()]+)\\\)/g, "\\($1\\)")
          // turn "[ <latex> ]" into "$$<latex>$$"
          .replace(/\[\s*([^[]+?)\s*\]/g, "$$$$$1$$$$");
}




function addToChatHistory(sender, message) {
  const div = document.createElement("div");
  div.className = `chat-entry ${sender}`;
  const safeMsg = normalizeMathDelimiters(message);
  // 1) Markdown → HTML
  //    marked.parse will turn ```code``` blocks, lists, **bold**, etc. into HTML
  div.innerHTML = marked.parse(safeMsg);

  // 2) TeX → KaTeX
  //    auto-render script gives us `renderMathInElement`
  renderMathInElement(div, {
    // these delimiters match what we loaded in index.html
    delimiters: [
      {left: "$$", right: "$$", display: true},
      {left: "\\[", right: "\\]", display: true},
      {left: "$",  right: "$",  display: false},
      {left: "\\(", right: "\\)", display: false}
    ],
    // you can tweak macros or ignoredTags here if needed
  });

  // 3) Append and scroll
  chatHistory.appendChild(div);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

