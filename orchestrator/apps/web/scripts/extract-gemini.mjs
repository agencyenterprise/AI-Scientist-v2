#!/usr/bin/env node
/**
 * Standalone Gemini extraction script
 * Called via child_process to avoid bundling Playwright with Next.js
 * 
 * Usage: node scripts/extract-gemini.mjs <gemini-share-url>
 * Output: JSON to stdout with { title, content } or { error }
 */

import { chromium } from '@playwright/test'

const url = process.argv[2]

if (!url || !url.includes('gemini.google.com/share/')) {
  console.log(JSON.stringify({ error: 'Invalid Gemini share URL' }))
  process.exit(1)
}

async function extract() {
  let browser = null
  
  try {
    browser = await chromium.launch({ 
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    })
    
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    const page = await context.newPage()
    
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.waitForSelector('main', { timeout: 15000 })
    await page.waitForTimeout(4000) // Wait for JS rendering
    
    // Extract title
    const title = await page.evaluate(() => {
      const heading = document.querySelector('h1, [role="heading"]')
      return heading?.textContent?.trim() || 'Gemini Conversation'
    })
    
    // Extract content from sections
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
    
    // Use sections if available
    let contentText = ''
    if (rawContent.sections.length > 0) {
      contentText = rawContent.sections.join('\n\n---\n\n')
    } else {
      contentText = rawContent.fullText
    }
    
    // Clean up UI text
    const uiPatterns = [
      'Opens in a new window', 'Google Privacy Policy', 'Terms of Service',
      'Sign in', 'About Gemini', 'Subscriptions', 'For Business',
      'may display inaccurate', 'double-check', 'Created with',
      'Thinking with', 'Published', 'https://gemini.google.com'
    ]
    
    const cleanedLines = contentText.split('\n').filter(line => {
      const trimmed = line.trim()
      if (!trimmed) return false
      return !uiPatterns.some(p => trimmed.includes(p))
    })
    
    const cleanedContent = cleanedLines.join('\n')
      .replace(/\r/g, '')
      .replace(/\t/g, '  ')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    
    // Format as transcript
    const transcript = `GEMINI CONVERSATION: ${title}\n${'='.repeat(50)}\n\n${cleanedContent}`
    
    console.log(JSON.stringify({ title, content: transcript }))
    
  } catch (err) {
    console.log(JSON.stringify({ error: err.message }))
    process.exit(1)
  } finally {
    if (browser) await browser.close()
  }
}

extract()

