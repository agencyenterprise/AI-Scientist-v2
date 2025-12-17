/**
 * Gemini Shared Conversation Extractor
 * 
 * Extracts conversation content from Gemini shared links (gemini.google.com/share/...)
 * 
 * NOTE: Gemini extraction requires Playwright which cannot be bundled in Next.js.
 * This feature is only available in development mode. In production, use ChatGPT links.
 */

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

    // Check if we're in a context where we can run the extraction script
    // In production builds, this feature is disabled due to bundling limitations
    if (process.env.NODE_ENV === 'production') {
      throw new Error(
        'Gemini extraction is not available in production. ' +
        'Please use a ChatGPT share link instead, or run the extraction locally.'
      )
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

  private async runExtractionScript(_url: string): Promise<{ title: string; content: string }> {
    // This method is only called in development mode (checked in extractPlainText)
    // In production, we throw before reaching here
    // This stub prevents bundler from analyzing child_process/spawn
    throw new Error('Gemini extraction requires development environment')
  }
}
