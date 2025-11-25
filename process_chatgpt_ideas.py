#!/usr/bin/env python3
"""
Process ChatGPT Shared Conversations into AI Scientist Ideas

This script:
1. Extracts ChatGPT conversations from shared URLs
2. Summarizes them using chain-of-density (preserving ALL important details)
3. Generates experiment ideas using the Sakana ideation process
4. Can either save for review or enqueue runs directly

Usage:
    # Extract, summarize, and ideate (review mode):
    python process_chatgpt_ideas.py --urls urls.txt --ideate-only
    
    # After review, enqueue the runs:
    python process_chatgpt_ideas.py --enqueue-from ideas_for_review.json
"""

import argparse
import json
import os
import sys
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
from pymongo import MongoClient
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# Import AI Scientist modules
sys.path.insert(0, str(Path(__file__).parent))
from ai_scientist.llm import create_client, get_response_from_llm
from ai_scientist.perform_ideation_temp_free import generate_temp_free_idea

# ChatGPT extractor will use Node.js script

console = Console()
load_dotenv()


class ChatGPTExtractor:
    """Wrapper around the Node.js ChatGPT extractor."""
    
    def __init__(self):
        self.script_path = Path(__file__).parent / "orchestrator" / "apps" / "web" / "lib" / "services" / "chatgpt-extractor.service.ts"
        if not self.script_path.exists():
            raise FileNotFoundError(f"ChatGPT extractor not found at {self.script_path}")
    
    def extract_plain_text(self, url: str) -> str:
        """
        Extract plain text from a ChatGPT shared URL using Node.js extractor.
        
        Args:
            url: The shared ChatGPT URL
            
        Returns:
            Plain text transcript of the conversation
        """
        import subprocess
        
        console.print(f"[yellow][DEBUG] Starting extraction for URL: {url}[/yellow]")
        
        # We'll use tsx to run the TypeScript directly
        # First try tsx, then fall back to a simple fetch approach
        try:
            # Create a simple inline Node.js script that uses the extractor
            inline_script = f"""
const cheerio = require('cheerio');

class ChatGPTSharedExtractor {{
  async extractPlainText(sharedUrl) {{
    console.error(`[DEBUG] Starting extraction for URL: ${{sharedUrl}}`);
    const html = await this.fetchHtml(sharedUrl);
    console.error(`[DEBUG] Fetched HTML, length: ${{html.length}} characters`);
    
    console.error(`[DEBUG] Attempting extraction method 1: extractFromStreamedData`);
    let messages = this.extractFromStreamedData(html);
    console.error(`[DEBUG] extractFromStreamedData result: ${{messages ? messages.length : 0}} messages`);
    
    if (!messages || messages.length === 0) {{
      console.error(`[DEBUG] Attempting extraction method 2: extractFromNextData`);
      messages = this.extractFromNextData(html);
      console.error(`[DEBUG] extractFromNextData result: ${{messages ? messages.length : 0}} messages`);
    }}
    if (!messages || messages.length === 0) {{
      console.error(`[DEBUG] Attempting extraction method 3: extractFromHTMLRendered`);
      messages = this.extractFromHTMLRendered(html);
      console.error(`[DEBUG] extractFromHTMLRendered result: ${{messages ? messages.length : 0}} messages`);
    }}
    if (!messages || messages.length === 0) {{
      console.error(`[DEBUG] ERROR: All extraction methods failed. HTML preview (first 500 chars): ${{html.substring(0, 500)}}`);
      throw new Error("No readable messages found");
    }}
    console.error(`[DEBUG] Successfully extracted ${{messages.length}} messages`);
    return this.toPlainTranscript(messages);
  }}

  async fetchHtml(u) {{
    console.error(`[DEBUG] Fetching HTML from: ${{u}}`);
    const startTime = Date.now();
    const res = await fetch(u, {{
      headers: {{
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "accept": "text/html,application/xhtml+xml",
      }},
      redirect: "follow",
    }});
    const fetchTime = Date.now() - startTime;
    console.error(`[DEBUG] Fetch completed in ${{fetchTime}}ms, status: ${{res.status}} ${{res.statusText}}`);
    if (!res.ok) {{
      console.error(`[DEBUG] HTTP error: ${{res.status}} ${{res.statusText}}`);
      throw new Error(`HTTP ${{res.status}} fetching page`);
    }}
    const html = await res.text();
    console.error(`[DEBUG] HTML received, length: ${{html.length}} characters`);
    return html;
  }}

  extractFromStreamedData(html) {{
    const $ = cheerio.load(html);
    let mainData = "";
    $("script").each((i, el) => {{
      const content = $(el).html() || "";
      if (content.includes('.enqueue(') && content.length > 100000) {{
        mainData = content;
      }}
    }});
    if (!mainData) return null;
    
    const enqueueStart = mainData.indexOf('.enqueue("');
    if (enqueueStart === -1) return null;
    const dataStart = enqueueStart + '.enqueue("'.length;
    let i = dataStart;
    let jsonStr = '';
    
    while (i < mainData.length) {{
      const char = mainData[i];
      if (char === '\\\\' && i + 1 < mainData.length) {{
        jsonStr += char + mainData[i + 1];
        i += 2;
        continue;
      }}
      if (char === '"') break;
      jsonStr += char;
      i++;
    }}
    if (i >= mainData.length) return null;
    
    jsonStr = jsonStr
      .replace(/\\\\\\\\/g, '\\x00BACKSLASH\\x00')
      .replace(/\\\\"/g, '"')
      .replace(/\\x00BACKSLASH\\x00/g, '\\\\');
    
    const jsonStart = jsonStr.indexOf('[');
    if (jsonStart === -1) return null;
    let jsonOnly = jsonStr.substring(jsonStart).trim();
    if (jsonOnly.endsWith('\\\\n')) {{
      jsonOnly = jsonOnly.substring(0, jsonOnly.length - 2);
    }}
    
    try {{
      const data = JSON.parse(jsonOnly);
      if (!Array.isArray(data)) return null;
      const conversationStrings = this.extractConversationStrings(data);
      const messages = [];
      for (const text of conversationStrings) {{
        const role = text.length > 200 ? 'assistant' : 'unknown';
        messages.push({{ role, text: this.cleanText(text) }});
      }}
      return messages.length > 0 ? messages : null;
    }} catch (e) {{
      return null;
    }}
  }}
  
  extractConversationStrings(data) {{
    const allStrings = [];
    const extractStrings = (obj, depth = 0) => {{
      if (depth > 15) return;
      if (typeof obj === 'string') {{
        if (obj.length >= 50 && obj.includes(' ') && !obj.startsWith('_') && 
            obj !== obj.toUpperCase() && !obj.startsWith('http') &&
            !obj.includes('window.') && !obj.includes('function') &&
            !obj.includes('const ') && !obj.match(/^[A-Za-z0-9_-]{{20,}}$/)) {{
          allStrings.push(obj);
        }}
      }} else if (Array.isArray(obj)) {{
        obj.forEach(item => extractStrings(item, depth + 1));
      }} else if (obj && typeof obj === 'object') {{
        Object.values(obj).forEach(v => extractStrings(v, depth + 1));
      }}
    }};
    extractStrings(data);
    return allStrings;
  }}

  extractFromNextData(html) {{ return null; }}
  extractFromHTMLRendered(html) {{ return []; }}
  
  toPlainTranscript(messages) {{
    return messages.map(m => `${{m.role.toUpperCase()}}:\\n${{m.text}}\\n`).join("\\n");
  }}
  
  cleanText(s) {{
    return String(s ?? "")
      .replace(/\\r/g, "")
      .replace(/\\t/g, "  ")
      .replace(/\\u00a0/g, " ")
      .replace(/[ \\t]+$/gm, "")
      .replace(/\\n{{3,}}/g, "\\n\\n")
      .trim();
  }}
}}

(async () => {{
  try {{
    console.error('[DEBUG] Node.js script starting extraction');
    const extractor = new ChatGPTSharedExtractor();
    const text = await extractor.extractPlainText("{url}");
    console.error(`[DEBUG] Extraction completed, output length: ${{text.length}}`);
    console.log(text);
  }} catch (error) {{
    console.error(`[DEBUG] Error in Node.js script: ${{error.message}}`);
    console.error(`[DEBUG] Error stack: ${{error.stack}}`);
    console.error(`Error: ${{error.message}}`);
    process.exit(1);
  }}
}})();
"""
            
            # Run the inline script with node
            console.print(f"[yellow][DEBUG] Running Node.js extraction script...[/yellow]")
            start_time = datetime.now()
            result = subprocess.run(
                ["node", "-e", inline_script],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path(__file__).parent / "orchestrator" / "apps" / "web")
            )
            elapsed = (datetime.now() - start_time).total_seconds()
            console.print(f"[yellow][DEBUG] Node.js script completed in {elapsed:.2f}s, return code: {result.returncode}[/yellow]")
            
            if result.stderr:
                console.print(f"[yellow][DEBUG] Node.js stderr output:[/yellow]")
                for line in result.stderr.strip().split('\n'):
                    console.print(f"[yellow]  {line}[/yellow]")
            
            if result.returncode != 0:
                console.print(f"[red][DEBUG] Extraction failed with return code {result.returncode}[/red]")
                console.print(f"[red][DEBUG] stdout: {result.stdout[:500]}[/red]")
                console.print(f"[red][DEBUG] stderr: {result.stderr[:500]}[/red]")
                raise ValueError(f"Extraction failed: {result.stderr}")
            
            output_text = result.stdout.strip()
            console.print(f"[green][DEBUG] Extraction successful, output length: {len(output_text)} characters[/green]")
            if len(output_text) < 100:
                console.print(f"[yellow][DEBUG] WARNING: Output seems very short, preview: {output_text[:200]}[/yellow]")
            
            return output_text
            
        except FileNotFoundError:
            console.print("[red][DEBUG] Node.js not found in PATH[/red]")
            raise ValueError("Node.js not found. Please install Node.js to use ChatGPT extraction.")
        except subprocess.TimeoutExpired:
            console.print("[red][DEBUG] Extraction timed out after 60 seconds[/red]")
            raise ValueError("ChatGPT extraction timed out after 60 seconds")
        except Exception as e:
            console.print(f"[red][DEBUG] Exception during extraction: {type(e).__name__}: {e}[/red]")
            import traceback
            console.print(f"[red][DEBUG] Traceback:[/red]")
            for line in traceback.format_exc().split('\n'):
                console.print(f"[red]  {line}[/red]")
            raise ValueError(f"Failed to extract ChatGPT conversation: {e}")


class ChainOfDensitySummarizer:
    """
    Implements Chain of Density summarization to preserve all critical details
    from ChatGPT conversations without creating a hypothesis yet.
    """
    
    SYSTEM_PROMPT = """You are an expert research summarizer. Your task is to distill a ChatGPT conversation into a comprehensive summary that preserves ALL critical technical details, concepts, and context.

DO NOT create a hypothesis or experimental design yet. Your goal is to create a dense, information-rich summary that:
1. Captures ALL key technical concepts, terms, and definitions discussed
2. Preserves the full context and reasoning from the conversation
3. Maintains any specific implementation details, parameters, or constraints mentioned
4. Includes all relevant background information needed to understand the topic
5. Keeps track of any important insights, observations, or conclusions

The summary should be thorough enough that someone reading it can understand the complete technical context without reading the original conversation. This will later be used for ideation, so missing important details will frustrate the user.

Return a JSON object with:
{
  "title": "A concise descriptive title for the conversation topic",
  "dense_summary": "A comprehensive, detailed summary preserving all technical content (3-5 paragraphs minimum)",
  "key_concepts": ["List of all important concepts, terms, and technical details"],
  "context": "Any critical background context or domain information"
}"""

    def __init__(self, model: str = "gpt-5.1"):
        self.model = model
        self.client, self.client_model = create_client(model)
    
    def summarize(self, conversation_text: str) -> Dict[str, str]:
        """
        Summarize a conversation using chain of density approach.
        
        Args:
            conversation_text: The extracted ChatGPT conversation text
            
        Returns:
            Dictionary with title, dense_summary, key_concepts, and context
        """
        console.print(f"[yellow]Summarizing conversation ({len(conversation_text)} chars)...[/yellow]")
        
        try:
            response_text, _ = get_response_from_llm(
                prompt=f"Conversation to summarize:\n\n{conversation_text}",
                client=self.client,
                model=self.client_model,
                system_message=self.SYSTEM_PROMPT,
                temperature=1.0
            )
            
            # Extract JSON from response
            json_str = self._extract_json(response_text)
            result = json.loads(json_str)
            
            console.print(f"[green]✓ Summarized: {result.get('title', 'Untitled')}[/green]")
            return result
            
        except Exception as e:
            console.print(f"[red]✗ Summarization failed: {e}[/red]")
            # Fallback: use first 1000 chars as summary
            return {
                "title": "ChatGPT Conversation",
                "dense_summary": conversation_text[:1000] + "...",
                "key_concepts": [],
                "context": "Summarization failed, using truncated conversation"
            }
    
    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from LLM response that might have markdown formatting."""
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        else:
            # Try to find JSON object directly
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return text[start:end]
        return text


class IdeationProcessor:
    """
    Handles the Sakana ideation process with retry logic for failed or empty results.
    """
    
    def __init__(self, model: str = "gpt-5.1", num_reflections: int = 5, max_retries: int = 3):
        self.model = model
        self.num_reflections = num_reflections
        self.max_retries = max_retries
        self.client, self.client_model = create_client(model)
        
        # Create runtime directory for workshop files
        self.runtime_dir = Path("ai_scientist/ideas/runtime/chatgpt_ideas")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
    
    def ideate(self, summary: Dict[str, str], conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Run ideation process on a summarized conversation.
        
        Args:
            summary: The dense summary from ChainOfDensitySummarizer
            conversation_id: Unique identifier for this conversation
            
        Returns:
            The first generated idea (as dict) or None if all retries fail
        """
        title = summary.get("title", "Untitled")
        dense_summary = summary.get("dense_summary", "")
        key_concepts = summary.get("key_concepts", [])
        context = summary.get("context", "")
        
        # Create workshop markdown file
        workshop_content = self._create_workshop_content(title, dense_summary, key_concepts, context)
        workshop_path = self.runtime_dir / f"{conversation_id}.md"
        workshop_path.write_text(workshop_content, encoding="utf-8")
        
        # Output path for ideas JSON
        ideas_path = self.runtime_dir / f"{conversation_id}.json"
        
        console.print(f"[yellow]Running ideation for: {title}[/yellow]")
        
        for attempt in range(self.max_retries):
            try:
                # Run ideation
                ideas = generate_temp_free_idea(
                    idea_fname=str(ideas_path),
                    client=self.client,
                    model=self.client_model,
                    workshop_description=workshop_content,
                    max_num_generations=1,  # Generate one idea at a time
                    num_reflections=self.num_reflections,
                    reload_ideas=False  # Don't reload, start fresh each retry
                )
                
                if ideas and len(ideas) > 0:
                    console.print(f"[green]✓ Generated idea: {ideas[0].get('Title', 'Untitled')}[/green]")
                    return ideas[0]
                else:
                    console.print(f"[yellow]⚠ Attempt {attempt + 1}/{self.max_retries}: No ideas generated, retrying...[/yellow]")
                    
            except Exception as e:
                console.print(f"[red]✗ Attempt {attempt + 1}/{self.max_retries} failed: {e}[/red]")
                if attempt < self.max_retries - 1:
                    console.print("[yellow]Retrying...[/yellow]")
        
        console.print(f"[red]✗ Failed to generate idea after {self.max_retries} attempts[/red]")
        return None
    
    @staticmethod
    def _create_workshop_content(title: str, summary: str, key_concepts: List[str], context: str) -> str:
        """Create a workshop markdown file for ideation."""
        concepts_str = "\n".join([f"- {concept}" for concept in key_concepts]) if key_concepts else "N/A"
        
        return f"""# {title}

## Context and Background

{context}

## Detailed Summary

{summary}

## Key Concepts and Technical Details

{concepts_str}

## Research Guidance

Based on the above context and technical details, propose a novel, high-impact research idea that:
1. Builds naturally on the concepts and observations discussed
2. Is feasible with standard academic lab resources
3. Could lead to a publication at a top ML conference
4. Explores new possibilities or challenges existing assumptions

Use the ideation tools (especially literature search) to ensure novelty and grounding in existing research.
"""


class ChatGPTIdeaPipeline:
    """
    Main pipeline that orchestrates extraction, summarization, and ideation.
    """
    
    def __init__(
        self,
        summarizer_model: str = "gpt-5.1",
        ideation_model: str = "gpt-5.1",
        num_reflections: int = 5,
        parallel_ideation: int = 2,
        mongodb_url: Optional[str] = None
    ):
        self.extractor = ChatGPTExtractor()
        self.summarizer = ChainOfDensitySummarizer(model=summarizer_model)
        self.ideator = IdeationProcessor(
            model=ideation_model,
            num_reflections=num_reflections
        )
        self.parallel_ideation = parallel_ideation
        
        # MongoDB connection (only used in enqueue mode)
        self.mongodb_url = mongodb_url or os.getenv("MONGODB_URL")
        self.mongo_client = None
        self.db = None
    
    def _connect_mongodb(self):
        """Lazy connection to MongoDB."""
        if not self.mongo_client and self.mongodb_url:
            self.mongo_client = MongoClient(self.mongodb_url)
            self.db = self.mongo_client["ai-scientist"]
            console.print("[green]✓ Connected to MongoDB[/green]")
    
    def process_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Process a single ChatGPT URL through the full pipeline.
        
        Returns:
            Dictionary with summary and idea, or None if failed
        """
        conversation_id = str(uuid.uuid4())
        
        try:
            # Step 1: Extract
            console.print(f"\n[bold cyan]Processing: {url}[/bold cyan]")
            conversation_text = self.extractor.extract_plain_text(url)
            
            if not conversation_text or len(conversation_text.strip()) < 100:
                console.print("[red]✗ Extracted text too short or empty[/red]")
                return None
            
            # Step 2: Summarize
            summary = self.summarizer.summarize(conversation_text)
            
            # Step 3: Ideate
            idea = self.ideator.ideate(summary, conversation_id)
            
            if not idea:
                console.print("[red]✗ Failed to generate idea[/red]")
                return None
            
            return {
                "conversation_id": conversation_id,
                "url": url,
                "summary": summary,
                "idea": idea,
                "raw_text": conversation_text,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            console.print(f"[red]✗ Error processing {url}: {e}[/red]")
            traceback.print_exc()
            return None
    
    def process_urls_parallel(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple URLs in parallel (ideation is parallelized).
        
        Args:
            urls: List of ChatGPT shared URLs
            
        Returns:
            List of successfully processed ideas
        """
        results = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task(f"[cyan]Processing {len(urls)} URLs...", total=len(urls))
            
            # Process extraction and summarization sequentially (they're fast)
            # Then parallelize ideation (which is slow)
            summaries_to_ideate = []
            
            for url in urls:
                conversation_id = str(uuid.uuid4())
                try:
                    # Extract
                    progress.update(task, description=f"[cyan]Extracting: {url[:50]}...")
                    conversation_text = self.extractor.extract_plain_text(url)
                    
                    if not conversation_text or len(conversation_text.strip()) < 100:
                        console.print(f"[red]✗ Skipping {url}: Extracted text too short[/red]")
                        progress.update(task, advance=1)
                        continue
                    
                    # Summarize
                    progress.update(task, description=f"[cyan]Summarizing: {url[:50]}...")
                    summary = self.summarizer.summarize(conversation_text)
                    
                    summaries_to_ideate.append({
                        "conversation_id": conversation_id,
                        "url": url,
                        "summary": summary,
                        "raw_text": conversation_text
                    })
                    
                except Exception as e:
                    console.print(f"[red]✗ Error extracting/summarizing {url}: {e}[/red]")
                    progress.update(task, advance=1)
                    continue
            
            # Now parallelize ideation
            progress.update(task, description=f"[cyan]Running ideation on {len(summaries_to_ideate)} summaries...")
            
            with ThreadPoolExecutor(max_workers=self.parallel_ideation) as executor:
                future_to_data = {}
                
                for data in summaries_to_ideate:
                    future = executor.submit(
                        self.ideator.ideate,
                        data["summary"],
                        data["conversation_id"]
                    )
                    future_to_data[future] = data
                
                for future in as_completed(future_to_data):
                    data = future_to_data[future]
                    try:
                        idea = future.result()
                        if idea:
                            results.append({
                                "conversation_id": data["conversation_id"],
                                "url": data["url"],
                                "summary": data["summary"],
                                "idea": idea,
                                "raw_text": data["raw_text"],
                                "processed_at": datetime.utcnow().isoformat()
                            })
                            console.print(f"[green]✓ Completed: {data['summary']['title']}[/green]")
                        else:
                            console.print(f"[red]✗ Failed to ideate: {data['url']}[/red]")
                    except Exception as e:
                        console.print(f"[red]✗ Exception during ideation: {e}[/red]")
                    finally:
                        progress.update(task, advance=1)
        
        return results
    
    def save_for_review(self, results: List[Dict[str, Any]], output_file: str):
        """Save processed ideas to a JSON file for review."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        
        console.print(f"\n[bold green]✓ Saved {len(results)} ideas to {output_file}[/bold green]")
        console.print("[yellow]Review the ideas and run with --enqueue-from to create experiments[/yellow]")
    
    def enqueue_runs(self, ideas_file: str):
        """
        Create hypotheses and enqueue runs from a reviewed ideas file.
        
        Args:
            ideas_file: Path to JSON file with reviewed ideas
        """
        self._connect_mongodb()
        
        if self.db is None:
            console.print("[red]✗ MongoDB connection required for enqueuing runs[/red]")
            return
        
        # Load ideas
        with open(ideas_file, "r") as f:
            ideas = json.load(f)
        
        console.print(f"\n[bold cyan]Enqueuing {len(ideas)} runs...[/bold cyan]\n")
        
        hypotheses_collection = self.db["hypotheses"]
        runs_collection = self.db["runs"]
        
        for item in ideas:
            try:
                idea = item["idea"]
                summary = item["summary"]
                
                hypothesis_id = str(uuid.uuid4())
                run_id = str(uuid.uuid4())
                now = datetime.utcnow()
                
                # Create hypothesis document
                hypothesis = {
                    "_id": hypothesis_id,
                    "title": idea.get("Title", summary["title"]),
                    "idea": summary["dense_summary"],
                    "ideaJson": idea,
                    "chatGptUrl": item["url"],
                    "createdAt": now,
                    "createdBy": "chatgpt_processor",
                    "updatedAt": now
                }
                
                hypotheses_collection.insert_one(hypothesis)
                console.print(f"[green]✓ Created hypothesis: {hypothesis['title']}[/green]")
                
                # Create run document
                run = {
                    "_id": run_id,
                    "hypothesisId": hypothesis_id,
                    "status": "QUEUED",
                    "chatgptUrl": item["url"],
                    "createdAt": now,
                    "updatedAt": now
                }
                
                runs_collection.insert_one(run)
                console.print(f"[green]  ✓ Enqueued run: {run_id}[/green]")
                
            except Exception as e:
                console.print(f"[red]✗ Failed to enqueue: {e}[/red]")
                traceback.print_exc()
        
        console.print(f"\n[bold green]✓ Successfully enqueued {len(ideas)} experiments![/bold green]")


def main():
    parser = argparse.ArgumentParser(
        description="Process ChatGPT conversations into AI Scientist experiment ideas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process URLs and save for review
  python process_chatgpt_ideas.py --urls urls.txt --ideate-only
  
  # Process single URL
  python process_chatgpt_ideas.py --url "https://chatgpt.com/share/..." --ideate-only
  
  # After review, enqueue runs
  python process_chatgpt_ideas.py --enqueue-from ideas_for_review.json
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--url",
        type=str,
        help="Single ChatGPT shared URL to process"
    )
    input_group.add_argument(
        "--urls",
        type=str,
        help="File containing ChatGPT shared URLs (one per line)"
    )
    input_group.add_argument(
        "--enqueue-from",
        type=str,
        help="JSON file with ideas to enqueue (from previous --ideate-only run)"
    )
    
    # Mode options
    parser.add_argument(
        "--ideate-only",
        action="store_true",
        help="Only extract, summarize, and ideate (don't enqueue runs)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ideas_for_review.json",
        help="Output file for ideas (default: ideas_for_review.json)"
    )
    
    # Model options
    parser.add_argument(
        "--summarizer-model",
        type=str,
        default="gpt-5.1",
        help="Model for summarization (default: gpt-5.1)"
    )
    parser.add_argument(
        "--ideation-model",
        type=str,
        default="gpt-5.1",
        help="Model for ideation (default: gpt-5.1)"
    )
    parser.add_argument(
        "--num-reflections",
        type=int,
        default=5,
        help="Number of reflection rounds for ideation (default: 5)"
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=2,
        help="Number of parallel ideation processes (default: 2)"
    )
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = ChatGPTIdeaPipeline(
        summarizer_model=args.summarizer_model,
        ideation_model=args.ideation_model,
        num_reflections=args.num_reflections,
        parallel_ideation=args.parallel
    )
    
    # Enqueue mode
    if args.enqueue_from:
        if not Path(args.enqueue_from).exists():
            console.print(f"[red]Error: File not found: {args.enqueue_from}[/red]")
            sys.exit(1)
        
        pipeline.enqueue_runs(args.enqueue_from)
        return
    
    # Ideate mode - collect URLs
    urls = []
    if args.url:
        urls = [args.url]
    elif args.urls:
        urls_file = Path(args.urls)
        if not urls_file.exists():
            console.print(f"[red]Error: File not found: {args.urls}[/red]")
            sys.exit(1)
        
        with open(urls_file, "r") as f:
            urls = [line.strip() for line in f if line.strip() and line.strip().startswith("http")]
    
    if not urls:
        console.print("[red]Error: No URLs provided[/red]")
        sys.exit(1)
    
    console.print(f"[bold cyan]Processing {len(urls)} ChatGPT conversation(s)...[/bold cyan]")
    
    # Process URLs
    results = pipeline.process_urls_parallel(urls)
    
    # Save results
    if results:
        pipeline.save_for_review(results, args.output)
        console.print(f"\n[bold green]Success! Processed {len(results)}/{len(urls)} conversations[/bold green]")
    else:
        console.print("[red]No ideas were successfully generated[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

