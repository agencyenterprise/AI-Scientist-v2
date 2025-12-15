/**
 * Gemini Shared Conversation Extractor
 * 
 * Extracts conversation content from Gemini shared links (gemini.google.com/share/...)
 * Uses a child process to run Playwright, avoiding Next.js bundling issues.
 */

import { spawn } from 'child_process'
import path from 'path'

export type GeminiMessage = {
  role: 'user' | 'assistant' | 'unknown'
  text: string
}

export class GeminiSharedExtractor {
  async extractPlainText(sharedUrl: string): Promise<string> {
    console.error(`[GeminiExtractor] Starting extraction for URL: ${sharedUrl}`)
    
    if (!this.isValidGeminiShareUrl(sharedUrl)) {
      throw new Error('Invalid Gemini share URL. Expected format: https://gemini.google.com/share/...')
    }

    const result = await this.runExtractionScript(sharedUrl)
    
    if (!result.content || result.content.length < 100) {
      throw new Error('No readable messages found in Gemini conversation.')
    }

    console.error(`[GeminiExtractor] Successfully extracted ${result.content.length} chars`)
    return result.content
  }

  private isValidGeminiShareUrl(url: string): boolean {
    try {
      const parsed = new URL(url)
      return parsed.hostname === 'gemini.google.com' && parsed.pathname.startsWith('/share/')
    } catch {
      return false
    }
  }

  private runExtractionScript(url: string): Promise<{ title: string; content: string }> {
    return new Promise((resolve, reject) => {
      // Path to the extraction script
      const scriptPath = path.join(process.cwd(), 'scripts', 'extract-gemini.mjs')
      
      console.error(`[GeminiExtractor] Running extraction script: ${scriptPath}`)
      
      const child = spawn('node', [scriptPath, url], {
        cwd: process.cwd(),
        stdio: ['pipe', 'pipe', 'pipe']
      })
      
      let stdout = ''
      let stderr = ''
      
      child.stdout.on('data', (data) => {
        stdout += data.toString()
      })
      
      child.stderr.on('data', (data) => {
        stderr += data.toString()
        // Log Playwright's stderr for debugging
        console.error(`[GeminiExtractor] ${data.toString().trim()}`)
      })
      
      child.on('close', (code) => {
        if (code !== 0) {
          console.error(`[GeminiExtractor] Script exited with code ${code}`)
          console.error(`[GeminiExtractor] stderr: ${stderr}`)
          reject(new Error(`Extraction failed: ${stderr || 'Unknown error'}`))
          return
        }
        
        try {
          const result = JSON.parse(stdout.trim())
          if (result.error) {
            reject(new Error(result.error))
          } else {
            resolve(result)
          }
        } catch (e) {
          reject(new Error(`Failed to parse extraction result: ${stdout}`))
        }
      })
      
      child.on('error', (err) => {
        reject(new Error(`Failed to run extraction script: ${err.message}`))
      })
      
      // Timeout after 60 seconds
      setTimeout(() => {
        child.kill()
        reject(new Error('Extraction timed out after 60 seconds'))
      }, 60000)
    })
  }
}
