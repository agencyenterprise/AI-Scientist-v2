#!/usr/bin/env node
/**
 * Test script to extract Gemini conversation content using Playwright
 * Run: npx playwright test test-gemini-extract.mjs
 * Or: node test-gemini-extract.mjs (after: npx playwright install chromium)
 */

import { chromium } from '@playwright/test';

const GEMINI_URL = 'https://gemini.google.com/share/8410a01fc0d8';

async function extractGeminiConversation(url) {
  console.log(`Extracting from: ${url}`);
  
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
  });
  const page = await context.newPage();
  
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    
    // Wait for conversation content to load
    await page.waitForSelector('main', { timeout: 15000 });
    await page.waitForTimeout(5000); // Extra time for JS rendering
    
    // Get the title
    const title = await page.$eval('h1, [role="heading"]', el => el.textContent?.trim() || 'Untitled');
    console.log(`Title: ${title}`);
    
    // Get all text content from the main area
    const mainContent = await page.evaluate(() => {
      const main = document.querySelector('main');
      if (!main) return '';
      
      // Get all text nodes
      const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
      const texts = [];
      let node;
      while (node = walker.nextNode()) {
        const text = node.textContent?.trim();
        if (text && text.length > 10) {
          texts.push(text);
        }
      }
      return texts.join('\n\n');
    });
    
    console.log(`\n=== Main Content (${mainContent.length} chars) ===`);
    console.log(mainContent.substring(0, 2000));
    console.log('\n...\n');
    
    // Try to find message containers specifically
    const messages = await page.evaluate(() => {
      // Look for message-like elements
      const messageElements = document.querySelectorAll('[class*="message"], [class*="response"], [class*="turn"], [data-message]');
      const msgs = [];
      messageElements.forEach(el => {
        const text = el.textContent?.trim();
        if (text && text.length > 20) {
          msgs.push(text);
        }
      });
      return msgs;
    });
    
    console.log(`Found ${messages.length} message elements`);
    
    // Get full HTML for inspection
    const html = await page.content();
    console.log(`\nFull HTML length: ${html.length}`);
    
    // Look for conversation data in page
    const conversationData = await page.evaluate(() => {
      // Check for any global data objects
      const dataKeys = ['__INITIAL_DATA__', '__NEXT_DATA__', 'WIZ_global_data'];
      for (const key of dataKeys) {
        if (window[key]) {
          return { key, data: JSON.stringify(window[key]).substring(0, 1000) };
        }
      }
      return null;
    });
    
    if (conversationData) {
      console.log(`\nFound global data: ${conversationData.key}`);
      console.log(conversationData.data);
    }
    
    return { title, content: mainContent };
    
  } finally {
    await browser.close();
  }
}

// Run
extractGeminiConversation(GEMINI_URL)
  .then(result => {
    console.log('\n=== RESULT ===');
    console.log(`Title: ${result.title}`);
    console.log(`Content length: ${result.content.length}`);
  })
  .catch(err => {
    console.error('Error:', err);
    process.exit(1);
  });

