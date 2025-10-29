"""
HuggingFace Dataset Reference for AI Scientist
===============================================
This file provides examples of how to load various HuggingFace datasets.
The AI agent can see this file and use any of these datasets (or others from HuggingFace).

IMPORTANT: You have L40S GPUs with 48GB VRAM - use substantial datasets that leverage this hardware!
"""

import os
from datasets import load_dataset
from huggingface_hub import login

# Login to HuggingFace (required for gated datasets)
login(token=os.environ["HF_TOKEN"])


# ============================================================================
# LARGE-SCALE IMAGE DATASETS
# ============================================================================

# COCO (Common Objects in Context) - 330K images with rich annotations
coco = load_dataset("detection-datasets/coco")
# >>> coco
# {'train': (118287, 7), 'validation': (5000, 7)}

# RESISC45 - Remote Sensing Image Scene Classification (31K images, 45 classes)
resisc45 = load_dataset("timm/resisc45")
# >>> resisc45  
# {'train': (25200, 2), 'validation': (6300, 2)}

# Food-101 - 101K food images across 101 categories
food101 = load_dataset("food101")
# >>> food101
# {'train': (75750, 2), 'validation': (25250, 2)}

# Oxford Flowers 102 - 8K flower images across 102 categories
flowers102 = load_dataset("nelorth/oxford-flowers")
# >>> flowers102
# {'train': (1020, 2), 'validation': (1020, 2), 'test': (6149, 2)}


# ============================================================================
# LARGE-SCALE TEXT DATASETS  
# ============================================================================

# C4 (Colossal Clean Crawled Corpus) - 365GB of cleaned web text
# One of the largest public text corpora
c4 = load_dataset("allenai/c4", "en", streaming=True)  # Use streaming for large datasets
# >>> c4
# IterableDatasetDict({
#     train: IterableDataset (over 300M documents)
#     validation: IterableDataset (364608 documents)
# })

# OpenWebText - 38GB of Reddit-quality web content
openwebtext = load_dataset("Skylion007/openwebtext", streaming=True)
# >>> openwebtext
# Over 8 million documents

# Wikipedia - Full English Wikipedia dump
wikipedia = load_dataset("wikipedia", "20220301.en", streaming=True)
# >>> wikipedia  
# Over 6 million articles

# Common Crawl News - News articles from Common Crawl
cc_news = load_dataset("cc_news", streaming=True)
# >>> cc_news
# 708,241 news articles

# RedPajama - 1.2 trillion tokens across 7 data slices
# High-quality pretraining corpus
redpajama = load_dataset("togethercomputer/RedPajama-Data-1T-Sample", streaming=True)
# >>> redpajama
# Sample of the full 1.2T token corpus


# ============================================================================
# LARGE-SCALE MULTIMODAL DATASETS
# ============================================================================

# Flickr30k - 31K images with 5 captions each (158K total captions)
flickr30k = load_dataset("nlphuji/flickr30k")
# >>> flickr30k
# {'test': (31014, 3)} - Each image has 5 captions

# Conceptual Captions - 3.3M image-text pairs
conceptual_captions = load_dataset("google-research-datasets/conceptual_captions")
# >>> conceptual_captions
# {'train': (3318333, 2), 'validation': (15840, 2)}

# WIT (Wikipedia-based Image Text) - 37M+ image-text associations
wit = load_dataset("wikimedia/wit_base", streaming=True)
# >>> wit
# Multilingual image-text from Wikipedia


# ============================================================================
# LARGE-SCALE NLP BENCHMARKS
# ============================================================================

# GLUE (General Language Understanding Evaluation)
glue = load_dataset("nyu-mll/glue", "mnli")  # Can use any GLUE task
# >>> glue
# {'train': (392702, 5), 'validation_matched': (9815, 5), 'validation_mismatched': (9832, 5)}

# SuperGLUE - More challenging language understanding
superglue = load_dataset("aps/super_glue", "cb")
# >>> superglue
# Multiple challenging tasks

# SQuAD 2.0 - 150K+ question-answer pairs with unanswerable questions
squad = load_dataset("rajpurkar/squad_v2")
# >>> squad  
# {'train': (130319, 5), 'validation': (11873, 5)}

# Natural Questions - 307K real Google search questions
natural_questions = load_dataset("google-research-datasets/natural_questions", streaming=True)
# >>> natural_questions
# Real user questions with Wikipedia answers

# RACE (Reading Comprehension from Examinations)
race = load_dataset("ehovy/race", "all")
# >>> race
# {'train': (87866, 5), 'validation': (4887, 5), 'test': (4934, 5)}


# ============================================================================
# CODE DATASETS
# ============================================================================

# CodeSearchNet - 6M functions with documentation
codesearchnet = load_dataset("code_search_net", "python")
# >>> codesearchnet
# {'train': (412178, 7), 'validation': (23107, 7), 'test': (22176, 7)}

# APPS (Automated Programming Progress Standard) - 10K programming problems
apps = load_dataset("codeparrot/apps")
# >>> apps
# {'train': (5000, 8), 'test': (5000, 8)}


# ============================================================================
# SCIENTIFIC DATASETS
# ============================================================================

# PubMed - Biomedical literature abstracts
pubmed = load_dataset("pubmed", streaming=True)
# >>> pubmed
# Millions of biomedical abstracts

# arXiv - Scientific papers
arxiv = load_dataset("arxiv_dataset", streaming=True)
# >>> arxiv  
# 1.7M+ scientific papers

# ChEMBL - Drug discovery and medicinal chemistry
chembl = load_dataset("chembl/chembl_v33", streaming=True)
# >>> chembl
# Large-scale bioactivity database


# ============================================================================
# RECOMMENDATION / USER BEHAVIOR DATASETS
# ============================================================================

# Amazon Reviews - 233M reviews across categories
amazon_reviews = load_dataset("amazon_us_reviews", "Books_v1_00", streaming=True)
# >>> amazon_reviews
# Massive user review corpus

# Yelp Reviews - 700K restaurant reviews
yelp = load_dataset("yelp_review_full")
# >>> yelp
# {'train': (650000, 2), 'test': (50000, 2)} - 5-star rating reviews


# ============================================================================
# AUDIO / SPEECH DATASETS
# ============================================================================

# LibriSpeech - 1000 hours of English speech
librispeech = load_dataset("librispeech_asr", "clean", streaming=True)
# >>> librispeech
# High-quality speech recognition corpus

# GTZAN - Music genre classification (1000 audio tracks, 10 genres)
gtzan = load_dataset("marsyas/gtzan", "all")
# >>> gtzan
# Music genre classification benchmark


# ============================================================================
# VIDEO DATASETS
# ============================================================================

# Kinetics-400 - 240K training videos across 400 human action classes
# (Note: Requires special downloading, see HuggingFace docs)
# kinetics = load_dataset("kinetics-dataset/kinetics400", streaming=True)

# YouTube-8M - 8M video IDs with video-level labels
# (Requires downloading features separately)


# ============================================================================
# EXAMPLE: HOW TO USE STREAMING FOR VERY LARGE DATASETS
# ============================================================================

# For datasets that are too large to fit in memory, use streaming=True
# This loads data on-the-fly without downloading the entire dataset

from torch.utils.data import DataLoader

# Load dataset in streaming mode
dataset = load_dataset("c4", "en", split="train", streaming=True)

# Shuffle and take first N examples
dataset = dataset.shuffle(seed=42, buffer_size=10000).take(100000)

# Can iterate directly
for example in dataset:
    text = example["text"]
    # Process example
    break

# Or use with PyTorch DataLoader
# dataloader = DataLoader(dataset, batch_size=32)


# ============================================================================
# EXAMPLE: HOW TO HANDLE LARGE IMAGE DATASETS EFFICIENTLY
# ============================================================================

from PIL import Image
import torch
from torchvision import transforms

# Load large image dataset
dataset = load_dataset("imagenet-1k", split="train", streaming=True, use_auth_token=True)

# Define transforms
transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# Create custom dataset class
class TransformedDataset(torch.utils.data.IterableDataset):
    def __init__(self, hf_dataset, transform):
        self.dataset = hf_dataset
        self.transform = transform
    
    def __iter__(self):
        for example in self.dataset:
            image = example["image"]
            label = example["label"]
            if self.transform:
                image = self.transform(image)
            yield image, label

# Use with DataLoader
# transformed_dataset = TransformedDataset(dataset, transform)
# dataloader = DataLoader(transformed_dataset, batch_size=256, num_workers=8)


# ============================================================================
# SMALLER DATASETS (for quick prototyping only)
# ============================================================================

# MNIST - 60K training images (28x28 grayscale)
mnist = load_dataset("ylecun/mnist")

# CIFAR-10 - 50K training images (32x32 RGB)
cifar10 = load_dataset("uoft-cs/cifar10")

# CIFAR-100 - 50K training images with 100 classes  
cifar100 = load_dataset("uoft-cs/cifar100")

# Fashion-MNIST - 60K training images of fashion items
fashion_mnist = load_dataset("zalando-datasets/fashion_mnist")

# IMDB - 25K movie reviews for sentiment analysis
imdb = load_dataset("stanfordnlp/imdb")

# AG News - 120K news articles across 4 categories
ag_news = load_dataset("fancyzhx/ag_news")


# ============================================================================
# TIPS FOR USING LARGE DATASETS
# ============================================================================
"""
1. USE STREAMING for datasets > 10GB:
   dataset = load_dataset("dataset_name", streaming=True)
   
2. CACHE datasets locally to avoid re-downloading:
   The datasets library automatically caches to ~/.cache/huggingface/datasets/
   
3. USE SUBSET for initial testing:
   dataset = dataset.take(10000)  # First 10K examples
   
4. SHARD datasets for multi-GPU training:
   dataset = dataset.shard(num_shards=num_gpus, index=gpu_id)
   
5. LEVERAGE YOUR HARDWARE - You have 48GB VRAM:
   - Can use batch sizes of 256-1024 for most models
   - Can load larger models (7B-13B parameters)
   - Can cache significant portions of datasets in GPU memory
   
6. PARALLEL LOADING with DataLoader:
   dataloader = DataLoader(dataset, batch_size=256, num_workers=8, pin_memory=True)
"""

