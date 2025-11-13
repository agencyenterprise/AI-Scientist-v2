// lib/chatgptSharedExtractor.ts
import * as cheerio from "cheerio";

export type Message = { role: string; text: string };

export class ChatGPTSharedExtractor {
  async extractPlainText(sharedUrl: string): Promise<string> {
    console.error(`[DEBUG] Starting extraction for URL: ${sharedUrl}`);
    const html = await this.fetchHtml(sharedUrl);
    console.error(`[DEBUG] Fetched HTML, length: ${html.length} characters`);

    // Try streamed React Router data (new format)
    console.error(`[DEBUG] Attempting extraction method 1: extractFromStreamedData`);
    let messages = this.extractFromStreamedData(html);
    console.error(`[DEBUG] extractFromStreamedData result: ${messages ? messages.length : 0} messages`);

    // Try JSON payload (older format)
    if (!messages || messages.length === 0) {
      console.error(`[DEBUG] Attempting extraction method 2: extractFromNextData`);
      messages = this.extractFromNextData(html);
      console.error(`[DEBUG] extractFromNextData result: ${messages ? messages.length : 0} messages`);
    }

    // Fallback: rendered HTML
    if (!messages || messages.length === 0) {
      console.error(`[DEBUG] Attempting extraction method 3: extractFromHTMLRendered`);
      messages = this.extractFromHTMLRendered(html);
      console.error(`[DEBUG] extractFromHTMLRendered result: ${messages ? messages.length : 0} messages`);
    }

    if (!messages || messages.length === 0) {
      console.error(`[DEBUG] ERROR: All extraction methods failed. HTML preview (first 500 chars): ${html.substring(0, 500)}`);
      throw new Error("No readable messages found. The page structure may have changed or the chat is restricted.");
    }
    console.error(`[DEBUG] Successfully extracted ${messages.length} messages`);
    return this.toPlainTranscript(messages);
  }

  // -------- Internals --------

  private extractFromStreamedData(html: string): Message[] | null {
    // ChatGPT now uses React Router with streamed data
    // Find the large script tag containing .enqueue() call
    const $ = cheerio.load(html);
    let mainData = "";
    let scriptCount = 0;
    let enqueueScriptCount = 0;
    
    $("script").each((i, el) => {
      scriptCount++;
      const content = $(el).html() || "";
      // Look for the script that contains .enqueue with a large data payload
      if (content.includes('.enqueue(')) {
        enqueueScriptCount++;
        console.error(`[DEBUG] Found script with .enqueue(), length: ${content.length}`);
        if (content.length > 100000) {
          mainData = content;
          console.error(`[DEBUG] Selected script with .enqueue() as mainData, length: ${content.length}`);
        }
      }
    });
    
    console.error(`[DEBUG] Total script tags: ${scriptCount}, scripts with .enqueue(): ${enqueueScriptCount}`);
    if (!mainData) {
      console.error(`[DEBUG] No suitable script with .enqueue() found (need length > 100000)`);
      return null;
    }
    
    // Extract the enqueue call with the large JSON payload
    // Find .enqueue(" and extract until the closing ");
    const enqueueStart = mainData.indexOf('.enqueue("');
    console.error(`[DEBUG] Looking for .enqueue(" pattern, found at index: ${enqueueStart}`);
    if (enqueueStart === -1) {
      console.error(`[DEBUG] Pattern .enqueue(" not found in mainData`);
      return null;
    }
    
    const dataStart = enqueueStart + '.enqueue("'.length;
    let i = dataStart;
    let jsonStr = '';
    
    // Extract data handling escaped quotes properly
    while (i < mainData.length) {
      const char = mainData[i];
      
      // If we find a backslash, include it and the next character
      if (char === '\\' && i + 1 < mainData.length) {
        jsonStr += char;
        jsonStr += mainData[i + 1];
        i += 2;
        continue;
      }
      
      // If we find unescaped ", that's the end
      if (char === '"') {
        break;
      }
      
      jsonStr += char;
      i++;
    }
    
    if (i >= mainData.length) return null;
    
    // Unescape: \\\\ becomes \\, then \\" becomes "
    jsonStr = jsonStr
      .replace(/\\\\/g, '\x00BACKSLASH\x00')
      .replace(/\\"/g, '"')
      .replace(/\x00BACKSLASH\x00/g, '\\');
    
    // Find the JSON array start
    const jsonStart = jsonStr.indexOf('[');
    console.error(`[DEBUG] Extracted jsonStr length: ${jsonStr.length}, looking for '[' at index: ${jsonStart}`);
    if (jsonStart === -1) {
      console.error(`[DEBUG] No '[' found in jsonStr, preview: ${jsonStr.substring(0, 200)}`);
      return null;
    }
    
    let jsonOnly = jsonStr.substring(jsonStart).trim();
    console.error(`[DEBUG] jsonOnly length after substring: ${jsonOnly.length}`);
    
    // Remove trailing \n (escaped newline chars)
    if (jsonOnly.endsWith('\\n')) {
      jsonOnly = jsonOnly.substring(0, jsonOnly.length - 2);
    }
    
    try {
      const data = JSON.parse(jsonOnly);
      console.error(`[DEBUG] Successfully parsed JSON, isArray: ${Array.isArray(data)}, type: ${typeof data}`);
      if (!Array.isArray(data)) {
        console.error(`[DEBUG] Parsed data is not an array`);
        return null;
      }
      
      // Extract substantial conversation strings
      const conversationStrings = this.extractConversationStrings(data);
      console.error(`[DEBUG] Extracted ${conversationStrings.length} conversation strings`);
      
      // Convert strings to messages
      const messages: Message[] = [];
      for (const text of conversationStrings) {
        // Heuristic: longer texts are likely assistant responses
        const role = text.length > 200 ? 'assistant' : 'unknown';
        messages.push({ role, text: this.cleanText(text) });
      }
      
      console.error(`[DEBUG] Created ${messages.length} messages from conversation strings`);
      return messages.length > 0 ? messages : null;
    } catch (e) {
      console.error(`[DEBUG] Failed to parse streamed data: ${e instanceof Error ? e.message : String(e)}`);
      console.error(`[DEBUG] jsonOnly preview (first 500 chars): ${jsonOnly.substring(0, 500)}`);
      return null;
    }
  }
  
  private extractConversationStrings(data: any): string[] {
    const allStrings: string[] = [];
    let totalStrings = 0;
    let filteredStrings = 0;
    
    const extractStrings = (obj: any, depth = 0): void => {
      if (depth > 15) return;
      
      if (typeof obj === 'string') {
        totalStrings++;
        // Filter for actual conversation content:
        // - At least 50 characters (substantial content)
        // - Contains spaces (actual sentences)
        // - Not all caps
        // - Not technical IDs or URLs
        if (obj.length >= 50 && 
            obj.includes(' ') &&
            !obj.startsWith('_') && 
            obj !== obj.toUpperCase() &&
            !obj.startsWith('http') &&
            !obj.includes('window.') &&
            !obj.includes('function') &&
            !obj.includes('const ') &&
            !obj.match(/^[A-Za-z0-9_-]{20,}$/)) {
          allStrings.push(obj);
          filteredStrings++;
        }
      } else if (Array.isArray(obj)) {
        obj.forEach(item => extractStrings(item, depth + 1));
      } else if (obj && typeof obj === 'object') {
        Object.values(obj).forEach(v => extractStrings(v, depth + 1));
      }
    };
    
    extractStrings(data);
    console.error(`[DEBUG] extractConversationStrings: found ${totalStrings} total strings, ${filteredStrings} passed filters`);
    return allStrings;
  }

  private async fetchHtml(u: string): Promise<string> {
    console.error(`[DEBUG] Fetching HTML from: ${u}`);
    const startTime = Date.now();
    const res = await fetch(u, {
      headers: {
        "user-agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "accept": "text/html,application/xhtml+xml",
      },
      // Shared chats are public; no cookies needed
      redirect: "follow",
    });
    const fetchTime = Date.now() - startTime;
    console.error(`[DEBUG] Fetch completed in ${fetchTime}ms, status: ${res.status} ${res.statusText}`);
    if (!res.ok) {
      console.error(`[DEBUG] HTTP error: ${res.status} ${res.statusText}`);
      throw new Error(`HTTP ${res.status} fetching page`);
    }
    const html = await res.text();
    console.error(`[DEBUG] HTML received, length: ${html.length} characters`);
    return html;
  }

  private extractFromNextData(html: string): Message[] | null {
    console.error(`[DEBUG] extractFromNextData: Looking for __NEXT_DATA__`);
    const $ = cheerio.load(html);

    let jsonText = $("#__NEXT_DATA__").html();
    if (!jsonText) {
      console.error(`[DEBUG] __NEXT_DATA__ not found, searching scripts for props/pageProps`);
      $("script").each((_, el) => {
        const t = $(el).html() || "";
        if (!jsonText && t.includes('"props"') && t.includes('"pageProps"')) {
          jsonText = t;
          console.error(`[DEBUG] Found script with props/pageProps, length: ${t.length}`);
        }
      });
    } else {
      console.error(`[DEBUG] Found __NEXT_DATA__, length: ${jsonText.length}`);
    }
    if (!jsonText) {
      console.error(`[DEBUG] No __NEXT_DATA__ or props/pageProps script found`);
      return null;
    }

    let root: any;
    try {
      root = JSON.parse(jsonText);
      console.error(`[DEBUG] Successfully parsed __NEXT_DATA__ JSON`);
    } catch (e1) {
      console.error(`[DEBUG] First JSON parse failed: ${e1 instanceof Error ? e1.message : String(e1)}`);
      try {
        root = JSON.parse(jsonText.replace(/&quot;/g, '"').replace(/&#34;/g, '"'));
        console.error(`[DEBUG] Successfully parsed after HTML entity replacement`);
      } catch (e2) {
        console.error(`[DEBUG] Second JSON parse also failed: ${e2 instanceof Error ? e2.message : String(e2)}`);
        return null;
      }
    }
    const msgs = this.collectMessagesFromJSON(root);
    console.error(`[DEBUG] collectMessagesFromJSON found ${msgs.length} messages`);
    const uniq = this.dedupeMessages(msgs);
    console.error(`[DEBUG] After deduplication: ${uniq.length} messages`);
    const filtered = uniq.filter((m) => ["user", "assistant", "system", "tool"].includes(m.role) || m.role === "unknown");
    console.error(`[DEBUG] After filtering: ${filtered.length} messages`);
    return filtered;
  }

  private extractFromHTMLRendered(html: string): Message[] {
    console.error(`[DEBUG] extractFromHTMLRendered: Parsing HTML for rendered content`);
    const $ = cheerio.load(html);
    const chunks: Message[] = [];

    // Broad capture of potential message nodes
    const candidates = $('[data-message-author-role], article, main, div')
      .toArray()
      .map((el) => $(el));
    console.error(`[DEBUG] Found ${candidates.length} candidate elements`);

    for (const el of candidates) {
      const roleAttr = el.attr("data-message-author-role");
      const role =
        roleAttr ||
        (el.text().trim().startsWith("You:") ? "user" : undefined) ||
        "unknown";

      // Capture code blocks separately to preserve them cleanly
      const codeBlocks = el.find("pre code").toArray().map((e) => $(e).text());

      // Remove code from a clone to avoid duplicate text
      const clone = el.clone();
      clone.find("pre").remove();
      let txt = clone.text();

      if (codeBlocks.length) {
        txt = `${txt}\n\n${codeBlocks.map((c) => "```\n" + c + "\n```").join("\n\n")}`;
      }

      txt = this.cleanText(txt);
      if (txt && txt.length > 40) {
        chunks.push({ role, text: txt });
      }
    }

    console.error(`[DEBUG] extractFromHTMLRendered: Found ${chunks.length} chunks before deduplication`);
    const deduped = this.dedupeMessages(chunks);
    console.error(`[DEBUG] extractFromHTMLRendered: ${deduped.length} chunks after deduplication`);
    return deduped;
  }

  // ---- JSON walking & formatting ----

  private collectMessagesFromJSON(node: any, out: Message[] = []): Message[] {
    if (!node || typeof node !== "object") return out;

    // Common shapes across versions:
    // - { author: { role }, content: { parts|text|... } }
    // - { message: { author, content } }
    // - { role, content }
    const candidate =
      (node.message && node.message.author && node.message.content && node.message) ||
      (node.author && node.content && node) ||
      (typeof (node as any).role === "string" && (node as any).content);

    if (candidate) {
      const role: string =
        candidate.author?.role ??
        candidate.role ??
        candidate.author_role ??
        "unknown";

      const text = this.extractTextFromContent(candidate.content);
      if (text) {
        out.push({ role: String(role), text: this.cleanText(text) });
      }
    }

    if (Array.isArray(node)) {
      for (const item of node) this.collectMessagesFromJSON(item, out);
    } else {
      for (const k of Object.keys(node)) this.collectMessagesFromJSON(node[k], out);
    }
    return out;
  }

  private extractTextFromContent(rawContent: any): string {
    let text = "";

    // 1) content.parts = [string...]
    if (rawContent?.parts && Array.isArray(rawContent.parts)) {
      text = rawContent.parts.filter((p: any) => typeof p === "string").join("\n\n");
    }

    // 2) newer shapes
    if (!text) {
      if (typeof rawContent?.text === "string") text = rawContent.text;
      else if (Array.isArray(rawContent)) {
        text = rawContent
          .map((block) => {
            if (typeof block === "string") return block;
            if (block?.text) return block.text;
            if (block?.type === "image" && block?.url) return `[Image] ${block.url}`;
            if (block?.type === "code" && block?.text) return "```\n" + block.text + "\n```";
            if (block?.type && block?.data?.url) return `[${block.type}] ${block.data.url}`;
            return "";
          })
          .filter(Boolean)
          .join("\n\n");
      } else if (rawContent?.content_type && rawContent?.parts) {
        text = rawContent.parts.join("\n\n");
      } else if (typeof rawContent === "string") {
        text = rawContent;
      }
    }

    // 3) last resort: walk the object and pull any text-like fields
    if (!text && rawContent && typeof rawContent === "object") {
      text = this.extractAnyText(rawContent);
    }

    return text;
  }

  private extractAnyText(obj: any): string {
    const acc: string[] = [];
    const walk = (n: any) => {
      if (n == null) return;
      if (typeof n === "string") {
        acc.push(n);
        return;
      }
      if (Array.isArray(n)) {
        n.forEach(walk);
        return;
      }
      if (typeof n === "object") {
        if (typeof n.text === "string") acc.push(n.text);
        if (typeof n.title === "string") acc.push(n.title);
        if (n.url && (n.type === "image" || n.kind === "image")) acc.push(`[Image] ${n.url}`);
        for (const v of Object.values(n)) walk(v);
      }
    };
    walk(obj);
    return this.cleanText(acc.join("\n\n"));
  }

  private toPlainTranscript(messages: Message[]): string {
    return messages
      .map((m) => `${m.role.toUpperCase()}:\n${this.toPlain(m.text)}\n`)
      .join("\n");
  }

  private toPlain(textOrMd: string): string {
    // lightweight markdown → text
    let s = String(textOrMd ?? "");
    s = s.replace(/```[\s\S]*?```/g, (m) =>
      m.replace(/```[a-zA-Z0-9_-]*\n?/, "").replace(/```$/, "")
    );
    s = s.replace(/`([^`]+)`/g, "$1");
    s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, "[$1] $2");
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)");
    s = s.replace(/^> ?/gm, "");
    s = s.replace(/^#{1,6}\s*/gm, "");
    s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
    s = s.replace(/\*([^*]+)\*/g, "$1");
    s = s.replace(/_([^_]+)_/g, "$1");
    s = s.replace(/^-{3,}$/gm, "");
    return this.cleanText(s);
  }

  private cleanText(s: string): string {
    return String(s ?? "")
      .replace(/\r/g, "")
      .replace(/\t/g, "  ")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+$/gm, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  private dedupeMessages(msgs: Message[]): Message[] {
    const seen = new Set<string>();
    const out: Message[] = [];
    for (const m of msgs) {
      const k = `${m.role}::${m.text}`;
      if (!seen.has(k)) {
        seen.add(k);
        out.push(m);
      }
    }
    return out;
  }
}
