#!/usr/bin/env node
/**
 * Test the actual GeminiSharedExtractor service
 */

// We need to transpile TypeScript, so let's use tsx or just replicate the logic
import { chromium } from '@playwright/test'

const GEMINI_URL = 'https://gemini.google.com/share/8410a01fc0d8'

// Replicating the service logic exactly
class GeminiSharedExtractor {
  async extractPlainText(sharedUrl) {
    console.log(`[GeminiExtractor] Starting extraction for URL: ${sharedUrl}`)
    
    if (!this.isValidGeminiShareUrl(sharedUrl)) {
      throw new Error('Invalid Gemini share URL')
    }

    const { title, messages } = await this.extractWithPlaywright(sharedUrl)
    
    if (!messages || messages.length === 0) {
      throw new Error('No readable messages found')
    }

    console.log(`[GeminiExtractor] Successfully extracted ${messages.length} messages`)
    return this.toPlainTranscript(title, messages)
  }

  isValidGeminiShareUrl(url) {
    try {
      const parsed = new URL(url)
      return parsed.hostname === 'gemini.google.com' && parsed.pathname.startsWith('/share/')
    } catch {
      return false
    }
  }

  async extractWithPlaywright(url) {
    let browser = null
    
    try {
      console.log('[GeminiExtractor] Launching browser...')
      browser = await chromium.launch({ 
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      })
      
      const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      })
      
      const page = await context.newPage()
      
      console.log('[GeminiExtractor] Navigating to page...')
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
      await page.waitForSelector('main', { timeout: 15000 })
      await page.waitForTimeout(3000)
      
      console.log('[GeminiExtractor] Extracting content...')
      
      const title = await page.evaluate(() => {
        const heading = document.querySelector('h1, [role="heading"]')
        return heading?.textContent?.trim() || 'Gemini Conversation'
      })
      
      const messages = await this.extractMessagesFromPage(page)
      
      return { title, messages }
      
    } finally {
      if (browser) await browser.close()
    }
  }

  async extractMessagesFromPage(page) {
    const rawContent = await page.evaluate(() => {
      const main = document.querySelector('main')
      if (!main) return { sections: [], fullText: '' }
      
      const sections = []
      const sectionElements = main.querySelectorAll('section')
      
      sectionElements.forEach(section => {
        const text = section.innerText?.trim()
        if (text && text.length > 50) {
          sections.push(text)
        }
      })
      
      const fullText = main.innerText?.trim() || ''
      
      return { sections, fullText }
    })
    
    let contentText = ''
    if (rawContent.sections.length > 0) {
      contentText = rawContent.sections.join('\n\n---\n\n')
    } else {
      contentText = rawContent.fullText
    }
    
    const cleanedLines = contentText.split('\n').filter(line => {
      const trimmed = line.trim()
      if (!trimmed) return false
      return !this.isUIText(trimmed)
    })
    
    const cleanedText = cleanedLines.join('\n')
    
    if (cleanedText.length > 100) {
      return [{ role: 'unknown', text: this.cleanText(cleanedText) }]
    }
    
    return []
  }

  isUIText(text) {
    const uiPatterns = [
      'Opens in a new window', 'Google Privacy Policy', 'Terms of Service',
      'Sign in', 'About Gemini', 'Subscriptions', 'For Business',
      'may display inaccurate', 'double-check', 'Created with',
      'Thinking with', 'Published', 'https://gemini.google.com'
    ]
    return uiPatterns.some(pattern => text.includes(pattern))
  }

  cleanText(text) {
    return text
      .replace(/\r/g, '')
      .replace(/\t/g, '  ')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+$/gm, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  }

  toPlainTranscript(title, messages) {
    let transcript = `GEMINI CONVERSATION: ${title}\n${'='.repeat(50)}\n\n`
    for (const msg of messages) {
      transcript += `${msg.role.toUpperCase()}:\n${msg.text}\n\n`
    }
    return transcript.trim()
  }
}

// Run the test
async function main() {
  console.log('🧪 Testing GeminiSharedExtractor service...\n')
  
  const extractor = new GeminiSharedExtractor()
  const result = await extractor.extractPlainText(GEMINI_URL)
  
  console.log(`\n✅ Extraction complete!`)
  console.log(`   Total length: ${result.length} chars`)
  console.log(`\n📄 Last 500 characters:`)
  console.log('─'.repeat(60))
  console.log(result.slice(-500))
  console.log('─'.repeat(60))
}

main().catch(err => {
  console.error('❌ Error:', err)
  process.exit(1)
})



