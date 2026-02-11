// ===== State =====
let isLoading = false;
let reportMarkdown = "";

// ===== DOM Elements =====
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const connectionStatus = document.getElementById("connectionStatus");
const reportModal = document.getElementById("reportModal");
const reportContent = document.getElementById("reportContent");

// ===== Initialize =====
document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    autoResizeTextarea();
});

// ===== Health Check =====
async function checkHealth() {
    const dot = connectionStatus.querySelector(".status-dot");
    const text = connectionStatus.querySelector(".status-text");

    try {
        const res = await fetch("/api/health");
        const data = await res.json();

        if (data.monday?.status === "connected") {
            dot.className = "status-dot connected";
            text.textContent = `Connected (${data.monday.boards_found} boards)`;
        } else {
            dot.className = "status-dot disconnected";
            text.textContent = "Monday.com disconnected";
        }
    } catch {
        dot.className = "status-dot disconnected";
        text.textContent = "Server offline";
    }
}

// ===== Auto-resize textarea =====
function autoResizeTextarea() {
    chatInput.addEventListener("input", () => {
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + "px";
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    });
}

// ===== Submit Handler =====
function handleSubmit(e) {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message || isLoading) return;
    sendMessage(message);
}

// ===== Send Message =====
async function sendMessage(message) {
    isLoading = true;
    sendBtn.disabled = true;

    // Add user message to chat
    addMessage(message, "user");

    // Clear input
    chatInput.value = "";
    chatInput.style.height = "auto";

    // Show typing indicator
    const typingEl = addTypingIndicator();

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });

        const data = await res.json();
        typingEl.remove();

        if (data.response) {
            addMessage(data.response, "assistant");
        } else {
            addMessage("Sorry, I couldn't generate a response. Please try again.", "assistant");
        }
    } catch (err) {
        typingEl.remove();
        addMessage("❌ Failed to connect to the server. Please check if the backend is running.", "assistant");
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

// ===== Add Message to Chat =====
function addMessage(content, role) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}-message`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";

    if (role === "user") {
        avatar.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
    } else {
        avatar.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#6C63FF" opacity="0.9"/><path d="M2 17L12 22L22 17" stroke="#00D2FF" stroke-width="2" fill="none"/><path d="M2 12L12 17L22 12" stroke="#00D2FF" stroke-width="2" fill="none"/></svg>`;
    }

    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";

    const header = document.createElement("div");
    header.className = "message-header";
    header.textContent = role === "user" ? "You" : "BI Agent";

    const body = document.createElement("div");
    body.className = "message-body";

    if (role === "assistant") {
        // Render markdown for assistant messages
        body.innerHTML = marked.parse(content);
    } else {
        body.textContent = content;
    }

    contentDiv.appendChild(header);
    contentDiv.appendChild(body);

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(contentDiv);

    chatMessages.appendChild(msgDiv);
    scrollToBottom();
}

// ===== Typing Indicator =====
function addTypingIndicator() {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message assistant-message";
    msgDiv.id = "typingIndicator";

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#6C63FF" opacity="0.9"/><path d="M2 17L12 22L22 17" stroke="#00D2FF" stroke-width="2" fill="none"/><path d="M2 12L12 17L22 12" stroke="#00D2FF" stroke-width="2" fill="none"/></svg>`;

    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";

    const header = document.createElement("div");
    header.className = "message-header";
    header.textContent = "BI Agent";

    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
    `;

    contentDiv.appendChild(header);
    contentDiv.appendChild(typing);
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(contentDiv);

    chatMessages.appendChild(msgDiv);
    scrollToBottom();

    return msgDiv;
}

// ===== Quick Query =====
function sendQuickQuery(btn) {
    const query = btn.textContent;
    chatInput.value = query;
    sendMessage(query);
}

// ===== Leadership Report =====
async function generateReport() {
    reportModal.classList.add("active");
    reportContent.innerHTML = '<div class="loading-shimmer">Generating leadership report...</div>';

    try {
        const res = await fetch("/api/report", { method: "POST" });
        const data = await res.json();

        if (data.report) {
            reportMarkdown = data.report;
            reportContent.innerHTML = marked.parse(data.report);
        } else {
            reportContent.innerHTML = "<p>❌ Failed to generate report.</p>";
        }
    } catch {
        reportContent.innerHTML = "<p>❌ Server connection failed.</p>";
    }
}

function closeReportModal() {
    reportModal.classList.remove("active");
}

function downloadReport() {
    if (!reportMarkdown) return;
    const blob = new Blob([reportMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `leadership_report_${new Date().toISOString().split("T")[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

// ===== Refresh Data =====
async function refreshData() {
    try {
        const res = await fetch("/api/refresh", { method: "POST" });
        const data = await res.json();
        addMessage(data.message || "Data refreshed.", "assistant");
        checkHealth();
    } catch {
        addMessage("❌ Failed to refresh data.", "assistant");
    }
}

// ===== View Switching =====
function switchView(view) {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    if (view === "chat") {
        document.getElementById("btnChat").classList.add("active");
    }
}

// ===== Sidebar Toggle (Mobile) =====
function toggleSidebar() {
    document.getElementById("sidebar").classList.toggle("open");
}

// ===== Scroll Helper =====
function scrollToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

// Close modal on overlay click
reportModal.addEventListener("click", (e) => {
    if (e.target === reportModal) closeReportModal();
});

// Close modal on Escape
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeReportModal();
});
