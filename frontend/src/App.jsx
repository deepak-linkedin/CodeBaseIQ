import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Bot, Code2, FolderGit2, MessageSquare, Plus, RefreshCw, Send,
  Trash2, Database, LoaderCircle, FileCode2, Sparkles, Sun, Moon,
  PanelLeftClose, PanelLeftOpen, Search, X, Command, Pencil,
  LogOut, ExternalLink, CircleHelp,
} from "lucide-react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
const SUGGESTIONS = [
  "Explain the overall project architecture",
  "Where is the main entry point?",
  "How does the data flow through this project?",
];


function GoogleSignIn({ onSuccess, onError }) {
  const buttonRef = useRef(null);
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !buttonRef.current) return;
    let cancelled = false;
    const renderButton = () => {
      if (cancelled || !window.google?.accounts?.id || !buttonRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => onSuccess(response),
      });
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: "outline", size: "large", shape: "pill",
        text: "signin_with", width: 260,
      });
    };
    const existing = document.querySelector('script[data-codebaseiq-google="true"]');
    if (window.google?.accounts?.id) {
      renderButton();
    } else if (existing) {
      existing.addEventListener("load", renderButton, { once: true });
      existing.addEventListener("error", onError, { once: true });
    } else {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.dataset.codebaseiqGoogle = "true";
      script.onload = renderButton;
      script.onerror = onError;
      document.head.appendChild(script);
    }
    return () => { cancelled = true; };
  }, [onSuccess, onError]);
  return <div ref={buttonRef} className="google-sign-in-button" />;
}

async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem("codebaseiq-google-token");
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && GOOGLE_CLIENT_ID) {
    localStorage.removeItem("codebaseiq-google-token");
    window.dispatchEvent(new Event("codebaseiq-auth-expired"));
  }
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return data;
}

function AppContent() {
  const [token, setToken] = useState(() => localStorage.getItem("codebaseiq-google-token") || "");
  const [repositories, setRepositories] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState("");
  const [activeConversationTitle, setActiveConversationTitle] = useState("New conversation");
  const [selectedRepositoryId, setSelectedRepositoryId] = useState("");
  const [messages, setMessages] = useState([]);
  const [githubUrl, setGithubUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [indexingStatus, setIndexingStatus] = useState(null);
  const [asking, setAsking] = useState(false);
  const [showConnect, setShowConnect] = useState(true);
  const [pageError, setPageError] = useState("");
  const [notice, setNotice] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [historySearch, setHistorySearch] = useState("");
  const [theme, setTheme] = useState(() => localStorage.getItem("codebaseiq-theme") || "dark");
  const messagesEndRef = useRef(null);
  const questionRef = useRef(null);

  const signedIn = !GOOGLE_CLIENT_ID || Boolean(token);

  useEffect(() => {
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem("codebaseiq-theme", theme);
  }, [theme]);

  useEffect(() => {
    const onExpired = () => setToken("");
    window.addEventListener("codebaseiq-auth-expired", onExpired);
    return () => window.removeEventListener("codebaseiq-auth-expired", onExpired);
  }, []);

  const loadRepositories = useCallback(async () => {
    setLoadingRepos(true);
    try {
      const data = await apiRequest("/api/workspace/repositories");
      setRepositories(Array.isArray(data.repositories) ? data.repositories : []);
    } catch (error) {
      setPageError(`Could not load repositories: ${error.message}`);
    } finally {
      setLoadingRepos(false);
    }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiRequest("/api/workspace/conversations");
      setConversations(Array.isArray(data.conversations) ? data.conversations : []);
    } catch (error) {
      setPageError(`Could not load chat history: ${error.message}`);
    }
  }, []);

  useEffect(() => {
    if (signedIn) {
      loadRepositories();
      loadConversations();
    }
  }, [signedIn, loadRepositories, loadConversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  const handleLoginSuccess = useCallback((response) => {
    const credential = response?.credential || "";
    if (!credential) {
      setPageError("Google sign-in did not return a credential. Please try again.");
      return;
    }
    localStorage.setItem("codebaseiq-google-token", credential);
    setToken(credential);
    setPageError("");
  }, []);

  const handleLoginError = useCallback(() => setPageError("Google sign-in failed. Please try again."), []);

  function signOut() {
    localStorage.removeItem("codebaseiq-google-token");
    setToken("");
    setRepositories([]);
    setConversations([]);
    setMessages([]);
    setActiveConversationId("");
    setSelectedRepositoryId("");
  }

  async function startNewConversation() {
    setPageError("");
    setNotice("");
    setActiveConversationId("");
    setActiveConversationTitle("New conversation");
    setSelectedRepositoryId("");
    setMessages([]);
    setQuestion("");
    try {
      const item = await apiRequest("/api/workspace/conversations", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setActiveConversationId(item.id);
      setActiveConversationTitle(item.title || "New conversation");
      await loadConversations();
    } catch (error) {
      setPageError(`Could not start a new conversation: ${error.message}`);
    }
    questionRef.current?.focus();
  }

  async function openConversation(item) {
    setPageError("");
    try {
      const data = await apiRequest(`/api/workspace/conversations/${encodeURIComponent(item.id)}`);
      setActiveConversationId(data.id);
      setActiveConversationTitle(data.title || item.title);
      setSelectedRepositoryId(data.repository_id || "");
      setMessages(Array.isArray(data.messages) ? data.messages : []);
      setQuestion("");
      setNotice("");
    } catch (error) {
      setPageError(`Could not open conversation: ${error.message}`);
    }
  }

  async function renameConversation(item) {
    const title = window.prompt("Rename conversation", item.title || "New conversation");
    if (title === null || !title.trim()) return;
    try {
      const result = await apiRequest(`/api/workspace/conversations/${encodeURIComponent(item.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ title: title.trim() }),
      });
      if (activeConversationId === item.id) setActiveConversationTitle(result.title);
      await loadConversations();
    } catch (error) {
      setPageError(`Could not rename conversation: ${error.message}`);
    }
  }

  async function deleteConversation(item) {
    if (!window.confirm(`Delete "${item.title}" and its saved messages?`)) return;
    try {
      await apiRequest(`/api/workspace/conversations/${encodeURIComponent(item.id)}`, { method: "DELETE" });
      if (activeConversationId === item.id) {
        setActiveConversationId("");
        setActiveConversationTitle("New conversation");
        setSelectedRepositoryId("");
        setMessages([]);
      }
      await loadConversations();
    } catch (error) {
      setPageError(`Could not delete conversation: ${error.message}`);
    }
  }

  async function connectRepository(event) {
    event.preventDefault();
    if (!githubUrl.trim()) {
      setPageError("Paste a public GitHub repository URL first.");
      return;
    }
    setConnecting(true);
    setIndexingStatus({ stage: "queued", message: "Queueing repository indexing…", progress: 0 });
    setPageError("");
    setNotice("");
    try {
      const queued = await apiRequest("/api/workspace/repositories", {
        method: "POST",
        body: JSON.stringify({ github_url: githubUrl.trim() }),
      });
      const startedAt = Date.now();
      let status;
      while (Date.now() - startedAt < 15 * 60 * 1000) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        status = await apiRequest(`/api/workspace/repositories/jobs/${encodeURIComponent(queued.job_id)}`);
        setIndexingStatus(status);
        if (status.status === "completed") break;
        if (status.status === "failed") throw new Error(status.error || "Repository indexing failed.");
      }
      if (!status || status.status !== "completed") {
        throw new Error("Indexing is taking longer than 15 minutes. Check the backend terminal for the current operation before retrying.");
      }
      const result = status.result;
      setGithubUrl("");
      setNotice(`${result.name} connected — indexed ${result.chunks_indexed} code chunks across ${result.files_processed} files.`);
      await loadRepositories();
      setShowConnect(false);
    } catch (error) {
      setPageError(`Could not connect repository: ${error.message}`);
    } finally {
      setConnecting(false);
      setIndexingStatus(null);
    }
  }

  async function disconnectRepository(repo) {
    if (!window.confirm(`Disconnect ${repo.name}? Its indexed code will be removed.`)) return;
    try {
      await apiRequest(`/api/workspace/repositories/${encodeURIComponent(repo.id)}`, { method: "DELETE" });
      if (selectedRepositoryId === repo.id) setSelectedRepositoryId("");
      setNotice(`${repo.name} disconnected.`);
      await loadRepositories();
    } catch (error) {
      setPageError(`Could not disconnect repository: ${error.message}`);
    }
  }

  async function submitQuestion(rawQuestion = question) {
    const text = rawQuestion.trim();
    if (!text || asking) return;
    if (!selectedRepositoryId) {
      setPageError("Select a connected repository in the sidebar before asking a question.");
      return;
    }
    setPageError("");
    setNotice("");
    setQuestion("");
    setMessages((previous) => [...previous, { role: "user", content: text, sources: [] }]);
    setAsking(true);
    try {
      let conversationId = activeConversationId;
      if (!conversationId) {
        const created = await apiRequest("/api/workspace/conversations", {
          method: "POST",
          body: JSON.stringify({}),
        });
        conversationId = created.id;
        setActiveConversationId(conversationId);
      }
      const data = await apiRequest(`/api/workspace/conversations/${encodeURIComponent(conversationId)}/messages`, {
        method: "POST",
        body: JSON.stringify({ question: text, repository_id: selectedRepositoryId }),
      });
      setActiveConversationTitle(data.title || text.slice(0, 58));
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: data.answer || "The API returned no answer.", sources: data.sources || [] },
      ]);
      await loadConversations();
    } catch (error) {
      setPageError(`Could not get an answer: ${error.message}`);
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: "I couldn't complete that request. Check the error message and try again.", sources: [] },
      ]);
    } finally {
      setAsking(false);
    }
  }

  async function handleAsk(event) {
    event.preventDefault();
    await submitQuestion(question);
  }

  const filteredRepositories = useMemo(() => repositories.filter((repo) => {
    const q = repoSearch.trim().toLowerCase();
    return !q || repo.name.toLowerCase().includes(q) || repo.github_url.toLowerCase().includes(q);
  }), [repositories, repoSearch]);

  const filteredConversations = useMemo(() => conversations.filter((item) => {
    const q = historySearch.trim().toLowerCase();
    return !q || item.title.toLowerCase().includes(q) || (item.repository_name || "").toLowerCase().includes(q);
  }), [conversations, historySearch]);

  if (!signedIn) {
    return (
      <div className={`auth-screen theme-${theme}`}>
        <div className="auth-card">
          <div className="brand-icon auth-logo"><Code2 size={26} /></div>
          <h1>Codebase<span>IQ</span></h1>
          <p>Sign in to connect public GitHub repositories and keep your conversations private to your account.</p>
          <GoogleSignIn onSuccess={handleLoginSuccess} onError={handleLoginError} />
          {pageError && <div className="alert alert-error">{pageError}</div>}
          <small>Only public GitHub repositories are supported in this version.</small>
        </div>
      </div>
    );
  }

  return (
    <div className={`app-shell theme-${theme}`}>
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="brand">
          <div className="brand-icon"><Code2 size={22} /></div>
          {!sidebarCollapsed && <div className="brand-copy"><h1>Codebase<span>IQ</span></h1><p>Understand your code</p></div>}
          <button className="icon-button sidebar-collapse" onClick={() => setSidebarCollapsed((v) => !v)} title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>

        <button className={`new-chat-button ${sidebarCollapsed ? "icon-only" : ""}`} onClick={startNewConversation} title="New conversation">
          <Plus size={17} />{!sidebarCollapsed && <span>New conversation</span>}
        </button>

        {!sidebarCollapsed && (
          <>
            <div className="sidebar-heading"><span>CHAT HISTORY</span><button className="icon-button" onClick={loadConversations} title="Refresh chat history"><RefreshCw size={14} /></button></div>
            <div className="repo-search"><Search size={14} /><input value={historySearch} onChange={(e) => setHistorySearch(e.target.value)} placeholder="Search conversations" aria-label="Search conversations" />{historySearch && <button className="icon-button" onClick={() => setHistorySearch("")} aria-label="Clear history search"><X size={13} /></button>}</div>
            <div className="history-list">
              {filteredConversations.map((item) => (
                <div className={`history-item ${activeConversationId === item.id ? "active" : ""}`} key={item.id}>
                  <button className="history-select" onClick={() => openConversation(item)} title={item.title}>
                    <MessageSquare size={15} /><span>{item.title || "New conversation"}</span>
                  </button>
                  <div className="history-actions">
                    <button className="icon-button" onClick={() => renameConversation(item)} title="Rename conversation" aria-label="Rename conversation"><Pencil size={12} /></button>
                    <button className="icon-button" onClick={() => deleteConversation(item)} title="Delete conversation" aria-label="Delete conversation"><Trash2 size={12} /></button>
                  </div>
                </div>
              ))}
              {filteredConversations.length === 0 && <div className="empty-repositories"><MessageSquare size={20} /><p>No saved conversations yet.</p></div>}
            </div>

            <div className="sidebar-heading repository-heading"><span>CONNECTED REPOSITORIES</span><button className="icon-button" onClick={loadRepositories} title="Refresh repositories" disabled={loadingRepos}><RefreshCw size={14} className={loadingRepos ? "spin" : ""} /></button></div>
            <div className="repo-search"><Search size={14} /><input value={repoSearch} onChange={(e) => setRepoSearch(e.target.value)} placeholder="Search repositories" aria-label="Search repositories" />{repoSearch && <button className="icon-button" onClick={() => setRepoSearch("")} aria-label="Clear repository search"><X size={13} /></button>}</div>
          </>
        )}

        <div className="repository-list">
          {filteredRepositories.map((repo) => (
            <div className={`repository-item ${selectedRepositoryId === repo.id ? "active" : ""}`} key={repo.id} title={repo.name}>
              <button className="repository-select" onClick={() => setSelectedRepositoryId(repo.id)} aria-label={`Select ${repo.name}`}>
                <Code2 size={16} />{!sidebarCollapsed && <span>{repo.name}</span>}
              </button>
              {!sidebarCollapsed && <button className="delete-button" onClick={() => disconnectRepository(repo)} title="Disconnect repository" aria-label={`Disconnect ${repo.name}`}><Trash2 size={13} /></button>}
            </div>
          ))}
          {filteredRepositories.length === 0 && <div className="empty-repositories"><Database size={20} />{!sidebarCollapsed && <><p>No repositories connected.</p><span>Connect a public GitHub repository.</span></>}</div>}
        </div>

        <div className="sidebar-footer"><div className="status-dot" />{!sidebarCollapsed && <><span>{GOOGLE_CLIENT_ID ? "Signed in with Google" : "Local development mode"}</span><button className="icon-button" onClick={signOut} title="Sign out" aria-label="Sign out"><LogOut size={14} /></button></>}</div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-separator">/</span><strong>{activeConversationTitle}</strong></div>
          <div className="topbar-actions">
            <div className="backend-status"><span className="status-dot" />FastAPI</div>
            <button className="theme-toggle" onClick={() => setTheme((v) => v === "dark" ? "light" : "dark")} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}<span>{theme === "dark" ? "Light mode" : "Dark mode"}</span></button>
          </div>
        </header>

        <section className="workspace">
          <div className="workspace-heading">
            <div className="eyebrow"><Sparkles size={14} /> AI-POWERED CODE UNDERSTANDING</div>
            <h2>Talk to your <span>codebase.</span></h2>
            <p>Explore architecture, trace logic, and understand how your code works.</p>
          </div>

          {showConnect && (
            <section className="index-card">
              <div className="index-card-title"><div className="feature-icon"><Code2 size={19} /></div><div><h3>Connect a public GitHub repository</h3><p>Paste a repository URL. CodebaseIQ clones and indexes supported source files.</p></div><button className="icon-button close-connect" onClick={() => setShowConnect(false)} title="Hide connect form" aria-label="Hide connect form"><X size={15} /></button></div>
              <form className="index-form" onSubmit={connectRepository}>
                <input value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} placeholder="https://github.com/owner/repository" aria-label="Public GitHub repository URL" />
                <button type="submit" disabled={connecting}>{connecting ? <><LoaderCircle size={15} className="spin" /> Indexing…</> : <><Plus size={15} /> Connect repository</>}</button>
              </form>
              {connecting && indexingStatus && (
                <div className="index-progress" role="status" aria-live="polite">
                  <div className="index-progress-top"><LoaderCircle size={15} className="spin" /><span>{indexingStatus.message || "Preparing repository…"}</span><strong>{indexingStatus.progress || 0}%</strong></div>
                  <div className="index-progress-track"><div className="index-progress-fill" style={{ width: `${indexingStatus.progress || 0}%` }} /></div>
                  <div className="index-stage-list">
                    {["cloning", "parsing", "embedding", "indexing", "complete"].map((stage) => (
                      <span key={stage} className={(indexingStatus.stage === stage || ["parsing", "embedding", "indexing", "complete"].indexOf(indexingStatus.stage) > ["parsing", "embedding", "indexing", "complete"].indexOf(stage)) ? "done" : ""}>{stage}</span>
                    ))}
                  </div>
                </div>
              )}
              <div className="index-hint"><CircleHelp size={13} /> Public repositories only · Python, JavaScript, JSX, TypeScript, and TSX files</div>
            </section>
          )}
          {!showConnect && <button className="reopen-connect" onClick={() => setShowConnect(true)}><Plus size={14} /> Connect another repository</button>}

          {pageError && <div className="alert alert-error" role="alert"><strong>Something went wrong</strong><span>{pageError}</span><button onClick={() => setPageError("")} aria-label="Dismiss error">×</button></div>}
          {notice && <div className="alert alert-success" role="status"><span>{notice}</span><button onClick={() => setNotice("")} aria-label="Dismiss notice">×</button></div>}

          <section className="chat-panel">
            <div className="chat-header">
              <div className="chat-header-icon"><MessageSquare size={17} /></div>
              <div className="chat-header-text"><h3>{activeConversationTitle}</h3><p>{repositories.find((r) => r.id === selectedRepositoryId)?.github_url || "No repository selected — choose one from the sidebar to begin"}</p></div>
              <select className="chat-repository-select" value={selectedRepositoryId} onChange={(event) => setSelectedRepositoryId(event.target.value)} aria-label="Select repository for this conversation">
                <option value="">Select repository…</option>
                {repositories.map((repo) => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
              </select>
              {selectedRepositoryId && <span className="indexed-badge">Repository selected</span>}
            </div>

            <div className="messages">
              {messages.length === 0 && (
                <div className="welcome-message">
                  <div className="bot-avatar"><Bot size={23} /></div>
                  <h3>{selectedRepositoryId ? "What would you like to understand?" : "Start with a repository"}</h3>
                  <p>{selectedRepositoryId ? "Ask a question about the selected repository. Answers include source references when available." : "This conversation is blank by design. Connect a public GitHub repository above, then select it in the sidebar. Your new conversation will not reuse the previous repository automatically."}</p>
                  {selectedRepositoryId && <div className="suggestion-list">{SUGGESTIONS.map((suggestion) => <button key={suggestion} onClick={() => submitQuestion(suggestion)} disabled={asking}>{suggestion}<span>↗</span></button>)}</div>}
                </div>
              )}

              {messages.map((message, index) => (
                <article className={`message ${message.role}`} key={message.id || `${message.role}-${index}`}>
                  <div className="message-avatar">{message.role === "user" ? "You" : <Bot size={17} />}</div>
                  <div className="message-body"><div className="message-label">{message.role === "user" ? "You" : "Codebase assistant"}</div><div className="markdown-content"><ReactMarkdown>{message.content}</ReactMarkdown></div>
                    {message.role === "assistant" && message.sources?.length > 0 && <div className="sources"><div className="sources-heading"><FileCode2 size={14} />Source references</div>{message.sources.map((source, i) => <div className="source-item" key={`${source.file_path}-${source.start_line}-${i}`}><FileCode2 size={14} /><span className="source-path">{source.file_path}</span><span className="source-lines">L{source.start_line ?? "?"}–L{source.end_line ?? "?"}</span></div>)}</div>}
                  </div>
                </article>
              ))}
              {asking && <div className="thinking-row"><div className="message-avatar"><Bot size={17} /></div><div><div className="message-label">Codebase assistant</div><div className="thinking-indicator"><span /><span /><span />Searching code and generating answer…</div></div></div>}
              <div ref={messagesEndRef} />
            </div>

            <form className="chat-composer" onSubmit={handleAsk}>
              <textarea ref={questionRef} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={selectedRepositoryId ? "Ask anything about your code…" : "Select a connected repository first…"} rows={2} aria-label="Ask a question about your codebase" disabled={!selectedRepositoryId || asking} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form.requestSubmit(); } }} />
              <div className="composer-footer"><span><Command size={12} /> Enter to send · Shift + Enter for a new line</span><button type="submit" disabled={asking || !question.trim() || !selectedRepositoryId}>{asking ? <LoaderCircle size={16} className="spin" /> : <Send size={16} />} Ask</button></div>
            </form>
          </section>

          <footer className="workspace-footer"><span><Sparkles size={13} />Powered by hybrid retrieval and Gemini</span><span>AI can make mistakes. Verify important code details.</span></footer>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return <AppContent />;
}
