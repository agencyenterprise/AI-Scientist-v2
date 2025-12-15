"""
HuggingFace Dataset Reference for AI Scientist
===============================================
This file provides examples of how to load various HuggingFace datasets.
The AI agent can see this file and use any of these datasets (or others from HuggingFace).

IMPORTANT HARDWARE: You have RTX 4090 GPUs with 24GB VRAM - use substantial datasets!

*** CRITICAL WARNING ***
========================
DO NOT use gated datasets or models that require accepting Terms of Service!
Examples of GATED datasets/models to AVOID:
  - meta-llama/* (Llama models)
  - mistralai/Mistral-7B-Instruct-* (gated versions)
  - Medical datasets with restricted access
  - Any dataset showing "Gated" badge on HuggingFace

These require manual human approval and WILL FAIL in automated pipelines.
Only use freely accessible public datasets listed below.
========================
"""

from datasets import load_dataset

# ============================================================================
# CORE LLM / TEXT EVALUATION - QUESTION ANSWERING
# ============================================================================

# SQuAD v1 - Extractive QA over Wikipedia passages (100K+ questions)
squad = load_dataset("rajpurkar/squad")
# >>> squad
# {'train': (87599, 5), 'validation': (10570, 5)}

# SQuAD v2 - 150K+ question-answer pairs with unanswerable questions
squad_v2 = load_dataset("rajpurkar/squad_v2")
# >>> squad_v2  
# {'train': (130319, 5), 'validation': (11873, 5)}

# WikiQA - Open-domain QA from Microsoft
wiki_qa = load_dataset("microsoft/wiki_qa")
# >>> wiki_qa
# Question answering over Wikipedia

# CoQA - Conversational QA (multi-turn dialog)
coqa = load_dataset("stanfordnlp/coqa")
# >>> coqa
# Conversational question answering

# QuAC - Question Answering in Context (dialog QA)
quac = load_dataset("allenai/quac")
# >>> quac
# Information-seeking dialog QA

# CommonsenseQA - Multiple-choice commonsense reasoning
commonsense_qa = load_dataset("tau/commonsense_qa")
# >>> commonsense_qa
# {'train': (9741, 5), 'validation': (1221, 5)}

# Natural Questions - 307K real Google search questions
natural_questions = load_dataset("google-research-datasets/natural_questions", streaming=True)
# >>> natural_questions
# Real user questions with Wikipedia answers


# ============================================================================
# MATH & REASONING DATASETS
# ============================================================================

# MathQA - Math word problems with rationale
math_qa = load_dataset("allenai/math_qa")
# >>> math_qa
# Math word problems with step-by-step solutions

# DeepMind Math - Generated arithmetic & mathematical reasoning
deepmind_math = load_dataset("deepmind/math_dataset", "algebra__linear_1d")
# >>> deepmind_math
# Various math problem types: algebra, arithmetic, calculus, etc.

# StackMathQA - ~2M math Q&A from StackExchange
stack_math_qa = load_dataset("math-ai/StackMathQA", streaming=True)
# >>> stack_math_qa
# Large-scale math Q&A corpus

# GSM8K - Grade school math word problems
gsm8k = load_dataset("openai/gsm8k", "main")
# >>> gsm8k
# {'train': (7473, 2), 'test': (1319, 2)}


# ============================================================================
# ALIGNMENT & SAFETY EVALUATION
# ============================================================================

# HHH Alignment - Helpful, Honest & Harmless evaluation
hhh_alignment = load_dataset("HuggingFaceH4/hhh_alignment")
# >>> hhh_alignment
# Alignment evaluation for helpfulness, honesty, harmlessness

# TruthfulQA - Evaluating model truthfulness
truthful_qa = load_dataset("truthfulqa/truthful_qa", "generation")
# >>> truthful_qa
# Questions to test if models generate truthful answers


# ============================================================================
# LARGE-SCALE TEXT DATASETS (for pretraining/fine-tuning)
# ============================================================================

# C4 (Colossal Clean Crawled Corpus) - 365GB of cleaned web text
c4 = load_dataset("allenai/c4", "en", streaming=True)
# >>> c4
# Over 300M documents - use streaming!

# OpenWebText - 38GB of Reddit-quality web content
openwebtext = load_dataset("Skylion007/openwebtext", streaming=True)
# >>> openwebtext
# Over 8 million documents

# Wikipedia - Full English Wikipedia dump
wikipedia = load_dataset("wikipedia", "20220301.en", streaming=True)
# >>> wikipedia  
# Over 6 million articles

# RedPajama - High-quality pretraining corpus sample
redpajama = load_dataset("togethercomputer/RedPajama-Data-1T-Sample", streaming=True)
# >>> redpajama
# Sample of the full 1.2T token corpus


# ============================================================================
# NLP BENCHMARKS
# ============================================================================

# GLUE - General Language Understanding Evaluation
glue_mnli = load_dataset("nyu-mll/glue", "mnli")
# >>> glue_mnli
# {'train': (392702, 5), 'validation_matched': (9815, 5)}

# SuperGLUE - More challenging language understanding
superglue = load_dataset("aps/super_glue", "cb")
# >>> superglue
# Challenging NLU tasks

# RACE - Reading Comprehension from Examinations
race = load_dataset("ehovy/race", "all")
# >>> race
# {'train': (87866, 5), 'validation': (4887, 5), 'test': (4934, 5)}

# BoolQ - Yes/No question answering
boolq = load_dataset("google/boolq")
# >>> boolq
# {'train': (9427, 3), 'validation': (3270, 3)}


# ============================================================================
# AUDIO / SPEECH DATASETS
# ============================================================================

# LibriSpeech - 1000 hours of English speech
librispeech = load_dataset("librispeech_asr", "clean", streaming=True)
# >>> librispeech
# High-quality speech recognition corpus

# GTZAN - Music genre classification (1000 tracks, 10 genres)
gtzan = load_dataset("marsyas/gtzan", "all")
# >>> gtzan
# Music genre classification benchmark

# Common Voice - Mozilla's multilingual speech corpus
common_voice = load_dataset("mozilla-foundation/common_voice_11_0", "en", streaming=True)
# >>> common_voice
# Crowdsourced speech data in many languages

# MECAT-QA - Audio clips with QA pairs & captioning
# mecat_qa = load_dataset("mispeech/MECAT-QA")
# >>> Audio QA dataset (check availability)

# AudioQA-1M - Large audio QA dataset
# audio_qa = load_dataset("VITA-MLLM/AudioQA-1M", streaming=True)
# >>> Large-scale audio QA (check availability)


# ============================================================================
# MULTI-MODAL / VISUAL QA DATASETS
# ============================================================================

# VQA v2 - Visual Question Answering
vqa_v2 = load_dataset("HuggingFaceM4/VQAv2", streaming=True)
# >>> vqa_v2
# Questions about images

# Flickr30k - 31K images with 5 captions each
flickr30k = load_dataset("nlphuji/flickr30k")
# >>> flickr30k
# {'test': (31014, 3)} - Each image has 5 captions

# Conceptual Captions - 3.3M image-text pairs
conceptual_captions = load_dataset("google-research-datasets/conceptual_captions")
# >>> conceptual_captions
# {'train': (3318333, 2), 'validation': (15840, 2)}

# VideoMathQA - Math QA grounded in video
# video_math_qa = load_dataset("MBZUAI/VideoMathQA")
# >>> Visual & textual math QA over videos (check availability)


# ============================================================================
# LARGE-SCALE IMAGE DATASETS
# ============================================================================

# COCO - 330K images with rich annotations
coco = load_dataset("detection-datasets/coco")
# >>> coco
# {'train': (118287, 7), 'validation': (5000, 7)}

# RESISC45 - Remote Sensing Image Classification (31K images)
resisc45 = load_dataset("timm/resisc45")
# >>> resisc45  
# {'train': (25200, 2), 'validation': (6300, 2)}

# Food-101 - 101K food images across 101 categories
food101 = load_dataset("food101")
# >>> food101
# {'train': (75750, 2), 'validation': (25250, 2)}

# Oxford Flowers 102 - 8K flower images
flowers102 = load_dataset("nelorth/oxford-flowers")
# >>> flowers102
# {'train': (1020, 2), 'validation': (1020, 2), 'test': (6149, 2)}


# ============================================================================
# CODE DATASETS
# ============================================================================

# CodeSearchNet - 6M functions with documentation
codesearchnet = load_dataset("code_search_net", "python")
# >>> codesearchnet
# {'train': (412178, 7), 'validation': (23107, 7), 'test': (22176, 7)}

# APPS - 10K programming problems
apps = load_dataset("codeparrot/apps")
# >>> apps
# {'train': (5000, 8), 'test': (5000, 8)}

# HumanEval - Code generation benchmark
humaneval = load_dataset("openai/humaneval")
# >>> humaneval
# 164 hand-written programming problems


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

# SciQ - Science exam questions
sciq = load_dataset("allenai/sciq")
# >>> sciq
# {'train': (11679, 5), 'validation': (1000, 5), 'test': (1000, 5)}


# ============================================================================
# SENTIMENT / REVIEWS DATASETS
# ============================================================================

# Yelp Reviews - 700K restaurant reviews
yelp = load_dataset("yelp_review_full")
# >>> yelp
# {'train': (650000, 2), 'test': (50000, 2)}

# IMDB - 50K movie reviews for sentiment analysis
imdb = load_dataset("stanfordnlp/imdb")
# >>> imdb
# {'train': (25000, 2), 'test': (25000, 2)}

# Amazon Reviews - Product reviews (multiple categories)
amazon_polarity = load_dataset("fancyzhx/amazon_polarity")
# >>> amazon_polarity
# Millions of product reviews with ratings


# ============================================================================
# SMALLER DATASETS (for quick prototyping)
# ============================================================================

# MNIST - 60K training images (28x28 grayscale)
mnist = load_dataset("ylecun/mnist")

# CIFAR-10 - 50K training images (32x32 RGB)
cifar10 = load_dataset("uoft-cs/cifar10")

# CIFAR-100 - 50K training images with 100 classes  
cifar100 = load_dataset("uoft-cs/cifar100")

# Fashion-MNIST - 60K training images of fashion items
fashion_mnist = load_dataset("zalando-datasets/fashion_mnist")

# AG News - 120K news articles across 4 categories
ag_news = load_dataset("fancyzhx/ag_news")


# ============================================================================
# TABULAR + TEXTUAL QA
# ============================================================================

# TAT-QA - Tabular and textual QA (numeric reasoning)
# tat_qa = load_dataset("tau/tat_qa")
# >>> Requires reading tables + text for QA (check availability)

# WikiTableQuestions - QA over Wikipedia tables
wiki_table_questions = load_dataset("Stanford/web_questions")
# >>> QA requiring table understanding


# ============================================================================
# EXAMPLE: HOW TO USE STREAMING FOR VERY LARGE DATASETS
# ============================================================================

# For datasets that are too large to fit in memory, use streaming=True

from torch.utils.data import DataLoader

# Load dataset in streaming mode
dataset = load_dataset("allenai/c4", "en", split="train", streaming=True)

# Shuffle and take first N examples
dataset = dataset.shuffle(seed=42, buffer_size=10000).take(100000)

# Can iterate directly
for example in dataset:
    text = example["text"]
    # Process example
    break


# ============================================================================
# TIPS FOR USING DATASETS
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
   
5. LEVERAGE YOUR HARDWARE - You have 24GB VRAM per GPU:
   - Can use batch sizes of 16-64 for most models
   - Can load medium-large models (up to ~7B parameters with quantization)
   - Can cache significant portions of datasets in memory
   
6. PARALLEL LOADING with DataLoader:
   dataloader = DataLoader(dataset, batch_size=64, num_workers=8, pin_memory=True)

7. *** AVOID GATED DATASETS ***
   - Do NOT use datasets that show "Gated" on HuggingFace
   - Do NOT use datasets requiring Terms of Service acceptance
   - Stick to publicly accessible datasets listed above
"""
