"""
Chat context utilities for injecting ChatGPT conversation context into reviews.

This module provides utilities to retrieve, truncate, and format chat context
for use in code reviews (node reviews) and final paper reviews.
"""

from typing import Optional

# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4
DEFAULT_MAX_TOKENS = 80_000


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    return len(text) // CHARS_PER_TOKEN


def truncate_chat_to_token_limit(
    chat_text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    preserve_end: bool = True
) -> str:
    """
    Truncate chat to fit within token limit.
    
    By default, preserves the END of the conversation (most recent context)
    and truncates from the beginning.
    
    Args:
        chat_text: The full chat transcript
        max_tokens: Maximum tokens to allow
        preserve_end: If True, keep the end and truncate beginning
        
    Returns:
        Truncated chat text with truncation notice if applicable
    """
    if not chat_text:
        return ""
    
    estimated_tokens = estimate_tokens(chat_text)
    
    if estimated_tokens <= max_tokens:
        return chat_text
    
    # Calculate how many characters we can keep
    max_chars = max_tokens * CHARS_PER_TOKEN
    
    if preserve_end:
        # Keep the end, truncate the beginning
        truncated = chat_text[-max_chars:]
        # Try to find a good break point (newline)
        newline_idx = truncated.find('\n')
        if newline_idx > 0 and newline_idx < 500:
            truncated = truncated[newline_idx + 1:]
        
        truncation_notice = (
            f"[... Earlier conversation truncated ({estimated_tokens - max_tokens:,} tokens removed) "
            f"to fit {max_tokens:,} token limit. Showing most recent context ...]\n\n"
        )
        return truncation_notice + truncated
    else:
        # Keep the beginning, truncate the end
        truncated = chat_text[:max_chars]
        # Try to find a good break point
        last_newline = truncated.rfind('\n')
        if last_newline > max_chars - 500:
            truncated = truncated[:last_newline]
        
        truncation_notice = (
            f"\n\n[... Later conversation truncated ({estimated_tokens - max_tokens:,} tokens removed) "
            f"to fit {max_tokens:,} token limit ...]"
        )
        return truncated + truncation_notice


def format_chat_for_code_generation(chat_text: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """
    Format chat context for injection into code generation prompts.
    
    Args:
        chat_text: The raw chat transcript
        max_tokens: Maximum tokens to include
        
    Returns:
        Formatted chat context with explanation header
    """
    if not chat_text:
        return ""
    
    truncated = truncate_chat_to_token_limit(chat_text, max_tokens)
    
    header = """
=== ORIGINAL CHATGPT CONVERSATION ===

The following is the original ChatGPT conversation that led to this experiment.
Use this context to understand:
- The user's actual goals and intent
- Specific constraints or requirements mentioned
- Expected behaviors or outcomes discussed
- Any domain-specific context or terminology

Your implementation should align with what was discussed in this conversation.

--- CONVERSATION START ---
"""
    
    footer = """
--- CONVERSATION END ---
"""
    
    return header + truncated + footer


def format_chat_for_node_review(chat_text: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """
    Format chat context for injection into node/code review prompts.
    
    Args:
        chat_text: The raw chat transcript
        max_tokens: Maximum tokens to include
        
    Returns:
        Formatted chat context with review-specific explanation
    """
    if not chat_text:
        return ""
    
    truncated = truncate_chat_to_token_limit(chat_text, max_tokens)
    
    header = """
=== ORIGINAL EXPERIMENT CONTEXT (ChatGPT Conversation) ===

The following is the original ChatGPT conversation that generated this experiment request.
When reviewing the code execution results, verify that:

1. **Goal Alignment**: Does the implementation address the goals discussed in the conversation?
2. **Constraint Adherence**: Are the constraints and requirements from the chat being followed?
3. **Expected Behavior**: Do the results match what the user expected based on the discussion?
4. **Methodology Match**: Is the approach consistent with what was discussed?

Flag any significant deviations from the user's stated intent.

--- CONVERSATION START ---
"""
    
    footer = """
--- CONVERSATION END ---
"""
    
    return header + truncated + footer


def format_chat_for_paper_review(chat_text: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """
    Format chat context for injection into final paper review prompts.
    
    Args:
        chat_text: The raw chat transcript
        max_tokens: Maximum tokens to include
        
    Returns:
        Formatted chat context with paper review-specific explanation
    """
    if not chat_text:
        return ""
    
    truncated = truncate_chat_to_token_limit(chat_text, max_tokens)
    
    header = """
=== ORIGINAL EXPERIMENT CONTEXT (ChatGPT Conversation) ===

This is the original ChatGPT conversation that led to this research paper.
When reviewing the paper, assess whether:

1. **Research Question Alignment**: Does the paper address the research questions/hypotheses from the conversation?
2. **Methodology Consistency**: Is the experimental methodology consistent with what was discussed?
3. **Success Criteria**: Are the metrics and evaluation criteria aligned with what was originally intended?
4. **Scope Coverage**: Does the paper cover the aspects the user cared about?
5. **Missing Elements**: Are there important aspects from the conversation that weren't addressed?

Note any gaps between what was discussed and what was actually tested/reported.

--- CONVERSATION START ---
"""
    
    footer = """
--- CONVERSATION END ---
"""
    
    return header + truncated + footer


def get_chat_context_from_hypothesis(hypothesis: dict) -> Optional[str]:
    """
    Extract raw chat text from a hypothesis document.
    
    Args:
        hypothesis: The hypothesis document from MongoDB
        
    Returns:
        The raw extracted chat text, or None if not available
    """
    if not hypothesis:
        return None
    
    # Check for extractedRawText (stored during ChatGPT URL extraction)
    raw_text = hypothesis.get("extractedRawText")
    if raw_text:
        return raw_text
    
    return None

