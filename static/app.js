// =========================================================================
// InquiryBot Client-Side Application Core
// =========================================================================

const API_BASE = window.location.origin;

// Session & Lead States
let currentSession = {
  sessionId: localStorage.getItem("ib_session_id") || "",
  leadId: localStorage.getItem("ib_lead_id") || null,
  leadName: localStorage.getItem("ib_lead_name") || "",
  leadPhone: localStorage.getItem("ib_lead_phone") || "",
  leadEmail: localStorage.getItem("ib_lead_email") || "",
  leadOrg: localStorage.getItem("ib_lead_org") || "",
  leadIntent: localStorage.getItem("ib_lead_intent") || "",
  startedAt: localStorage.getItem("ib_session_start") || ""
};

// Admin authentication state
let adminPassword = localStorage.getItem("ib_admin_password") || "";

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  setupUIEventListeners();
  checkExistingSession();
  checkSystemStatus();
  
  // Set default model in UI
  document.getElementById("chat-input").disabled = !currentSession.leadId;
  document.getElementById("chat-send-btn").disabled = !currentSession.leadId;
});

// ---------------------------------------------------------------------------
// Setup Event Listeners
// ---------------------------------------------------------------------------
function setupUIEventListeners() {
  // Lead Registration Form Submit
  const leadForm = document.getElementById("lead-form");
  leadForm.addEventListener("submit", handleLeadRegistration);

  // Chat message submit
  const chatForm = document.getElementById("chat-form");
  chatForm.addEventListener("submit", handleMessageSubmission);

  // Admin View toggles
  document.getElementById("link-admin-panel").addEventListener("click", (e) => {
    e.preventDefault();
    showAdminView();
  });
  
  document.getElementById("btn-back-to-chat").addEventListener("click", () => {
    showChatView();
  });

  document.getElementById("btn-admin-logout").addEventListener("click", () => {
    adminLogout();
  });

  // Admin Login submit
  document.getElementById("admin-login-form").addEventListener("submit", handleAdminLogin);

  // Admin Tab Toggles
  const tabButtons = document.querySelectorAll(".tab-btn");
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      const tabId = btn.getAttribute("data-tab");
      const panels = document.querySelectorAll(".tab-panel");
      panels.forEach(p => p.classList.remove("active"));
      document.getElementById(tabId).classList.add("active");
      
      // Load tab specific data
      loadTabContent(tabId);
    });
  });

  // active users refresh buttons
  document.getElementById("btn-refresh-active-users").addEventListener("click", () => {
    loadActiveSessions();
  });

  // CSV exports
  document.getElementById("btn-export-chat-csv").addEventListener("click", exportChatCSV);

  // Apply chat filters
  document.getElementById("btn-apply-chat-filters").addEventListener("click", () => {
    loadChatHistory();
  });

  // FAQ Training form
  document.getElementById("training-form").addEventListener("submit", handleFAQSubmission);

  // File upload drag & drop triggers
  setupFileUploadDropzone();

  // Contact support triggers
  const supportTrigger = (e) => {
    e.preventDefault();
    alert("Support request submitted. Our team will contact you shortly!");
  };
  document.getElementById("link-contact-support").addEventListener("click", supportTrigger);
  document.getElementById("btn-contact-support-2").addEventListener("click", supportTrigger);
}

// ---------------------------------------------------------------------------
// Lead Registration Flow
// ---------------------------------------------------------------------------
async function handleLeadRegistration(e) {
  e.preventDefault();
  
  const name = document.getElementById("lead-name").value.trim();
  const phone = document.getElementById("lead-phone").value.trim();
  const email = document.getElementById("lead-email").value.trim();
  const intent = document.getElementById("lead-type").value;
  const organization = document.getElementById("lead-org").value.trim();

  if (!name || !phone) {
    alert("Name and Phone Number are required fields.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/leads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, phone, email, intent, organization })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Registration failed");
    }

    const data = await res.json();
    
    // Save state
    currentSession.sessionId = data.session_id;
    currentSession.leadId = data.lead.id;
    currentSession.leadName = data.lead.name;
    currentSession.leadPhone = data.lead.phone;
    currentSession.leadEmail = data.lead.email;
    currentSession.leadOrg = data.lead.organization;
    currentSession.leadIntent = data.lead.intent;
    currentSession.startedAt = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    saveSessionToLocalStorage();
    renderSessionDetails();
    
    // Enable Chat Input
    document.getElementById("chat-input").disabled = false;
    document.getElementById("chat-send-btn").disabled = false;
    document.getElementById("chat-input").placeholder = "Ask a question about your documents...";
    
    // Welcome message updates
    const msgsContainer = document.getElementById("messages-container");
    msgsContainer.innerHTML = "";
    
    appendBotMessage(`Hello ${data.lead.name}! I have successfully started your session. How can I help you today?`);
  } catch (error) {
    alert(`Registration Error: ${error.message}`);
  }
}

function checkExistingSession() {
  if (currentSession.leadId) {
    renderSessionDetails();
    document.getElementById("chat-input").disabled = false;
    document.getElementById("chat-send-btn").disabled = false;
    document.getElementById("chat-input").placeholder = "Ask a question about your documents...";
    
    const msgsContainer = document.getElementById("messages-container");
    msgsContainer.innerHTML = "";
    appendBotMessage(`Welcome back, ${currentSession.leadName}! Your previous chat session has been resumed.`);
  }
}

function renderSessionDetails() {
  document.getElementById("details-card").style.display = "none";
  document.getElementById("session-card").style.display = "flex";
  
  document.getElementById("display-session-id").innerText = currentSession.sessionId;
  document.getElementById("display-session-start").innerText = currentSession.startedAt;
  
  // Right sidebar updates
  document.getElementById("stat-start").innerText = currentSession.startedAt;
  document.getElementById("stat-activity").innerText = "Just now";
}

function saveSessionToLocalStorage() {
  localStorage.setItem("ib_session_id", currentSession.sessionId);
  localStorage.setItem("ib_lead_id", currentSession.leadId);
  localStorage.setItem("ib_lead_name", currentSession.leadName);
  localStorage.setItem("ib_lead_phone", currentSession.leadPhone);
  localStorage.setItem("ib_lead_email", currentSession.leadEmail);
  localStorage.setItem("ib_lead_org", currentSession.leadOrg);
  localStorage.setItem("ib_lead_intent", currentSession.leadIntent);
  localStorage.setItem("ib_session_start", currentSession.startedAt);
}

// ---------------------------------------------------------------------------
// Chat Execution Flow
// ---------------------------------------------------------------------------
async function handleMessageSubmission(e) {
  e.preventDefault();
  const inputEl = document.getElementById("chat-input");
  const question = inputEl.value.trim();
  if (!question) return;

  // Render user question
  appendUserMessage(question);
  inputEl.value = "";
  
  // Show bot typing placeholder
  const placeholderId = appendTypingPlaceholder();

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSession.sessionId,
        lead_id: parseInt(currentSession.leadId),
        question: question
      })
    });

    // Remove typing placeholder
    document.getElementById(placeholderId).remove();

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Query failed");
    }

    const data = await res.json();
    appendBotMessage(data.answer, data.citations);

    // Update dynamic stats counters
    updateSessionStats(data.citations);
  } catch (error) {
    if (document.getElementById(placeholderId)) {
      document.getElementById(placeholderId).remove();
    }
    appendBotMessage(`Error: Could not retrieve answer. Details: ${error.message}. Please verify your API status settings.`);
  }
}

// Rendering message items
function appendUserMessage(text) {
  const container = document.getElementById("messages-container");
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  
  const msgRow = document.createElement("div");
  msgRow.className = "message-row user-row";
  msgRow.innerHTML = `
    <div class="message-bubble">
      <div class="bubble-text">${escapeHtml(text)}</div>
      <div class="bubble-meta">
        <span>${time}</span>
        <i class="fa-solid fa-check-double checkmark-icon"></i>
      </div>
    </div>
  `;
  container.appendChild(msgRow);
  scrollToBottom();
}

function appendBotMessage(text, citations = []) {
  const container = document.getElementById("messages-container");
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const msgId = "msg-" + Date.now();
  
  const msgRow = document.createElement("div");
  msgRow.className = "message-row bot-row";
  
  // Format markdown-like bullet points to clean list elements
  let formattedText = escapeHtml(text);
  formattedText = formattedText.replace(/\n\s*-\s*(.*)/g, '<br>&bull; $1');
  
  let citationsHtml = "";
  if (citations && citations.length > 0) {
    const pills = citations.map(c => {
      const isFaq = c.source_type === "admin_training";
      const badgeClass = isFaq ? "citation-pill admin-training-citation" : "citation-pill";
      const label = isFaq ? `Admin Training` : `${c.document_name} | page ${c.page_number || 1}`;
      return `<span class="${badgeClass}" title="${escapeHtml(c.chunk_text)}"><i class="fa-solid fa-bookmark"></i> ${label}</span>`;
    }).join("");
    
    citationsHtml = `
      <div class="bubble-citations-section">
        <span class="bubble-citations-label">Sources:</span>
        <div class="citation-pills-row">${pills}</div>
      </div>
    `;
  }

  msgRow.innerHTML = `
    <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
    <div class="message-bubble" id="${msgId}">
      <div class="bubble-author">InquiryBot</div>
      <div class="bubble-text">${formattedText}</div>
      ${citationsHtml}
      <div class="bubble-meta">
        <span>${time}</span>
      </div>
      <div class="bot-feedback-row">
        <i class="fa-regular fa-thumbs-up feedback-btn"></i>
        <i class="fa-regular fa-thumbs-down feedback-btn"></i>
      </div>
    </div>
  `;
  container.appendChild(msgRow);
  scrollToBottom();
}

function appendTypingPlaceholder() {
  const container = document.getElementById("messages-container");
  const id = "typing-" + Date.now();
  
  const msgRow = document.createElement("div");
  msgRow.className = "message-row bot-row";
  msgRow.id = id;
  msgRow.innerHTML = `
    <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
    <div class="message-bubble">
      <div class="bubble-author">InquiryBot</div>
      <div class="bubble-text">Thinking<span class="typing-dots">...</span></div>
    </div>
  `;
  container.appendChild(msgRow);
  scrollToBottom();
  return id;
}

function scrollToBottom() {
  const container = document.getElementById("messages-container");
  container.scrollTop = container.scrollHeight;
}

function updateSessionStats(citations) {
  // Update message counters
  const currentMessages = parseInt(document.getElementById("stat-messages").innerText) + 2;
  document.getElementById("stat-messages").innerText = currentMessages;

  // Add source documents in sidebar
  if (citations && citations.length > 0) {
    const list = document.getElementById("retrieved-sources-list");
    
    // Clear placeholder on first source addition
    if (list.querySelector(".empty-list-placeholder")) {
      list.innerHTML = "";
    }
    
    citations.forEach(c => {
      const item = document.createElement("div");
      item.className = "source-item-card";
      const scoreLabel = c.score ? `Score: ${c.score.toFixed(2)}` : "relevance active";
      const label = c.source_type === "admin_training" ? "Admin Q&A Override" : `Page ${c.page_number || 1}`;
      item.innerHTML = `
        <strong>${escapeHtml(c.document_name)}</strong>
        <div class="source-item-meta">
          <span>${label}</span>
          <span>${scoreLabel}</span>
        </div>
      `;
      list.appendChild(item);
    });

    const totalSources = list.children.length;
    document.getElementById("stat-sources").innerText = totalSources;
    document.getElementById("btn-view-all-sources").disabled = false;
    document.getElementById("btn-view-all-sources").innerText = `View All Sources (${totalSources})`;
  }
}

// ---------------------------------------------------------------------------
// Admin Control Layer
// ---------------------------------------------------------------------------
let activeRefreshInterval = null;

function showAdminView() {
  document.getElementById("chat-app").style.display = "none";
  document.getElementById("admin-app").style.display = "flex";
  
  if (adminPassword) {
    document.getElementById("admin-login-view").style.display = "none";
    document.getElementById("admin-dashboard-view").style.display = "block";
    loadAdminMetrics();
    loadTabContent("tab-active-users");
  } else {
    document.getElementById("admin-login-view").style.display = "flex";
    document.getElementById("admin-dashboard-view").style.display = "none";
  }
}

function showChatView() {
  document.getElementById("chat-app").style.display = "grid";
  document.getElementById("admin-app").style.display = "none";
  stopAutoRefresh();
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const password = document.getElementById("admin-password-input").value;
  
  try {
    // Attempt authentication by fetching metrics
    const res = await fetch(`${API_BASE}/api/admin/metrics`, {
      headers: { "x-admin-password": password }
    });

    if (!res.ok) throw new Error("Incorrect Password");

    // Success authentication
    adminPassword = password;
    localStorage.setItem("ib_admin_password", password);
    
    document.getElementById("admin-login-view").style.display = "none";
    document.getElementById("admin-dashboard-view").style.display = "block";
    
    loadAdminMetrics();
    loadTabContent("tab-active-users");
  } catch (error) {
    alert("Access Denied: Invalid credentials.");
  }
}

function adminLogout() {
  adminPassword = "";
  localStorage.removeItem("ib_admin_password");
  showAdminView();
}

async function loadAdminMetrics() {
  try {
    const res = await fetch(`${API_BASE}/api/admin/metrics`, {
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) return;
    
    const data = await res.json();
    document.getElementById("stat-admin-leads").innerText = data.total_leads;
    document.getElementById("stat-admin-active").innerText = data.active_users;
    document.getElementById("stat-admin-msgs").innerText = data.total_messages;
    document.getElementById("stat-admin-docs").innerText = data.trained_docs;
  } catch (err) {
    console.error("Failed to load admin metrics", err);
  }
}

function loadTabContent(tabId) {
  stopAutoRefresh();
  
  if (tabId === "tab-active-users") {
    loadActiveSessions();
    setupActiveUsersAutoRefresh();
  } else if (tabId === "tab-chat-history") {
    loadChatHistory();
  } else if (tabId === "tab-leads") {
    loadLeadsCRM();
  } else if (tabId === "tab-file-training") {
    loadIngestedDocuments();
  } else if (tabId === "tab-chat-training") {
    loadFAQTraining();
  }
}

// A: Active users tab
async function loadActiveSessions() {
  const tbody = document.getElementById("active-users-tbody");
  tbody.innerHTML = `<tr><td colspan="6" style="text-align: center;">Loading sessions...</td></tr>`;

  try {
    const res = await fetch(`${API_BASE}/api/admin/sessions`, {
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) return;

    const data = await res.json();
    tbody.innerHTML = "";
    
    if (data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center;">No active chatting sessions found.</td></tr>`;
      return;
    }

    data.forEach(user => {
      const statusClass = user.is_active ? "status-badge active" : "status-badge inactive";
      const statusLabel = user.is_active ? "🟢 Active" : "⚪ Inactive";
      
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <strong>${escapeHtml(user.name || 'Anonymous')}</strong><br>
          <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(user.phone || 'N/A')}</span>
        </td>
        <td>${escapeHtml(user.email || 'N/A')}</td>
        <td><code>${user.session_id.substring(0, 8)}...</code></td>
        <td>${user.message_count} msgs</td>
        <td><span style="font-size:12px; color: var(--text-muted);">${escapeHtml(user.latest_question || 'N/A')}</span></td>
        <td><span class="${statusClass}">${statusLabel}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger-color);">Error: ${err.message}</td></tr>`;
  }
}

function setupActiveUsersAutoRefresh() {
  const toggle = document.getElementById("admin-auto-refresh");
  toggle.onchange = () => {
    if (toggle.checked) {
      activeRefreshInterval = setInterval(loadActiveSessions, 15000);
    } else {
      stopAutoRefresh();
    }
  };
}

function stopAutoRefresh() {
  if (activeRefreshInterval) {
    clearInterval(activeRefreshInterval);
    activeRefreshInterval = null;
  }
}

// B: Chat history tab
async function loadChatHistory() {
  const container = document.getElementById("chat-history-transcripts");
  container.innerHTML = `<p style="text-align: center; padding: 20px;">Loading messages log...</p>`;

  const phone = document.getElementById("filter-chat-phone").value.trim();
  const name = document.getElementById("filter-chat-name").value.trim();
  const session = document.getElementById("filter-chat-session").value.trim();

  try {
    let url = `${API_BASE}/api/admin/leads`; // We'll group chats by leads for conversational display
    const res = await fetch(url, {
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) return;

    const data = await res.json();
    container.innerHTML = "";

    // Filter dynamic records manually or fetch
    const filteredLeads = data.filter(l => {
      if (phone && !l.phone.includes(phone)) return false;
      if (name && !l.name.toLowerCase().includes(name.toLowerCase())) return false;
      return true;
    });

    if (filteredLeads.length === 0) {
      container.innerHTML = `<p style="text-align: center; color: var(--text-muted); padding: 20px;">No conversation transcripts matched.</p>`;
      return;
    }

    filteredLeads.forEach(lead => {
      if (!lead.conversations || lead.conversations.length === 0) return;
      
      lead.conversations.forEach(conv => {
        if (session && !conv.session_id.includes(session)) return;

        const card = document.createElement("div");
        card.className = "conversation-group-card";
        
        let messagesHtml = conv.messages.map(m => {
          const isUser = m.role === 'user';
          const alignClass = isUser ? 'user-msg' : 'bot-msg';
          const icon = isUser ? '👤' : '🤖';
          return `
            <div style="padding: 10px; margin-bottom: 8px; border-radius: 6px; background-color: ${isUser ? '#f1f5f9' : '#fff'}; border: 1px solid var(--border-color);">
              <strong>${icon} ${m.role.toUpperCase()}</strong> <span style="font-size:10px; color: var(--text-muted);">${m.created_at.substring(11, 16)}</span>
              <p style="margin-top: 4px; font-size:13px;">${escapeHtml(m.content)}</p>
            </div>
          `;
        }).join("");

        card.innerHTML = `
          <div class="conv-header" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
            <span><i class="fa-regular fa-comments"></i> Session: <code>${conv.session_id.substring(0,8)}...</code> — ${escapeHtml(lead.name)} (${escapeHtml(lead.phone)})</span>
            <span style="font-size:12px; color: var(--text-muted);">${conv.last_active_at.substring(0,10)} <i class="fa-solid fa-chevron-down"></i></span>
          </div>
          <div class="conv-body-transcript" style="display: none;">
            ${messagesHtml}
          </div>
        `;
        container.appendChild(card);
      });
    });
  } catch (err) {
    container.innerHTML = `<p style="color: var(--danger-color); text-align: center;">Error loading history: ${err.message}</p>`;
  }
}

async function exportChatCSV() {
  try {
    const res = await fetch(`${API_BASE}/api/admin/leads`, {
      headers: { "x-admin-password": adminPassword }
    });
    const leads = await res.json();
    
    let csv = "Created At,Session ID,Lead Name,Phone,Email,Role,Content,Model\n";
    leads.forEach(l => {
      l.conversations.forEach(c => {
        c.messages.forEach(m => {
          const cleanContent = m.content.replace(/"/g, '""');
          csv += `"${m.created_at}","${c.session_id}","${l.name}","${l.phone}","${l.email}","${m.role}","${cleanContent}","${m.model}"\n`;
        });
      });
    });
    
    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.setAttribute("href", url);
    a.setAttribute("download", "chat_history_transcripts.csv");
    a.click();
  } catch (err) {
    alert("Export failed: " + err.message);
  }
}

// C: Leads CRM tab
async function loadLeadsCRM() {
  const container = document.getElementById("leads-crm-container");
  container.innerHTML = `<p style="text-align: center; padding: 20px;">Loading CRM leads...</p>`;

  try {
    const res = await fetch(`${API_BASE}/api/admin/leads`, {
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) return;

    const data = await res.json();
    container.innerHTML = "";

    if (data.length === 0) {
      container.innerHTML = `<p style="text-align: center; color: var(--text-muted); padding: 20px;">No leads found.</p>`;
      return;
    }

    data.forEach(lead => {
      const card = document.createElement("div");
      card.className = "lead-detail-card";
      
      const ratingClass = lead.rating.includes("Hot") ? "lead-badge-score hot" : (lead.rating.includes("Warm") ? "lead-badge-score warm" : "lead-badge-score");
      
      card.innerHTML = `
        <div class="lead-summary-row" onclick="toggleLeadExpand(${lead.id})">
          <div class="lead-summary-left">
            <strong>#${lead.id} — ${escapeHtml(lead.name)}</strong>
            <span>📱 ${escapeHtml(lead.phone)}</span>
            <span style="font-size:12px; color: var(--text-muted);">Status: <strong>${lead.status}</strong></span>
          </div>
          <div>
            <span class="${ratingClass}">Score: ${lead.score} (${lead.rating})</span>
          </div>
        </div>
        <div class="lead-expand-content" id="lead-expand-${lead.id}" style="display: none;">
          <div class="lead-details-grid">
            <div>
              <p><strong>Email:</strong> ${escapeHtml(lead.email || 'N/A')}</p>
              <p><strong>Stated Intent:</strong> ${escapeHtml(lead.intent || 'N/A')}</p>
              <p><strong>Detected Intent:</strong> ${escapeHtml(lead.detected_intent || 'N/A')}</p>
              <p><strong>Organization:</strong> ${escapeHtml(lead.organization || 'N/A')}</p>
            </div>
            <div>
              <p><strong>First Seen:</strong> ${lead.first_seen_at.substring(0,19)}</p>
              <p><strong>Last Seen:</strong> ${lead.last_seen_at.substring(0,19)}</p>
              <p><strong>Total Conversations:</strong> ${lead.total_conversations}</p>
            </div>
          </div>
          
          <div class="form-group">
            <label>Pipeline status</label>
            <select onchange="updateLeadStatus(${lead.id}, this.value)" style="max-width: 200px;">
              <option value="New" ${lead.status === 'New' ? 'selected' : ''}>New</option>
              <option value="Contacted" ${lead.status === 'Contacted' ? 'selected' : ''}>Contacted</option>
              <option value="Qualified" ${lead.status === 'Qualified' ? 'selected' : ''}>Qualified</option>
              <option value="Converted" ${lead.status === 'Converted' ? 'selected' : ''}>Converted</option>
              <option value="Closed" ${lead.status === 'Closed' ? 'selected' : ''}>Closed</option>
            </select>
          </div>
          
          <div class="form-group">
            <label>Lead Notes</label>
            <textarea id="notes-textarea-${lead.id}" rows="2" style="width: 100%;">${escapeHtml(lead.notes || '')}</textarea>
            <button onclick="saveLeadNotes(${lead.id})" class="btn btn-outline" style="margin-top: 6px; width: 120px;">Save Notes</button>
          </div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<p style="color: var(--danger-color); text-align: center;">Error loading CRM: ${err.message}</p>`;
  }
}

window.toggleLeadExpand = (id) => {
  const el = document.getElementById(`lead-expand-${id}`);
  el.style.display = el.style.display === "none" ? "block" : "none";
};

window.updateLeadStatus = async (id, status) => {
  try {
    const formData = new FormData();
    formData.append("status", status);
    
    const res = await fetch(`${API_BASE}/api/admin/leads/${id}/status`, {
      method: "POST",
      headers: { "x-admin-password": adminPassword },
      body: formData
    });
    if (!res.ok) throw new Error("Update status failed");
    alert("Pipeline status updated.");
    loadAdminMetrics();
  } catch (err) {
    alert(err.message);
  }
};

window.saveLeadNotes = async (id) => {
  const notes = document.getElementById(`notes-textarea-${id}`).value;
  try {
    const formData = new FormData();
    formData.append("notes", notes);
    
    const res = await fetch(`${API_BASE}/api/admin/leads/${id}/notes`, {
      method: "POST",
      headers: { "x-admin-password": adminPassword },
      body: formData
    });
    if (!res.ok) throw new Error("Update notes failed");
    alert("Lead notes saved.");
  } catch (err) {
    alert(err.message);
  }
};

// D: Ingested documents training tab
async function loadIngestedDocuments() {
  const tbody = document.getElementById("documents-tbody");
  tbody.innerHTML = `<tr><td colspan="5" style="text-align: center;">Loading document files...</td></tr>`;

  try {
    const res = await fetch(`${API_BASE}/api/admin/documents`, {
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) return;

    const data = await res.json();
    tbody.innerHTML = "";
    
    if (data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center;">No knowledge PDFs uploaded yet.</td></tr>`;
      return;
    }

    data.forEach(doc => {
      const statusIcon = doc.status === "ingested" ? "🟢" : "⏳";
      tbody.innerHTML += `
        <tr>
          <td><strong>${escapeHtml(doc.file_name)}</strong></td>
          <td><code>${doc.file_hash.substring(0, 10)}...</code></td>
          <td>${doc.chunk_count} chunks</td>
          <td>${statusIcon} ${doc.status}</td>
          <td>
            <button onclick="reingestDocument(${doc.id})" class="btn btn-outline" style="padding: 4px 8px; font-size:11px;">Re-ingest</button>
            <button onclick="deleteDocument(${doc.id})" class="btn btn-outline text-danger" style="padding: 4px 8px; font-size:11px;"><i class="fa-solid fa-trash"></i></button>
          </td>
        </tr>
      `;
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--danger-color);">Error: ${err.message}</td></tr>`;
  }
}

function setupFileUploadDropzone() {
  const dropzone = document.getElementById("upload-dropzone");
  const fileInput = document.getElementById("doc-file-input");
  
  dropzone.onclick = () => fileInput.click();
  
  dropzone.ondragover = (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "var(--primary-color)";
  };

  dropzone.ondragleave = () => {
    dropzone.style.borderColor = "var(--border-color)";
  };

  dropzone.ondrop = (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "var(--border-color)";
    if (e.dataTransfer.files.length > 0) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  fileInput.onchange = () => {
    if (fileInput.files.length > 0) {
      handleFileSelection(fileInput.files[0]);
    }
  };

  document.getElementById("btn-clear-upload").onclick = (e) => {
    e.stopPropagation();
    clearFileSelection();
  };

  document.getElementById("doc-upload-form").onsubmit = handleDocumentUpload;
}

let selectedUploadFile = null;

function handleFileSelection(file) {
  if (!file.name.endsWith(".pdf")) {
    alert("Only PDF files are supported.");
    return;
  }
  selectedUploadFile = file;
  document.getElementById("upload-file-info").style.display = "flex";
  document.getElementById("upload-file-info").querySelector(".file-name").innerText = file.name;
  document.getElementById("btn-submit-upload").disabled = false;
}

function clearFileSelection() {
  selectedUploadFile = null;
  document.getElementById("doc-file-input").value = "";
  document.getElementById("upload-file-info").style.display = "none";
  document.getElementById("btn-submit-upload").disabled = true;
}

async function handleDocumentUpload(e) {
  e.preventDefault();
  if (!selectedUploadFile) return;

  const btn = document.getElementById("btn-submit-upload");
  btn.innerText = "Ingesting...";
  btn.disabled = true;

  try {
    const formData = new FormData();
    formData.append("file", selectedUploadFile);

    const res = await fetch(`${API_BASE}/api/admin/documents/upload`, {
      method: "POST",
      headers: { "x-admin-password": adminPassword },
      body: formData
    });

    if (!res.ok) throw new Error("Upload process failed");
    
    const data = await res.json();
    if (data.status === "duplicate") {
      alert(`Warning: Duplicate file hash. Ingestion skipped. File matches document #${data.document.id}.`);
    } else {
      alert("Success: PDF uploaded and ingested into ChromaDB successfully.");
    }
    
    clearFileSelection();
    loadAdminMetrics();
    loadIngestedDocuments();
  } catch (err) {
    alert("Ingestion Error: " + err.message);
  } finally {
    btn.innerText = "Upload & Ingest";
    btn.disabled = false;
  }
}

window.reingestDocument = async (id) => {
  try {
    const res = await fetch(`${API_BASE}/api/admin/documents/${id}/reingest`, {
      method: "POST",
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) throw new Error("Reingest failed");
    alert("Document re-ingestion finished successfully.");
    loadIngestedDocuments();
  } catch (err) {
    alert(err.message);
  }
};

window.deleteDocument = async (id) => {
  if (!confirm("Are you sure you want to delete this document from vector database?")) return;
  try {
    const res = await fetch(`${API_BASE}/api/admin/documents/${id}`, {
      method: "DELETE",
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) throw new Error("Delete failed");
    alert("Document pruned from SQLite and ChromaDB.");
    loadAdminMetrics();
    loadIngestedDocuments();
  } catch (err) {
    alert(err.message);
  }
};

// E: FAQ chat training tab
async function loadFAQTraining() {
  const list = document.getElementById("faq-training-list");
  list.innerHTML = `<p style="text-align: center; color: var(--text-muted);">Loading FAQ overrides...</p>`;

  try {
    const res = await fetch(`${API_BASE}/api/admin/training`, {
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) return;

    const data = await res.json();
    list.innerHTML = "";
    
    if (data.length === 0) {
      list.innerHTML = `<p style="text-align: center; color: var(--text-muted); padding: 20px;">No FAQ override entries yet.</p>`;
      return;
    }

    data.forEach(entry => {
      const card = document.createElement("div");
      card.className = "faq-item-card";
      card.innerHTML = `
        <div class="faq-item-actions">
          <button onclick="deleteFAQ(${entry.id})"><i class="fa-solid fa-trash"></i></button>
        </div>
        <p style="font-size:12px; font-weight: 600; color: var(--primary-color);">Category: ${escapeHtml(entry.category || 'Uncategorized')}</p>
        <strong>Q: ${escapeHtml(entry.question)}</strong>
        <p style="font-size:13px; color: var(--text-muted);">A: ${escapeHtml(entry.answer)}</p>
      `;
      list.appendChild(card);
    });
  } catch (err) {
    list.innerHTML = `<p style="color: var(--danger-color); text-align: center;">Error: ${err.message}</p>`;
  }
}

async function handleFAQSubmission(e) {
  e.preventDefault();
  
  const question = document.getElementById("train-q").value.trim();
  const answer = document.getElementById("train-a").value.trim();
  const category = document.getElementById("train-cat").value.trim();
  const tags = document.getElementById("train-tags").value.trim();

  if (!question || !answer) {
    alert("Question and Answer are required.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/admin/training`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "x-admin-password": adminPassword
      },
      body: JSON.stringify({ question, answer, category, tags })
    });

    if (!res.ok) throw new Error("Failed to add FAQ override");

    alert("Success: FAQ entry vectorized and added successfully.");
    document.getElementById("train-q").value = "";
    document.getElementById("train-a").value = "";
    document.getElementById("train-cat").value = "";
    document.getElementById("train-tags").value = "";
    
    loadAdminMetrics();
    loadFAQTraining();
  } catch (err) {
    alert(err.message);
  }
}

window.deleteFAQ = async (id) => {
  if (!confirm("Remove this Q&A entry from vectors and database?")) return;
  try {
    const res = await fetch(`${API_BASE}/api/admin/training/${id}`, {
      method: "DELETE",
      headers: { "x-admin-password": adminPassword }
    });
    if (!res.ok) throw new Error("Delete failed");
    alert("FAQ entry purged.");
    loadAdminMetrics();
    loadFAQTraining();
  } catch (err) {
    alert(err.message);
  }
};

// ---------------------------------------------------------------------------
// Health Status Check
// ---------------------------------------------------------------------------
async function checkSystemStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) return;
    const status = await res.json();
    
    const badge = document.getElementById("badge-chroma");
    if (status.chromadb === "Connected") {
      badge.className = "status-badge active";
      badge.innerHTML = `<i class="fa-solid fa-check"></i> Connected`;
    } else {
      badge.className = "status-badge inactive";
      badge.innerHTML = `<i class="fa-solid fa-xmark"></i> Disconnected`;
    }
  } catch (err) {
    console.error("System health status call failed", err);
  }
}

// Helper: Escape HTML strings to neutralize scripts/tags
function escapeHtml(text) {
  if (!text) return "";
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}
