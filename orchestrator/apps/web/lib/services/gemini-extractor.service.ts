/**
 * Gemini Shared Conversation Extractor
 * 
 * Extracts conversation content from Gemini shared links (gemini.google.com/share/...)
 * Uses Playwright for headless browser rendering since Gemini loads content via JavaScript.
 */

import { chromium, type Browser, type Page } from '@playwright/test'

export type GeminiMessage = {
  role: 'user' | 'assistant' | 'unknown'
  text: string
}

export class GeminiSharedExtractor {
  private browser: Browser | null = null

  async extractPlainText(sharedUrl: string): Promise<string> {
    console.error(`[GeminiExtractor] Starting extraction for URL: ${sharedUrl}`)
    
    if (!this.isValidGeminiShareUrl(sharedUrl)) {
      throw new Error('Invalid Gemini share URL. Expected format: https://gemini.google.com/share/...')
    }

    const { title, messages } = await this.extractWithPlaywright(sharedUrl)
    
    if (!messages || messages.length === 0) {
      throw new Error('No readable messages found in Gemini conversation.')
    }

    console.error(`[GeminiExtractor] Successfully extracted ${messages.length} messages`)
    return this.toPlainTranscript(title, messages)
  }

  private isValidGeminiShareUrl(url: string): boolean {
    try {
      const parsed = new URL(url)
      return parsed.hostname === 'gemini.google.com' && parsed.pathname.startsWith('/share/')
    } catch {
      return false
    }
  }

  private async extractWithPlaywright(url: string): Promise<{ title: string; messages: GeminiMessage[] }> {
    let browser: Browser | null = null
    
    try {
      console.error('[GeminiExtractor] Launching browser...')
      browser = await chromium.launch({ 
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      })
      
      const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
      })
      
      const page = await context.newPage()
      
      console.error('[GeminiExtractor] Navigating to page...')
      await page.goto(url, { 
        waitUntil: 'domcontentloaded', 
        timeout: 30000 
      })
      
      // Wait for main content to load
      await page.waitForSelector('main', { timeout: 15000 })
      
      // Extra time for JavaScript rendering
      await page.waitForTimeout(3000)
      
      console.error('[GeminiExtractor] Extracting content...')
      
      // Extract title
      const title = await page.evaluate(() => {
        const heading = document.querySelector('h1, [role="heading"]')
        return heading?.textContent?.trim() || 'Gemini Conversation'
      })
      
      // Extract messages by parsing the rendered content
      const messages = await this.extractMessagesFromPage(page)
      
      return { title, messages }
      
    } finally {
      if (browser) {
        await browser.close()
      }
    }
  }

  private async extractMessagesFromPage(page: Page): Promise<GeminiMessage[]> {
    // Gemini renders conversations in sections within main
    // The best strategy is to get innerText from each section
    
    const rawContent = await page.evaluate(() => {
      const main = document.querySelector('main')
      if (!main) return { sections: [], fullText: '' }
      
      // Strategy: Get text from each section element
      const sections: string[] = []
      const sectionElements = main.querySelectorAll('section')
      
      sectionElements.forEach(section => {
        const text = (section as HTMLElement).innerText?.trim()
        if (text && text.length > 50) {
          sections.push(text)
        }
      })
      
      // Fallback: get full innerText
      const fullText = (main as HTMLElement).innerText?.trim() || ''
      
      return { sections, fullText }
    })
    
    // Use sections if available (better structure), otherwise use full text
    let contentText = ''
    if (rawContent.sections.length > 0) {
      contentText = rawContent.sections.join('\n\n---\n\n')
    } else {
      contentText = rawContent.fullText
    }
    
    // Clean up UI elements
    const cleanedLines = contentText.split('\n').filter(line => {
      const trimmed = line.trim()
      if (!trimmed) return false
      return !this.isUIText(trimmed)
    })
    
    const cleanedText = cleanedLines.join('\n')
    
    // Return as a single message (Gemini conversations are typically one flow)
    // The LLM will parse the structure when creating the hypothesis
    if (cleanedText.length > 100) {
      return [{
        role: 'unknown',
        text: this.cleanText(cleanedText)
      }]
    }
    
    return []
  }

  private isUIText(text: string): boolean {
    const uiPatterns = [
      'Opens in a new window',
      'Google Privacy Policy',
      'Terms of Service',
      'Sign in',
      'About Gemini',
      'Subscriptions',
      'For Business',
      'may display inaccurate',
      'double-check',
      'Created with',
      'Thinking with',
      'Published',
      'https://gemini.google.com'
    ]
    
    return uiPatterns.some(pattern => text.includes(pattern))
  }

  private splitIntoSections(text: string): string[] {
    // Split on paragraph breaks
    const sections = text.split(/\n\n+/)
    return sections.filter(s => s.trim().length > 0)
  }

  private cleanText(text: string): string {
    return text
      .replace(/\r/g, '')
      .replace(/\t/g, '  ')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+$/gm, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  }

  private dedupeMessages(messages: GeminiMessage[]): GeminiMessage[] {
    const result: GeminiMessage[] = []
    
    for (const msg of messages) {
      // Skip if this message is a substring of an existing message
      const isDuplicate = result.some(existing => 
        existing.text.includes(msg.text) || msg.text.includes(existing.text)
      )
      
      if (!isDuplicate) {
        result.push(msg)
      } else {
        // If this is a longer version, replace the shorter one
        const shorterIdx = result.findIndex(existing => 
          msg.text.includes(existing.text) && msg.text.length > existing.text.length
        )
        if (shorterIdx >= 0) {
          result[shorterIdx] = msg
        }
      }
    }
    
    return result
  }

  private toPlainTranscript(title: string, messages: GeminiMessage[]): string {
    let transcript = `GEMINI CONVERSATION: ${title}\n${'='.repeat(50)}\n\n`
    
    for (const msg of messages) {
      const roleLabel = msg.role.toUpperCase()
      transcript += `${roleLabel}:\n${msg.text}\n\n`
    }
    
    return transcript.trim()
  }
}

