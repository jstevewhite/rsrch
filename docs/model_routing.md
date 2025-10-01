# MRS Model Routing - Intent + Heuristics Implementation

## Overview

The research pipeline now supports **content-aware model routing** for the Multi-Resource Summarizer (MRS) stage. This allows different AI models to be used based on the type of content being summarized (research papers, code documentation, news articles, etc.).

## Architecture

### 1. Content Type Detection (`stages/content_detector.py`)

Uses URL heuristics to classify content into five categories:

- **RESEARCH**: Academic papers, journals (arXiv, PLOS, Nature, IEEE, etc.)
- **CODE**: Developer resources (GitHub, Stack Overflow, PyPI, etc.)
- **NEWS**: Media outlets (NYT, Reuters, TechCrunch, Wired, etc.)
- **DOCUMENTATION**: Technical docs (docs.*, developer.*, api.*, etc.)
- **GENERAL**: Everything else (fallback)

```python
from stages.content_detector import ContentPatterns, ContentType

# Detect content type from URL
content_type = ContentPatterns.detect_from_url("https://arxiv.org/abs/2301.00001")
# Returns: ContentType.RESEARCH
```

### 2. Model Selection

The configuration supports content-specific models with graceful fallback:

```
MRS_MODEL_DEFAULT → Used when no content-specific model is configured
       ↓
MRS_MODEL_[TYPE] → Used if configured for detected content type
       ↓
MRS_MODEL_GENERAL → Fallback if content-specific model not configured
       ↓
MRS_MODEL_DEFAULT → Final fallback
```

## Configuration

### `.env` File

```env
# Multi-Resource Summarizer (MRS) Model Configuration
# Default model used when no content type is specified
MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507

# Content-Specific MRS Models (optional)
# Uncomment and configure models for different content types:
# MRS_MODEL_CODE=deepseek/deepseek-v3.2-exp        # For Stack Overflow, GitHub, code documentation
# MRS_MODEL_RESEARCH=openai/o3-mini                 # For arXiv, research papers, academic content
# MRS_MODEL_NEWS=openai/gpt-oss-120b                # For news articles, blogs, media
# MRS_MODEL_DOCUMENTATION=qwen/qwen3-next-80b-a3b-instruct  # For technical documentation
# MRS_MODEL_GENERAL=qwen/qwen3-30b-a3b-instruct-2507 # Fallback for general content

# How content type detection works:
# 1. URL heuristics check domain patterns (arxiv.org -> research, github.com -> code)
# 2. Falls back to MRS_MODEL_DEFAULT if no content-specific model is configured
# 3. Uses MRS_MODEL_GENERAL if configured, otherwise MRS_MODEL_DEFAULT
```

### Example Configurations

#### Scenario 1: Basic Setup (Use Default for Everything)
```env
MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507
```

#### Scenario 2: Specialized Models for Research & Code
```env
MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507
MRS_MODEL_RESEARCH=openai/o3-mini                 # Better for academic content
MRS_MODEL_CODE=deepseek/deepseek-v3.2-exp         # Optimized for code
```

#### Scenario 3: Full Customization
```env
MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507
MRS_MODEL_CODE=deepseek/deepseek-v3.2-exp
MRS_MODEL_RESEARCH=openai/o3-mini
MRS_MODEL_NEWS=openai/gpt-oss-120b
MRS_MODEL_DOCUMENTATION=qwen/qwen3-next-80b-a3b-instruct
MRS_MODEL_GENERAL=qwen/qwen3-30b-a3b-instruct-2507
```

## URL Pattern Matching

### Research Domains
- arxiv.org
- scholar.google
- plos.org
- nature.com
- science.org
- ieee.org
- acm.org
- pubmed.ncbi
- doi.org
- jstor.org
- researchgate.net
- biorxiv.org, medrxiv.org

### Code Domains
- github.com
- gitlab.com
- stackoverflow.com
- stackexchange.com
- bitbucket.org
- pypi.org
- npmjs.com
- crates.io (Rust)
- packagist.org (PHP)
- rubygems.org (Ruby)
- maven.org
- nuget.org

### News Domains
- nytimes.com
- apnews.com (Associated Press)
- reuters.com
- bbc.com
- cnn.com
- theguardian.com
- washingtonpost.com
- wsj.com (Wall Street Journal)
- bloomberg.com
- ft.com (Financial Times)
- npr.org
- axios.com
- politico.com
- techcrunch.com
- theverge.com
- wired.com
- arstechnica.com

### Documentation Patterns
- URLs containing: `docs.`, `documentation`, `developer.`, `dev.`, `api.`, `reference`, `manual`, `wiki`

## Implementation Details

### Summarizer Changes

The `Summarizer` class now accepts a `model_selector` callback:

```python
summarizer = Summarizer(
    llm_client=llm_client,
    default_model=config.mrs_model_default,
    model_selector=config.get_mrs_model_for_content_type,
)
```

Model selection happens for each URL being summarized:

```python
def _select_model(self, url: str) -> str:
    """Select the appropriate model based on URL content type."""
    if not self.model_selector:
        return self.default_model
    
    # Detect content type from URL
    content_type = ContentPatterns.detect_from_url(url)
    
    # Get model for content type
    model = self.model_selector(content_type.value)
    
    return model
```

### Config Changes

New configuration fields:

```python
@dataclass
class Config:
    # ... existing fields ...
    
    # MRS model routing
    mrs_model_default: str
    mrs_model_code: Optional[str]
    mrs_model_research: Optional[str]
    mrs_model_news: Optional[str]
    mrs_model_documentation: Optional[str]
    mrs_model_general: Optional[str]
    
    def get_mrs_model_for_content_type(self, content_type: str) -> str:
        """Get the appropriate MRS model for a content type."""
        # Implementation handles fallback logic
```

## Testing

Run the content detection tests:

```bash
python test_detector.py
```

Expected output:
```
================================================================================
CONTENT TYPE DETECTION TESTS
================================================================================

✓ https://arxiv.org/abs/2301.00001
  Expected: research, Got: research
✓ https://stackoverflow.com/questions/12345
  Expected: code, Got: code
✓ https://nytimes.com/article
  Expected: news, Got: news
...

Results: 9 passed, 0 failed
```

## Future Enhancements

### Expandable Pattern Lists

The pattern lists in `content_detector.py` are designed to be easily extended:

```python
class ContentPatterns:
    # Add more domains as needed
    RESEARCH_DOMAINS: Set[str] = {
        'arxiv.org',
        'scholar.google',
        # Add new academic sites here
    }
    
    CODE_DOMAINS: Set[str] = {
        'github.com',
        'stackoverflow.com',
        # Add new code sites here
    }
    
    NEWS_DOMAINS: Set[str] = {
        'nytimes.com',
        'reuters.com',
        # Add new news sites here
    }
```

### Intent-Based Detection (Future)

Currently uses URL heuristics only. Future versions could analyze:
- HTML metadata (article type, OpenGraph tags)
- Content structure (code blocks, citations, references)
- Page layout patterns
- Semantic analysis of titles and snippets

### Model Performance Tracking

Future enhancement: Log which models are used and track their performance:

```python
# Track model usage
logger.info(f"Using {model} for {content_type.value} content: {url}")

# Could add metrics
metrics.record_model_usage(
    model=model,
    content_type=content_type.value,
    url=url,
    token_count=summary_tokens,
)
```

## Benefits

1. **Cost Optimization**: Use cheaper models for simple content, expensive models for complex content
2. **Quality Improvement**: Specialized models (e.g., DeepSeek for code) produce better results
3. **Flexibility**: Easy to experiment with different model combinations
4. **Graceful Degradation**: Falls back to default model if content-specific model not configured
5. **Transparency**: Logs model selection for debugging and monitoring

## Migration Guide

### From Old Config

Old configuration:
```env
MRS_MODEL=qwen/qwen3-30b-a3b-instruct-2507
```

New configuration:
```env
MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507
```

**Note**: The pipeline will use `MRS_MODEL_DEFAULT` for all content types unless you configure content-specific models.

### Adding Content-Specific Models

1. Choose models for specific content types
2. Uncomment and set them in `.env`:
   ```env
   MRS_MODEL_RESEARCH=openai/o3-mini
   MRS_MODEL_CODE=deepseek/deepseek-v3.2-exp
   ```
3. Test with mixed content to verify routing works
4. Monitor logs to see which models are being used

## Troubleshooting

### Model Not Being Used

Check the logs for model selection:

```
DEBUG:stages.summarizer:Selected model 'openai/o3-mini' for content type 'research' (URL: https://arxiv.org/...)
```

If you don't see this, ensure:
1. The content type is being detected correctly (test with `test_detector.py`)
2. The model is configured in `.env`
3. The environment variable is loaded properly

### Content Type Not Detected

Add the domain to the appropriate pattern list in `stages/content_detector.py`:

```python
RESEARCH_DOMAINS: Set[str] = {
    'arxiv.org',
    'your-new-site.org',  # Add here
}
```

### Wrong Model Being Selected

Check the fallback chain:
1. Is the content-specific model configured?
2. Is the general fallback model configured?
3. Is the default model set correctly?

Enable DEBUG logging to trace model selection:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

### Heuristic Speed

URL-based detection is extremely fast (<1ms per URL) with no API calls required.

### Model Switching Overhead

The model selection happens per-URL, not per-chunk, so the overhead is minimal even for map-reduce summarization.

### Cost Management

Example cost strategy:

```env
MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507  # Cheap
MRS_MODEL_RESEARCH=openai/o3-mini                    # Expensive but accurate
MRS_MODEL_CODE=deepseek/deepseek-v3.2-exp            # Specialized
MRS_MODEL_GENERAL=qwen/qwen3-30b-a3b-instruct-2507   # Cheap fallback
```

This configuration uses expensive models only for research papers where quality matters most.
