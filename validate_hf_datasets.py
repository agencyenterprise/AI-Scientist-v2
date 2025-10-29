#!/usr/bin/env python3
"""
Validate HuggingFace Dataset Accessibility
==========================================
This script checks if datasets can be accessed from HuggingFace without downloading them.
It verifies that dataset IDs are valid and accessible with your credentials.
"""

import os
import sys
from dotenv import load_dotenv
from huggingface_hub import HfApi, list_datasets
from datasets import load_dataset_builder
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Load environment variables
load_dotenv()

console = Console()

# List of datasets to validate
DATASETS_TO_CHECK = [
    # Large-scale image datasets
    ("detection-datasets/coco", None, False, "COCO (330K images)"),
    ("timm/resisc45", None, False, "RESISC45 (31K images)"),
    ("food101", None, False, "Food-101 (101K images)"),
    ("nelorth/oxford-flowers", None, False, "Oxford Flowers 102 (8K images)"),
    
    # Large-scale text datasets
    ("allenai/c4", "en", False, "C4 (365GB web text)"),
    ("Skylion007/openwebtext", None, False, "OpenWebText (38GB)"),
    ("wikipedia", "20220301.en", False, "Wikipedia (6M articles)"),
    ("cc_news", None, False, "Common Crawl News (708K articles)"),
    ("togethercomputer/RedPajama-Data-1T-Sample", None, False, "RedPajama (1.2T tokens sample)"),
    
    # Multimodal datasets
    ("nlphuji/flickr30k", None, False, "Flickr30k (31K images, 158K captions)"),
    ("google-research-datasets/conceptual_captions", None, False, "Conceptual Captions (3.3M)"),
    ("wikimedia/wit_base", None, False, "WIT (37M+ associations)"),
    
    # NLP benchmarks
    ("nyu-mll/glue", "mnli", False, "GLUE - MNLI"),
    ("aps/super_glue", "cb", False, "SuperGLUE - CB"),
    ("rajpurkar/squad_v2", None, False, "SQuAD 2.0 (150K QA pairs)"),
    ("google-research-datasets/natural_questions", None, False, "Natural Questions (307K)"),
    ("ehovy/race", "all", False, "RACE (87K reading comprehension)"),
    
    # Code datasets
    ("code_search_net", "python", False, "CodeSearchNet (6M functions)"),
    ("codeparrot/apps", None, False, "APPS (10K programming problems)"),
    
    # Scientific datasets
    ("pubmed", None, False, "PubMed (biomedical abstracts)"),
    ("arxiv_dataset", None, False, "arXiv (1.7M papers)"),
    
    # Recommendation datasets
    ("amazon_us_reviews", "Books_v1_00", False, "Amazon Reviews - Books"),
    ("yelp_review_full", None, False, "Yelp Reviews (700K reviews)"),
    
    # Audio/Speech
    ("librispeech_asr", "clean", False, "LibriSpeech (1000 hours)"),
    ("marsyas/gtzan", "all", False, "GTZAN (1000 music tracks)"),
    
    # Small datasets (for prototyping)
    ("ylecun/mnist", None, False, "MNIST (60K images)"),
    ("uoft-cs/cifar10", None, False, "CIFAR-10 (50K images)"),
    ("uoft-cs/cifar100", None, False, "CIFAR-100 (50K images)"),
    ("zalando-datasets/fashion_mnist", None, False, "Fashion-MNIST (60K images)"),
    ("stanfordnlp/imdb", None, False, "IMDB (25K reviews)"),
    ("fancyzhx/ag_news", None, False, "AG News (120K articles)"),
]


def check_hf_token():
    """Check if HF_TOKEN is set"""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        console.print("[yellow]⚠️  Warning: HF_TOKEN not found in environment[/yellow]")
        console.print("[yellow]   Some gated datasets may not be accessible[/yellow]")
        return None
    console.print("[green]✓ HF_TOKEN found in environment[/green]")
    return token


def validate_dataset(dataset_id, config_name, requires_auth, description):
    """
    Validate if a dataset is accessible without downloading it.
    
    Returns:
        tuple: (status, message)
            status: "success", "warning", or "error"
            message: description of the result
    """
    try:
        # Try to get dataset info using HuggingFace API
        api = HfApi()
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
        
        # First, check if dataset exists in the Hub
        try:
            dataset_info = api.dataset_info(dataset_id, token=token)
            
            # Check if it's gated and requires authentication
            if hasattr(dataset_info, 'gated') and dataset_info.gated:
                if not token:
                    return ("error", "Dataset is gated but no HF_TOKEN provided")
                else:
                    # Try to load dataset builder to verify access
                    try:
                        builder = load_dataset_builder(
                            dataset_id, 
                            config_name, 
                            token=token,
                            trust_remote_code=True
                        )
                        return ("success", f"Accessible (gated, {builder.info.dataset_size or 'size unknown'})")
                    except Exception as e:
                        return ("warning", f"Gated but access may be restricted: {str(e)[:50]}")
            
            # Not gated, try to load builder to verify structure
            try:
                builder = load_dataset_builder(
                    dataset_id, 
                    config_name,
                    trust_remote_code=True
                )
                size_info = builder.info.dataset_size if hasattr(builder.info, 'dataset_size') else 'unknown size'
                return ("success", f"Accessible ({size_info})")
            except Exception as e:
                # Dataset exists but might have issues
                return ("warning", f"Found but may have issues: {str(e)[:80]}")
                
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                return ("error", "Dataset not found in HuggingFace Hub")
            elif "403" in error_msg or "unauthorized" in error_msg:
                return ("error", "Access denied - may need authentication or permission")
            else:
                return ("error", f"Error: {str(e)[:100]}")
                
    except Exception as e:
        return ("error", f"Unexpected error: {str(e)[:100]}")


def main():
    console.print("\n[bold cyan]🔍 HuggingFace Dataset Validation[/bold cyan]\n")
    console.print("This script checks if datasets are accessible without downloading them.\n")
    
    # Check for HF token
    token = check_hf_token()
    console.print()
    
    # Validate all datasets
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Validating datasets...", total=len(DATASETS_TO_CHECK))
        
        for dataset_id, config_name, requires_auth, description in DATASETS_TO_CHECK:
            progress.update(task, description=f"Checking {dataset_id}...")
            status, message = validate_dataset(dataset_id, config_name, requires_auth, description)
            results.append({
                "dataset_id": dataset_id,
                "config": config_name or "-",
                "description": description,
                "status": status,
                "message": message,
                "requires_auth": requires_auth
            })
            progress.advance(task)
    
    # Create results table
    table = Table(title="\n📊 Dataset Validation Results", show_lines=True)
    table.add_column("Dataset ID", style="cyan", no_wrap=False, max_width=35)
    table.add_column("Config", style="magenta", max_width=15)
    table.add_column("Description", style="blue", max_width=30)
    table.add_column("Auth", justify="center", max_width=5)
    table.add_column("Status", justify="center", max_width=10)
    table.add_column("Message", style="white", max_width=50)
    
    success_count = 0
    warning_count = 0
    error_count = 0
    
    for result in results:
        # Determine status emoji and color
        if result["status"] == "success":
            status_text = "[green]✓[/green]"
            success_count += 1
        elif result["status"] == "warning":
            status_text = "[yellow]⚠[/yellow]"
            warning_count += 1
        else:
            status_text = "[red]✗[/red]"
            error_count += 1
        
        auth_text = "🔒" if result["requires_auth"] else ""
        
        table.add_row(
            result["dataset_id"],
            result["config"],
            result["description"],
            auth_text,
            status_text,
            result["message"]
        )
    
    console.print(table)
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  [green]✓ Success: {success_count}/{len(DATASETS_TO_CHECK)}[/green]")
    if warning_count > 0:
        console.print(f"  [yellow]⚠ Warnings: {warning_count}/{len(DATASETS_TO_CHECK)}[/yellow]")
    if error_count > 0:
        console.print(f"  [red]✗ Errors: {error_count}/{len(DATASETS_TO_CHECK)}[/red]")
    
    # Recommendations
    console.print(f"\n[bold]Recommendations:[/bold]")
    
    if error_count > 0:
        console.print("  • Some datasets are not accessible - consider removing them from hf_dataset_reference.py")
    
    if warning_count > 0:
        console.print("  • Some datasets have warnings - they may work but could have issues")
        console.print("  • Consider testing these manually before using in production")
    
    if not token:
        console.print("  • Set HF_TOKEN in .env to access gated datasets (like ImageNet)")
        console.print("    Get your token from: https://huggingface.co/settings/tokens")
    
    console.print("\n[bold cyan]💡 Usage Tips:[/bold cyan]")
    console.print("  • Datasets marked with 🔒 require HuggingFace authentication")
    console.print("  • For large datasets (>10GB), use streaming=True in load_dataset()")
    console.print("  • Some datasets require accepting terms on HuggingFace website first")
    console.print()
    
    # Exit with appropriate code
    if error_count > len(DATASETS_TO_CHECK) * 0.3:  # More than 30% errors
        console.print("[yellow]⚠️  Warning: High error rate - review dataset IDs[/yellow]")
        sys.exit(1)
    else:
        console.print("[green]✅ Validation complete![/green]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

