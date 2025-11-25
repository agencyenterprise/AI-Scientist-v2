"""
Idea Processor Service

This service polls MongoDB for new research idea documents, creates markdown files,
and runs the AI Scientist pipeline (ideation + experiment execution).

The service marks processed documents to avoid re-processing and captures detailed
error traces for debugging.
"""

import os
import sys
import time
import subprocess
import traceback
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from pymongo import MongoClient
from dotenv import load_dotenv


class IdeaProcessor:
    """Processes research ideas from MongoDB through the AI Scientist pipeline."""
    
    def __init__(
        self,
        mongo_url: str,
        poll_interval: int = 60,
        dry_run: bool = False,
        collection_name: str = 'ideas'
    ):
        """
        Initialize the processor.
        
        Args:
            mongo_url: MongoDB connection string
            poll_interval: Polling interval in seconds (default: 60)
            dry_run: If True, only print commands without executing them
            collection_name: Name of the MongoDB collection to query (default: 'ideas')
        """
        self.mongo_url = mongo_url
        self.poll_interval = poll_interval
        self.dry_run = dry_run
        self.client = MongoClient(mongo_url)
        self.db = self.client['ai-scientist']
        self.ideas_collection = self.db[collection_name]
        self.ideas_dir = Path("ai_scientist/ideas")
        self.workspace_root = Path(__file__).parent
        
        # Ensure ideas directory exists
        self.ideas_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Initialized IdeaProcessor")
        print(f"MongoDB collection: {collection_name}")
        print(f"Ideas directory: {self.ideas_dir.absolute()}")
        print(f"Poll interval: {poll_interval}s")
        print(f"Dry run mode: {'ENABLED' if dry_run else 'DISABLED'}")
        if dry_run:
            print("⚠️  DRY RUN MODE - Commands will be printed but not executed")
    
    def run_command(
        self, 
        command: str, 
        description: str,
        cwd: Optional[Path] = None
    ) -> tuple[bool, str]:
        """
        Run a shell command and capture output.
        
        Args:
            command: Command to execute
            description: Human-readable description for logging
            cwd: Working directory (default: workspace root)
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        if cwd is None:
            cwd = self.workspace_root
            
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Command: {command}")
        print(f"Working directory: {cwd}")
        print(f"{'='*60}\n")
        
        # In dry-run mode, just print and return success
        if self.dry_run:
            print("🔍 DRY RUN - Command would be executed with:")
            print(f"   Full command: source .venv/bin/activate && {command}")
            print(f"   Shell: /bin/zsh")
            print(f"   Timeout: 3600s (1 hour)")
            print(f"\n✓ [DRY RUN] {description} would be executed\n")
            return True, "[DRY RUN] Command not executed"
        
        try:
            # Activate virtual environment and run command
            activate_cmd = "source .venv/bin/activate"
            full_command = f"{activate_cmd} && {command}"
            
            result = subprocess.run(
                full_command,
                shell=True,
                cwd=str(cwd),
                executable='/bin/zsh',
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            
            if result.returncode == 0:
                print(f"✓ {description} completed successfully")
                return True, output
            else:
                print(f"✗ {description} failed with return code {result.returncode}")
                return False, output
                
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after 1 hour"
            print(f"✗ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Exception: {str(e)}\n{traceback.format_exc()}"
            print(f"✗ {description} raised exception: {str(e)}")
            return False, error_msg
    
    def create_markdown_file(self, name: str, content: str) -> bool:
        """
        Create a markdown file with the given content.
        
        Args:
            name: Base filename (without extension)
            content: Markdown content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self.ideas_dir / f"{name}.md"
            file_path.write_text(content, encoding='utf-8')
            print(f"✓ Created markdown file: {file_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to create markdown file: {e}")
            return False
    
    def update_document(self, doc_id: Any, update_dict: Dict[str, Any]) -> None:
        """
        Update a MongoDB document, or print the update in dry-run mode.
        
        Args:
            doc_id: Document ID to update
            update_dict: Dictionary of fields to update
        """
        if self.dry_run:
            print(f"\n🔍 [DRY RUN] Would update document {doc_id} with:")
            for key, value in update_dict.items():
                # Truncate long values for readability
                if isinstance(value, str) and len(value) > 200:
                    display_value = value[:200] + "... [truncated]"
                else:
                    display_value = value
                print(f"   {key}: {display_value}")
            print()
        else:
            self.ideas_collection.update_one(
                {'_id': doc_id},
                {'$set': update_dict}
            )
    
    def process_idea(self, document: Dict[str, Any]) -> None:
        """
        Process a single idea document through the AI Scientist pipeline.
        
        Args:
            document: MongoDB document containing idea information
        """
        doc_id = document['_id']
        name = document.get('name')
        content = document.get('content')
        
        print(f"\n{'#'*60}")
        print(f"Processing document: {doc_id}")
        print(f"Name: {name}")
        print(f"{'#'*60}\n")
        
        if not name or not content:
            error_msg = "Missing required fields: 'name' or 'content'"
            print(f"✗ {error_msg}")
            self.update_document(doc_id, {
                'seen': True,
                'errored': True,
                'error_message': error_msg,
                'processed_at': datetime.utcnow()
            })
            return
        
        # Create markdown file
        if not self.create_markdown_file(name, content):
            error_msg = "Failed to create markdown file"
            self.update_document(doc_id, {
                'seen': True,
                'errored': True,
                'error_message': error_msg,
                'processed_at': datetime.utcnow()
            })
            return
        
        # Step 1: Run ideation
        ideation_cmd = (
            f"python ai_scientist/perform_ideation_temp_free.py "
            f"--workshop-file \"ai_scientist/ideas/{name}.md\" "
            f"--model gpt-5.1 "
            f"--max-num-generations 2 "
            f"--num-reflections 5"
        )
        
        success, output = self.run_command(
            ideation_cmd,
            "Ideation Phase"
        )
        
        if not success:
            print(f"✗ Ideation failed for {name}")
            self.update_document(doc_id, {
                'seen': True,
                'errored': True,
                'error_message': 'Ideation phase failed',
                'ideation_trace': output,
                'processed_at': datetime.utcnow()
            })
            return
        
        # Step 2: Run experiment execution
        experiment_cmd = (
            f"python launch_scientist_bfts.py "
            f"--load_ideas \"ai_scientist/ideas/{name}.json\" "
            f"--add_dataset_ref "
            f"--model_writeup gpt-5.1 "
            f"--model_citation gpt-5.1 "
            f"--model_review gpt-5.1 "
            f"--model_agg_plots gpt-5.1 "
            f"--num_cite_rounds 20"
        )
        
        success, output = self.run_command(
            experiment_cmd,
            "Experiment Execution Phase"
        )
        
        if not success:
            print(f"✗ Experiment execution failed for {name}")
            self.update_document(doc_id, {
                'seen': True,
                'errored': True,
                'error_message': 'Experiment execution phase failed',
                'runtime_trace': output,
                'processed_at': datetime.utcnow()
            })
            return
        
        # Success!
        print(f"✓ Successfully completed processing for {name}")
        self.update_document(doc_id, {
            'seen': True,
            'errored': False,
            'completed': True,
            'processed_at': datetime.utcnow()
        })
    
    def poll_and_process(self) -> None:
        """
        Main polling loop. Continuously checks for new documents and processes them.
        """
        print(f"\n{'='*60}")
        print("Starting polling loop...")
        print(f"{'='*60}\n")
        
        while True:
            try:
                # Query for unseen documents
                query = {'$or': [{'seen': {'$exists': False}}, {'seen': False}]}
                new_documents = list(self.ideas_collection.find(query))
                
                if new_documents:
                    print(f"\nFound {len(new_documents)} new document(s)")
                    
                    for document in new_documents:
                        try:
                            self.process_idea(document)
                        except Exception as e:
                            # Catch-all for unexpected errors
                            print(f"✗ Unexpected error processing document: {e}")
                            error_trace = traceback.format_exc()
                            self.update_document(document['_id'], {
                                'seen': True,
                                'errored': True,
                                'error_message': f'Unexpected error: {str(e)}',
                                'runtime_trace': error_trace,
                                'processed_at': datetime.utcnow()
                            })
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No new documents found")
                
            except Exception as e:
                print(f"✗ Error in polling loop: {e}")
                traceback.print_exc()
            
            # Wait before next poll
            time.sleep(self.poll_interval)
    
    def close(self) -> None:
        """Clean up resources."""
        self.client.close()
        print("Closed MongoDB connection")


def main():
    """Entry point for the idea processor service."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="MongoDB polling service for AI Scientist idea processing"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print commands without executing them (for testing)'
    )
    parser.add_argument(
        '--poll-interval',
        type=int,
        default=60,
        help='Polling interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--collection',
        type=str,
        default='ideas',
        help='MongoDB collection name (default: ideas)'
    )
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    mongo_url = os.getenv('MONGODB_URL') or os.getenv('MONGO_URL')
    if not mongo_url:
        print("ERROR: MONGODB_URL (or MONGO_URL) environment variable not set in .env file")
        sys.exit(1)
    
    # Create and run processor
    processor = IdeaProcessor(
        mongo_url=mongo_url,
        poll_interval=args.poll_interval,
        dry_run=args.dry_run,
        collection_name=args.collection
    )
    
    try:
        processor.poll_and_process()
    except KeyboardInterrupt:
        print("\n\nReceived interrupt signal, shutting down...")
    finally:
        processor.close()


if __name__ == "__main__":
    main()

