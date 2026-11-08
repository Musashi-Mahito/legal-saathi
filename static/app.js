"use strict";

(function () {
  const FLAG_TEXT = {
    unverified_reference_removed:
      "We removed a legal reference we could not verify. Please check with a lawyer.",
    unverified_number: "Some numbers in this answer could not be checked against your details.",
    possible_prompt_injection:
      "This document contains instructions aimed at an AI. We ignored them.",
    partial_result: "Only part of the document could be processed. Please try again later.",
    llm_failure: "The assistant is having trouble right now. Please try again.",
    unknown_kb_tag: "We removed a source tag that is not in our knowledge base.",
  };

  const EXAMPLES = [
    "My landlord is not returning my Rs 60,000 security deposit",
    "My refund never came after I returned the product",
    "Is the arbitration clause in my agreement a problem?",
    "I was charged for a service that was never delivered",
  ];

  const WELCOME =
    "**Namaste.** I help with two kinds of problems:\n" +
    "- **Tenant deposit** - your landlord will not return the deposit, or is deducting too much\n" +
    "- **Consumer refund** - refund never came, defective product, service not delivered\n" +
    "\n" +
    "Write in English, Hindi or Hinglish. Tell me what happened in your own words and I will " +
    "explain where you stand and what to do next. You can also upload your agreement, invoice " +
    "or notice and I will summarise it.";

  const state = {
    sessionId: null,
    kb: new Map(),
    documents: [],
    domain: "unknown",
    busy: false,
  };

  const els = {
    messages: document.getElementById("messages"),
    suggestions: document.getElementById("suggestions"),
    typing: document.getElementById("typing"),
    chatForm: document.getElementById("chat-form"),
    chatInput: document.getElementById("chat-input"),
    sendButton: document.getElementById("send-button"),
    banner: document.getElementById("banner"),
    bannerTitle: document.getElementById("banner-title"),
    bannerReasons: document.getElementById("banner-reasons"),
    bannerResources: document.getElementById("banner-resources"),
    errorBox: document.getElementById("error-box"),
    errorText: document.getElementById("error-text"),
    errorClose: document.getElementById("error-close"),
    uploadForm: document.getElementById("upload-form"),
    fileInput: document.getElementById("file-input"),
    uploadButton: document.getElementById("upload-button"),
    documentList: document.getElementById("document-list"),
    documentsEmpty: document.getElementById("documents-empty"),
    summaryDoc: document.getElementById("summary-doc"),
    summarizeButton: document.getElementById("summarize-button"),
    summaryOutput: document.getElementById("summary-output"),
    timelineButton: document.getElementById("timeline-button"),
    timelineOutput: document.getElementById("timeline-output"),
    noticeButton: document.getElementById("notice-button"),
    noticeHint: document.getElementById("notice-hint"),
    noticeOutput: document.getElementById("notice-output"),
    caseOutput: document.getElementById("case-output"),
  };

  const tabs = Array.from(document.querySelectorAll(".tab"));

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function jsonRequest(payload) {
    return {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    };
  }

  async function api(path, options) {
    const response = await fetch(path, options);
    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }
    if (!response.ok) {
      const message =
        data && data.error && data.error.message
          ? data.error.message
          : "Request failed (" + response.status + ").";
      throw new Error(message);
    }
    return data || {};
  }

  function showError(message) {
    els.errorText.textContent = message;
    els.errorBox.hidden = false;
  }

  function clearError() {
    els.errorBox.hidden = true;
    els.errorText.textContent = "";
  }

  function setChatBusy(value) {
    state.busy = value;
    els.chatInput.disabled = value;
    els.sendButton.disabled = value;
    els.typing.hidden = !value;
  }

  function setButtonBusy(button, busy, label) {
    button.disabled = busy;
    button.textContent = busy ? "Working…" : label;
  }

  function kbChip(id) {
    const entry = state.kb.get(id);
    const chip = el("span", "chip", entry ? "Source: " + entry.title : "Source: " + id);
    if (!entry) {
      chip.classList.add("unverified");
      chip.title = "This source tag is not in our knowledge base.";
    } else if (!entry.verified) {
      chip.classList.add("unverified");
      chip.title = "This knowledge base entry has not been verified yet.";
    }
    return chip;
  }

  const INLINE_TOKEN_RE = /(\[KB:[A-Za-z0-9_\-]+\]|\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\n]+\*)/g;
  const LIST_ITEM_RE = /^\s*(?:[-*\u2022]|\d+[.)])\s+/;

  function appendInline(parent, text) {
    const parts = String(text || "").split(INLINE_TOKEN_RE);
    parts.forEach(function (part, index) {
      if (!part) return;
      const kbMatch = /^\[KB:([A-Za-z0-9_\-]+)\]$/.exec(part);
      if (kbMatch) {
        const chip = kbChip(kbMatch[1]);
        const next = parts[index + 1];
        if (next && /^[.,;:!?]/.test(next)) {
          const punct = next.charAt(0);
          if (chip.firstChild && chip.firstChild.nodeType === 3) {
            chip.firstChild.nodeValue += punct;
          } else {
            chip.appendChild(document.createTextNode(punct));
          }
          parts[index + 1] = next.slice(1);
        }
        parent.appendChild(chip);
        return;
      }
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        parent.appendChild(el("strong", null, part.slice(2, -2)));
        return;
      }
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
        parent.appendChild(el("code", null, part.slice(1, -1)));
        return;
      }
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        parent.appendChild(el("em", null, part.slice(1, -1)));
        return;
      }
      parent.appendChild(document.createTextNode(part));
    });
  }

  function appendMarkdown(container, text) {
    let list = null;
    let listTag = null;
    String(text || "")
      .split("\n")
      .forEach(function (rawLine) {
        const line = rawLine.replace(/\s+$/, "");
        if (!line.trim()) {
          list = null;
          listTag = null;
          return;
        }
        const itemMatch = LIST_ITEM_RE.exec(line);
        if (itemMatch) {
          const tag = /\d/.test(itemMatch[0]) ? "ol" : "ul";
          if (!list || listTag !== tag) {
            list = document.createElement(tag);
            container.appendChild(list);
            listTag = tag;
          }
          const body = line.replace(LIST_ITEM_RE, "");
          const pieces = body
            .split(/\s+(?=\d{1,2}[.)]\s)/)
            .map(function (piece, index) {
              return index === 0 ? piece : piece.replace(/^\d{1,2}[.)]\s+/, "");
            });
          pieces.forEach(function (piece) {
            const text = piece.trim();
            if (!text) return;
            const li = document.createElement("li");
            appendInline(li, text);
            list.appendChild(li);
          });
          return;
        }
        list = null;
        listTag = null;
        const heading = /^#{1,6}\s+(.*)$/.exec(line);
        const paragraph = el("p", heading ? "md-heading" : null);
        appendInline(paragraph, heading ? heading[1] : line);
        container.appendChild(paragraph);
      });
  }

  function addFlagNotes(container, flags) {
    (flags || []).forEach(function (flag) {
      const text = FLAG_TEXT[flag];
      if (text) container.appendChild(el("span", "flag-note", text));
    });
  }

  function addMessage(role, text) {
    const wrapper = el("div", "message " + role);
    if (role === "assistant") {
      appendMarkdown(wrapper, text);
    } else {
      wrapper.appendChild(document.createTextNode(String(text || "")));
    }
    els.messages.appendChild(wrapper);
    els.messages.scrollTop = els.messages.scrollHeight;
    return wrapper;
  }

  function addAssistantMessage(text, flags) {
    const wrapper = addMessage("assistant", text);
    addFlagNotes(wrapper, flags);
    return wrapper;
  }

  function renderEscalation(escalation) {
    if (!escalation || escalation.level === "none") {
      els.banner.hidden = true;
      return;
    }
    const urgent = escalation.level === "urgent";
    els.banner.hidden = false;
    els.banner.className = "banner " + (urgent ? "urgent" : "advise");
    els.bannerTitle.textContent = urgent
      ? "Please talk to a lawyer now"
      : "It is worth checking this with a lawyer";
    els.bannerReasons.replaceChildren.apply(
      els.bannerReasons,
      (escalation.reasons || []).map(function (reason) {
        return el("li", null, reason);
      })
    );
    els.bannerResources.replaceChildren.apply(
      els.bannerResources,
      (escalation.resources || []).map(function (resource) {
        return el("li", null, resource);
      })
    );
  }

  function activateTab(name, focus) {
    tabs.forEach(function (tab) {
      const selected = tab.dataset.panel === name;
      tab.setAttribute("aria-selected", selected ? "true" : "false");
      tab.tabIndex = selected ? 0 : -1;
      const panel = document.getElementById("panel-" + tab.dataset.panel);
      if (panel) panel.hidden = !selected;
    });
    if (focus) {
      const active = tabs.find(function (tab) {
        return tab.dataset.panel === name;
      });
      if (active) active.focus();
    }
  }

  function suggestionsContainer() {
    if (els.suggestions) return els.suggestions;
    const container = el("div", "suggestions");
    container.id = "suggestions";
    container.setAttribute("aria-label", "Example messages");
    const anchor = els.typing && els.typing.parentNode ? els.typing : els.chatForm;
    anchor.parentNode.insertBefore(container, anchor);
    els.suggestions = container;
    return container;
  }

  function renderSuggestions() {
    const box = suggestionsContainer();
    box.replaceChildren();
    EXAMPLES.forEach(function (example) {
      const button = el("button", "suggestion", example);
      button.type = "button";
      button.addEventListener("click", function () {
        els.chatInput.value = example;
        els.chatForm.requestSubmit();
      });
      box.appendChild(button);
    });
  }

  function clearSuggestions() {
    if (!els.suggestions) return;
    els.suggestions.replaceChildren();
  }

  async function sendMessage(event) {
    event.preventDefault();
    const value = els.chatInput.value.trim();
    if (!value || !state.sessionId || state.busy) return;
    clearError();
    clearSuggestions();
    addMessage("user", value);
    els.chatInput.value = "";
    setChatBusy(true);
    try {
      const data = await api(
        "/api/chat",
        jsonRequest({ session_id: state.sessionId, message: value })
      );
      addAssistantMessage(data.reply, data.flags);
      renderEscalation(data.escalation);
      state.domain = data.domain || "unknown";
      renderCaseFile(data.case_file);
      updateNoticeHint();
    } catch (error) {
      showError(error.message);
      addAssistantMessage("Sorry, something went wrong. Please try again.");
    } finally {
      setChatBusy(false);
      els.chatInput.focus();
    }
  }

  function renderDocuments() {
    els.documentList.replaceChildren();
    els.documentsEmpty.hidden = state.documents.length > 0;
    state.documents.forEach(function (doc) {
      const item = el("li");
      item.appendChild(el("div", "document-name", doc.filename));
      const bits = [];
      if (doc.pages) bits.push(doc.pages + " pages");
      bits.push(doc.chars + " characters");
      if (doc.truncated) bits.push("truncated");
      item.appendChild(el("div", "document-meta", bits.join(" · ")));
      (doc.warnings || []).forEach(function (warning) {
        item.appendChild(el("span", "flag-note", "Note: " + warning.replace(/_/g, " ")));
      });
      addFlagNotes(item, doc.flags);
      els.documentList.appendChild(item);
    });
  }

  function syncDocumentSelects() {
    els.summaryDoc.replaceChildren();
    state.documents.forEach(function (doc) {
      const option = el("option", null, doc.filename);
      option.value = doc.doc_id;
      els.summaryDoc.appendChild(option);
    });
    els.summaryDoc.disabled = state.documents.length === 0;
  }

  async function handleUpload(event) {
    event.preventDefault();
    const file = els.fileInput.files && els.fileInput.files[0];
    if (!file) {
      showError("Choose a PDF, DOCX or TXT file first.");
      return;
    }
    if (!state.sessionId) {
      showError("Please wait until the session is ready.");
      return;
    }
    clearError();
    setButtonBusy(els.uploadButton, true, "Upload");
    const form = new FormData();
    form.append("session_id", state.sessionId);
    form.append("file", file);
    try {
      const data = await api("/api/upload", { method: "POST", body: form });
      state.documents.push(data);
      renderDocuments();
      syncDocumentSelects();
      els.fileInput.value = "";
      activateTab("summary");
    } catch (error) {
      showError(error.message);
    } finally {
      setButtonBusy(els.uploadButton, false, "Upload");
    }
  }

  function quoteBlock(text) {
    return el("blockquote", null, text);
  }

  function badge(text, className) {
    return el("span", "badge " + (className || ""), text);
  }

  function detailQuote(label, text) {
    const details = el("details");
    details.appendChild(el("summary", null, label));
    details.appendChild(quoteBlock(text));
    return details;
  }

  function sectionTitle(out, text) {
    out.appendChild(el("h3", null, text));
  }

  function renderSummary(payload) {
    const out = els.summaryOutput;
    out.replaceChildren();
    const summary = payload.summary || {};
    out.appendChild(el("p", null, summary.plain_summary || "No plain summary was returned."));

    const arbitration = summary.arbitration_clause || { found: false };
    const card = el("div", "card arbitration" + (arbitration.found ? "" : " clear"));
    card.appendChild(
      el(
        "p",
        "card-title",
        arbitration.found ? "Arbitration clause: found" : "Arbitration clause: not found"
      )
    );
    if (arbitration.found) {
      if (arbitration.quote) card.appendChild(quoteBlock(arbitration.quote));
      if (arbitration.plain_explanation) {
        card.appendChild(el("p", null, arbitration.plain_explanation));
      }
      const chips = el("div", "message-meta");
      (arbitration.kb_ids || []).forEach(function (id) {
        chips.appendChild(kbChip(id));
      });
      if (chips.childNodes.length) card.appendChild(chips);
    } else {
      card.appendChild(
        el("p", null, "No clause sending disputes to arbitration was found in this document.")
      );
    }
    out.appendChild(card);

    const parties = summary.parties || [];
    if (parties.length) {
      sectionTitle(out, "Parties");
      const list = el("ul");
      parties.forEach(function (party) {
        list.appendChild(el("li", null, party.name + (party.role ? " — " + party.role : "")));
      });
      out.appendChild(list);
    }

    const amounts = summary.key_amounts || [];
    if (amounts.length) {
      sectionTitle(out, "Amounts");
      const list = el("ul");
      amounts.forEach(function (item) {
        const amount = item.amount_inr === null || item.amount_inr === undefined
          ? ""
          : " — Rs. " + Number(item.amount_inr).toLocaleString("en-IN");
        const entry = el("li", null, item.label + amount);
        if (item.quote) entry.appendChild(detailQuote("Show source quote", item.quote));
        list.appendChild(entry);
      });
      out.appendChild(list);
    }

    const dates = summary.key_dates || [];
    if (dates.length) {
      sectionTitle(out, "Dates");
      const list = el("ul");
      dates.forEach(function (item) {
        const dateText = item.date_iso || item.date_raw || "unknown date";
        const entry = el("li", null, item.label + " — " + dateText);
        if (item.quote) entry.appendChild(detailQuote("Show source quote", item.quote));
        list.appendChild(entry);
      });
      out.appendChild(list);
    }

    const clauses = summary.key_clauses || [];
    if (clauses.length) {
      sectionTitle(out, "Key clauses");
      const list = el("ul");
      clauses.forEach(function (item) {
        const entry = el("li", null, item.topic + ": " + item.summary);
        if (item.quote) entry.appendChild(detailQuote("Show source quote", item.quote));
        list.appendChild(entry);
      });
      out.appendChild(list);
    }

    const redFlags = summary.red_flags || [];
    if (redFlags.length) {
      sectionTitle(out, "Red flags");
      const list = el("ul");
      redFlags.forEach(function (flag) {
        list.appendChild(el("li", null, flag));
      });
      out.appendChild(list);
    }

    if (payload.dropped_unverified) {
      out.appendChild(
        el(
          "p",
          "hint",
          payload.dropped_unverified +
            " item(s) were removed because they could not be verified in the document."
        )
      );
    }
    if ((payload.flags || []).length) {
      const notes = el("div");
      addFlagNotes(notes, payload.flags);
      out.appendChild(notes);
    }
  }

  async function summarize() {
    const docId = els.summaryDoc.value;
    if (!docId) {
      showError("Upload a document first.");
      return;
    }
    clearError();
    setButtonBusy(els.summarizeButton, true, "Summarize");
    try {
      const data = await api(
        "/api/summarize",
        jsonRequest({ session_id: state.sessionId, doc_id: docId })
      );
      renderSummary(data);
    } catch (error) {
      showError(error.message);
    } finally {
      setButtonBusy(els.summarizeButton, false, "Summarize");
    }
  }

  function renderTimelineEvent(event) {
    const item = el("li");
    item.appendChild(el("div", "timeline-date", event.date_iso || event.date_raw || "Undated"));
    item.appendChild(el("div", "timeline-event", event.event));
    const badges = el("div", "badges");
    if (event.confidence) badges.appendChild(badge("confidence: " + event.confidence, event.confidence));
    if (event.source) badges.appendChild(badge("source: " + event.source));
    item.appendChild(badges);
    if (event.quote) item.appendChild(detailQuote("Show source quote", event.quote));
    return item;
  }

  function renderTimeline(payload) {
    const out = els.timelineOutput;
    out.replaceChildren();
    const events = payload.events || [];
    const undated = payload.undated || [];
    if (!events.length && !undated.length) {
      out.appendChild(
        el("p", "empty", "No events could be verified yet. Upload a document or describe the dates in chat.")
      );
    }
    if (events.length) {
      const list = el("ol", "timeline");
      events.forEach(function (event) {
        list.appendChild(renderTimelineEvent(event));
      });
      out.appendChild(list);
    }
    if (undated.length) {
      sectionTitle(out, "Undated");
      const list = el("ul", "timeline");
      undated.forEach(function (event) {
        list.appendChild(renderTimelineEvent(event));
      });
      out.appendChild(list);
    }
    if (payload.dropped_unverified) {
      out.appendChild(
        el(
          "p",
          "hint",
          payload.dropped_unverified + " item(s) were removed because they could not be verified."
        )
      );
    }
    if ((payload.flags || []).length) {
      const notes = el("div");
      addFlagNotes(notes, payload.flags);
      out.appendChild(notes);
    }
  }

  async function buildTimeline() {
    clearError();
    setButtonBusy(els.timelineButton, true, "Build timeline");
    try {
      const data = await api(
        "/api/timeline",
        jsonRequest({ session_id: state.sessionId, include_chat: true })
      );
      renderTimeline(data);
    } catch (error) {
      showError(error.message);
    } finally {
      setButtonBusy(els.timelineButton, false, "Build timeline");
    }
  }

  const PLACEHOLDER_PATTERN = /\[([A-Za-z0-9][A-Za-z0-9 _\-/'.]{0,48})\](?!\()/g;

  function renderPlaceholders(container, text, placeholders) {
    const known = new Set(placeholders || []);
    const pattern = new RegExp(PLACEHOLDER_PATTERN.source, "g");
    let last = 0;
    let match = pattern.exec(text);
    while (match !== null) {
      container.appendChild(document.createTextNode(text.slice(last, match.index)));
      const node = known.has(match[0])
        ? el("mark", null, match[0])
        : document.createTextNode(match[0]);
      container.appendChild(node);
      last = match.index + match[0].length;
      match = pattern.exec(text);
    }
    container.appendChild(document.createTextNode(text.slice(last)));
  }

  function downloadText(filename, text) {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function renderNotice(payload) {
    const out = els.noticeOutput;
    out.replaceChildren();
    out.appendChild(
      el(
        "p",
        "draft-banner",
        "DRAFT - review before sending. This is not legal advice."
      )
    );
    const body = el("div", "notice-text");
    renderPlaceholders(body, payload.notice_markdown || "", payload.missing_placeholders || []);
    out.appendChild(body);

    const placeholders = payload.missing_placeholders || [];
    if (placeholders.length) {
      sectionTitle(out, "Fill these in before sending");
      const list = el("ul");
      placeholders.forEach(function (placeholder) {
        list.appendChild(el("li", null, placeholder));
      });
      out.appendChild(list);
    }

    const actions = el("div", "toolbar");
    const copyButton = el("button", "secondary", "Copy");
    copyButton.type = "button";
    copyButton.addEventListener("click", function () {
      const text = payload.notice_markdown || "";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            copyButton.textContent = "Copied";
            window.setTimeout(function () {
              copyButton.textContent = "Copy";
            }, 1500);
          },
          function () {
            showError("Copy failed. Please select the text and copy it yourself.");
          }
        );
      } else {
        showError("Copy is not available in this browser.");
      }
    });
    const downloadButton = el("button", "secondary", "Download .txt");
    downloadButton.type = "button";
    downloadButton.addEventListener("click", function () {
      downloadText("legal-notice-draft.txt", payload.notice_markdown || "");
    });
    actions.appendChild(copyButton);
    actions.appendChild(downloadButton);
    out.appendChild(actions);

    if ((payload.flags || []).length) {
      const notes = el("div");
      addFlagNotes(notes, payload.flags);
      out.appendChild(notes);
    }
  }

  function updateNoticeHint() {
    const ready = state.domain === "deposit" || state.domain === "refund";
    els.noticeButton.disabled = !ready;
    els.noticeHint.textContent = ready
      ? ""
      : "Tell me first whether this is a deposit or a refund problem.";
  }

  async function draftNotice() {
    clearError();
    setButtonBusy(els.noticeButton, true, "Draft notice");
    try {
      const data = await api(
        "/api/notice",
        jsonRequest({
          session_id: state.sessionId,
          doc_ids: state.documents.map(function (doc) {
            return doc.doc_id;
          }),
        })
      );
      renderNotice(data);
    } catch (error) {
      showError(error.message);
    } finally {
      els.noticeButton.disabled = false;
      els.noticeButton.textContent = "Draft notice";
      updateNoticeHint();
    }
  }

  function factLabel(key) {
    return key.replace(/_/g, " ").replace(/\b(inr)\b/g, "(INR)");
  }

  function renderFactsTable(caseFile) {
    const table = el("table", "facts-table");
    const body = document.createElement("tbody");
    const facts = (caseFile && caseFile.facts) || {};
    Object.keys(facts).forEach(function (group) {
      const groupFacts = facts[group] || {};
      Object.keys(groupFacts).forEach(function (key) {
        const value = groupFacts[key];
        const empty =
          value === null ||
          value === undefined ||
          value === "" ||
          (Array.isArray(value) && value.length === 0);
        if (empty) return;
        const row = document.createElement("tr");
        row.appendChild(el("th", null, factLabel(key)));
        row.appendChild(el("td", null, Array.isArray(value) ? value.join("; ") : String(value)));
        body.appendChild(row);
      });
    });
    table.appendChild(body);
    return table;
  }

  function renderCaseFile(caseFile) {
    const out = els.caseOutput;
    out.replaceChildren();
    if (!caseFile) {
      out.appendChild(el("p", "empty", "Start a chat to build your case file."));
      return;
    }
    out.appendChild(
      el(
        "p",
        "hint",
        "Case type: " + (caseFile.domain || "unknown") + " · Language: " + (caseFile.language || "en")
      )
    );

    sectionTitle(out, "Facts collected");
    const table = renderFactsTable(caseFile);
    if (!table.querySelector("td")) {
      out.appendChild(el("p", "empty", "No facts yet."));
    } else {
      out.appendChild(table);
    }

    const evidence = caseFile.evidence || [];
    sectionTitle(out, "Evidence");
    if (evidence.length) {
      const list = el("ul");
      evidence.forEach(function (item) {
        list.appendChild(
          el("li", null, item.type + " — " + item.description + " (have: " + item.have + ")")
        );
      });
      out.appendChild(list);
    } else {
      out.appendChild(el("p", "empty", "No evidence recorded yet."));
    }

    const missing = caseFile.missing_info || [];
    sectionTitle(out, "Still needed");
    if (missing.length) {
      const list = el("ul");
      missing.forEach(function (item) {
        list.appendChild(el("li", null, item));
      });
      out.appendChild(list);
    } else {
      out.appendChild(el("p", "empty", "Nothing outstanding right now."));
    }
  }

  async function loadKb() {
    try {
      const entries = await api("/api/kb");
      state.kb = new Map(
        entries.map(function (entry) {
          return [entry.id, entry];
        })
      );
    } catch (error) {
      state.kb = new Map();
    }
  }

  function bindEvents() {
    els.chatForm.addEventListener("submit", sendMessage);
    els.chatInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        els.chatForm.requestSubmit();
      }
    });
    els.uploadForm.addEventListener("submit", handleUpload);
    els.summarizeButton.addEventListener("click", summarize);
    els.timelineButton.addEventListener("click", buildTimeline);
    els.noticeButton.addEventListener("click", draftNotice);
    els.errorClose.addEventListener("click", clearError);

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        activateTab(tab.dataset.panel, false);
      });
      tab.addEventListener("keydown", function (event) {
        const index = tabs.indexOf(tab);
        let next = null;
        if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
        if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
        if (event.key === "Home") next = tabs[0];
        if (event.key === "End") next = tabs[tabs.length - 1];
        if (next) {
          event.preventDefault();
          activateTab(next.dataset.panel, true);
        }
      });
    });
  }

  async function init() {
    bindEvents();
    activateTab("documents", false);
    setChatBusy(true);
    updateNoticeHint();
    renderCaseFile(null);
    await loadKb();
    try {
      const data = await api("/api/session", { method: "POST" });
      state.sessionId = data.session_id;
      addAssistantMessage(WELCOME);
      renderSuggestions();
      setChatBusy(false);
      els.chatInput.focus();
    } catch (error) {
      setChatBusy(false);
      showError("Could not start a session. Please reload the page.");
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
