#!/usr/bin/env node
/**
 * Test the Gemini extractor service
 * Run: node test-gemini-service.mjs
 */

import { chromium } from '@playwright/test'

const GEMINI_URL = 'https://gemini.google.com/share/8410a01fc0d8'

// Minimal inline implementation for testing (mirrors the service)
async function testGeminiExtraction(url) {
  console.log(`\n🧪 Testing Gemini Extraction`)
  console.log(`   URL: ${url}\n`)
  
  const browser = await chromium.launch({ headless: true })
  
  try {
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    const page = await context.newPage()
    
    console.log('1️⃣ Navigating to page...')
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
    
    console.log('2️⃣ Waiting for content to render...')
    await page.waitForSelector('main', { timeout: 15000 })
    await page.waitForTimeout(3000)
    
    console.log('3️⃣ Extracting title...')
    const title = await page.evaluate(() => {
      const heading = document.querySelector('h1, [role="heading"]')
      return heading?.textContent?.trim() || 'Untitled'
    })
    console.log(`   Title: "${title}"`)
    
    console.log('4️⃣ Extracting conversation content...')
    const content = await page.evaluate(() => {
      const main = document.querySelector('main')
      if (!main) return ''
      
      // Get text content, filtering out UI elements
      const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT)
      const texts = []
      const seenTexts = new Set()
      let node
      
      while (node = walker.nextNode()) {
        const text = node.textContent?.trim()
        if (!text || text.length < 20) continue
        if (seenTexts.has(text)) continue
        
        // Skip UI elements
        const uiPatterns = [
          'Opens in a new window', 'Google Privacy', 'Terms of Service',
          'Sign in', 'About Gemini', 'Subscriptions', 'For Business',
          'may display inaccurate', 'Created with', 'Thinking with'
        ]
        if (uiPatterns.some(p => text.includes(p))) continue
        
        seenTexts.add(text)
        texts.push(text)
      }
      
      return texts.join('\n\n')
    })
    
    console.log(`   Content length: ${content.length} chars`)
    
    // Format as transcript
    const transcript = `GEMINI CONVERSATION: ${title}\n${'='.repeat(50)}\n\n${content}`
    
    console.log('\n5️⃣ Preview of extracted content:')
    console.log('─'.repeat(60))
    console.log(transcript.substring(0, 2000))
    console.log('...')
    console.log('─'.repeat(60))
    
    console.log('\n✅ EXTRACTION SUCCESSFUL!')
    console.log(`   Total transcript length: ${transcript.length} chars`)
    
    return { title, content: transcript, success: true }
    
  } catch (err) {
    console.error('\n❌ EXTRACTION FAILED:', err.message)
    return { success: false, error: err.message }
  } finally {
    await browser.close()
  }
}

// Run test
testGeminiExtraction(GEMINI_URL)
  .then(result => {
    if (result.success) {
      console.log('\n🎉 Test passed! Gemini extraction is working.')
      console.log(`   This content will be saved as extractedRawText in MongoDB`)
      console.log(`   and passed to the coding/review agents as ChatContext.\n`)
    }
    process.exit(result.success ? 0 : 1)
  })

