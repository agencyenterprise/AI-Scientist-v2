#!/usr/bin/env node
/**
 * Standalone ChatGPT extractor script
 * Reuses the existing TypeScript extraction logic from the orchestrator
 */

const { ChatGPTSharedExtractor } = require('./orchestrator/apps/web/lib/services/chatgpt-extractor.service.ts');

async function main() {
  const url = process.argv[2];
  
  if (!url) {
    console.error('Usage: node extract_chatgpt.js <chatgpt_share_url>');
    process.exit(1);
  }
  
  try {
    const extractor = new ChatGPTSharedExtractor();
    const text = await extractor.extractPlainText(url);
    console.log(text);
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

main();


