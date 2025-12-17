#!/usr/bin/env node
/**
 * Full Gemini extraction test - captures all conversation content
 */

import { chromium } from '@playwright/test'

const GEMINI_URL = 'https://gemini.google.com/share/8410a01fc0d8'

async function testGeminiFull(url) {
  console.log(`\n🧪 Full Gemini Extraction Test`)
  console.log(`   URL: ${url}\n`)
  
  const browser = await chromium.launch({ headless: true })
  
  try {
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    const page = await context.newPage()
    
    console.log('1️⃣ Navigating...')
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.waitForSelector('main', { timeout: 15000 })
    await page.waitForTimeout(5000) // Wait longer for full render
    
    console.log('2️⃣ Extracting with multiple strategies...')
    
    // Strategy 1: Get inner text of main (simple but effective)
    const mainText = await page.evaluate(() => {
      const main = document.querySelector('main')
      return main?.innerText || ''
    })
    
    console.log(`   Strategy 1 (innerText): ${mainText.length} chars`)
    
    // Strategy 2: Get text from message containers
    const messageText = await page.evaluate(() => {
      const sections = document.querySelectorAll('main section')
      let text = ''
      sections.forEach(section => {
        const sectionText = section.innerText?.trim()
        if (sectionText && sectionText.length > 50) {
          text += sectionText + '\n\n---\n\n'
        }
      })
      return text
    })
    
    console.log(`   Strategy 2 (sections): ${messageText.length} chars`)
    
    // Use the longer result
    const content = mainText.length > messageText.length ? mainText : messageText
    
    // Clean up UI text
    const cleanedContent = content
      .split('\n')
      .filter(line => {
        const trimmed = line.trim()
        // Filter out common UI elements
        if (!trimmed) return false
        if (trimmed === 'Opens in a new window') return false
        if (trimmed.startsWith('Google Privacy')) return false
        if (trimmed.startsWith('Google Terms')) return false
        if (trimmed === 'Sign in') return false
        if (trimmed === 'About Gemini') return false
        if (trimmed === 'Subscriptions') return false
        if (trimmed === 'For Business') return false
        if (trimmed.includes('may display inaccurate')) return false
        return true
      })
      .join('\n')
    
    console.log(`   After cleanup: ${cleanedContent.length} chars`)
    
    // Get title
    const title = await page.evaluate(() => {
      const heading = document.querySelector('h1, [role="heading"]')
      return heading?.textContent?.trim() || 'Gemini Conversation'
    })
    
    const transcript = `GEMINI CONVERSATION: ${title}\n${'='.repeat(50)}\n\n${cleanedContent}`
    
    console.log('\n3️⃣ Preview:')
    console.log('─'.repeat(60))
    console.log(transcript.substring(0, 3000))
    if (transcript.length > 3000) {
      console.log('\n... (truncated) ...\n')
      console.log(transcript.substring(transcript.length - 1000))
    }
    console.log('─'.repeat(60))
    
    console.log(`\n✅ Total extracted: ${transcript.length} chars`)
    
    return { title, content: transcript, length: transcript.length }
    
  } finally {
    await browser.close()
  }
}

testGeminiFull(GEMINI_URL)
  .then(result => {
    console.log(`\n🎉 Success! Got ${result.length} chars of conversation.`)
    process.exit(0)
  })
  .catch(err => {
    console.error('❌ Error:', err)
    process.exit(1)
  })



