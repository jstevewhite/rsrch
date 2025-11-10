"""Configuration management for the research pipeline."""

import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration for the research pipeline."""
    
    # API Configuration
    api_key: str
    api_endpoint: str
    default_model: str
    
    # Stage-Specific Models
    intent_model: str
    planner_model: str
    mrs_model_default: str
    mrs_model_code: Optional[str]
    mrs_model_research: Optional[str]
    mrs_model_news: Optional[str]
    mrs_model_documentation: Optional[str]
    mrs_model_general: Optional[str]
    context_model: str
    reflection_model: str
    report_model: str
    
    # Search Configuration
    serper_api_key: Optional[str]  # Serper.dev API key (for both search and scraping)
    tavily_api_key: Optional[str]  # Optional: enables higher rate limits
    perplexity_api_key: Optional[str]  # Perplexity Search API key
    search_provider: str  # SERP, TAVILY, or PERPLEXITY
    search_results_per_query: int  # Number of search results to request per query
    rerank_top_k_url: float  # Ratio of search results to scrape (Stage 4.5)
    rerank_top_k_sum: float  # Ratio of summaries to include in report (Stage 7)
    
    # Domain Exclusions
    exclude_domains: List[str]
    
    # Vector Database Configuration
    vector_db_path: Path
    embedding_model: str
    embedding_url: str
    embedding_api_key: Optional[str]

    # Domain exclusions (optional)
    exclude_domains: List[str]
    
    # Reranker Configuration
    reranker_url: Optional[str]
    reranker_model: Optional[str]
    reranker_api_key: Optional[str]
    use_reranker: bool
    
    # Reflection Configuration
    max_iterations: int  # Maximum research iterations (including initial)
    
    # LLM Client Configuration
    llm_max_retries: int  # Maximum retry attempts for empty/invalid LLM responses
    
    # Verification Configuration
    verify_claims: bool  # Enable claim verification stage
    verify_model: str  # Model to use for claim verification
    verify_confidence_threshold: float  # Minimum confidence for flagging
    
    # Prompt Policy Configuration
    prompt_policy_include: bool  # Enable global prompt policy to prevent knowledge cutoff refusals
    
    # Output Configuration
    output_dir: Path
    log_level: str
    report_max_tokens: int
    
    # Rendering/Extraction Flags
    output_format: str  # e.g., "markdown" (affects scraper output preference)
    preserve_tables: bool  # if true, attempt to preserve/emit tables in scraped content
    
    # Summarizer table handling (configurable via env)
    summarizer_enable_table_aware: bool
    summarizer_table_topk_rows: int
    summarizer_table_max_rows_verbatim: int
    summarizer_table_max_cols_verbatim: int
    
    # Parallelization Configuration
    search_parallel: int      # Number of concurrent search queries
    scrape_parallel: int      # Number of concurrent scraping operations
    summary_parallel: int     # Number of concurrent summarization tasks
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Config":
        """Load configuration from environment variables."""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        # Helper to get required env var
        def get_required(key: str) -> str:
            value = os.getenv(key)
            if not value:
                raise ValueError(f"Required environment variable {key} is not set")
            return value
        
        # Helper to get optional env var with default
        def get_optional(key: str, default: str) -> str:
            return os.getenv(key, default)
        
        # Helper for parsing and validating parallel settings
        def get_parallel_setting(key: str, default: str) -> int:
            """Parse and validate parallel setting."""
            val_str = os.getenv(key, default)
            try:
                val = int(val_str)
                if val < 1:
                    raise ValueError(f"{key} must be at least 1, got {val}")
                if val > 32:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"{key} is set to {val}, which is very high. "
                        f"This may cause resource exhaustion or rate limiting."
                    )
                return val
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Invalid value for {key}: '{val_str}'. "
                    f"Must be a positive integer (1-32 recommended). Error: {e}"
                )
        
        # Parse excluded domains (comma-separated)
        exclude_domains_env = os.getenv("EXCLUDE_DOMAINS", "")
        exclude_domains_list = [d.strip().lower() for d in exclude_domains_env.split(',') if d.strip()]
        
        return cls(
            api_key=get_required("API_KEY"),
            api_endpoint=get_optional("API_ENDPOINT", "https://api.openai.com/v1"),
            default_model=get_optional("DEFAULT_MODEL", "gpt-4o-mini"),
            
            intent_model=get_optional("INTENT_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o-mini")),
            planner_model=get_optional("PLANNER_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o")),
            mrs_model_default=get_optional("MRS_MODEL_DEFAULT", os.getenv("DEFAULT_MODEL", "gpt-4o-mini")),
            mrs_model_code=os.getenv("MRS_MODEL_CODE"),
            mrs_model_research=os.getenv("MRS_MODEL_RESEARCH"),
            mrs_model_news=os.getenv("MRS_MODEL_NEWS"),
            mrs_model_documentation=os.getenv("MRS_MODEL_DOCUMENTATION"),
            mrs_model_general=os.getenv("MRS_MODEL_GENERAL"),
            context_model=get_optional("CONTEXT_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o-mini")),
            reflection_model=get_optional("REFLECTION_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o")),
            report_model=get_optional("REPORT_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o")),
            
            serper_api_key=os.getenv("SERPER_API_KEY"),
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
            search_provider=get_optional("SEARCH_PROVIDER", "SERP").upper(),
            search_results_per_query=int(get_optional("SEARCH_RESULTS_PER_QUERY", "10")),
            rerank_top_k_url=float(get_optional("RERANK_TOP_K_URL", "0.3")),
            rerank_top_k_sum=float(get_optional("RERANK_TOP_K_SUM", "0.5")),
            
            # Domain exclusions
            exclude_domains=exclude_domains_list,
            
            vector_db_path=Path(get_optional("VECTOR_DB_PATH", "./research_db.sqlite")),
            embedding_model=get_optional("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_url=get_optional("EMBEDDING_URL", os.getenv("API_ENDPOINT", "https://api.openai.com/v1")),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("API_KEY")),
            reranker_url=os.getenv("RERANKER_URL"),
            reranker_model=os.getenv("RERANKER_MODEL"),
            reranker_api_key=os.getenv("RERANKER_API_KEY"),
            use_reranker=get_optional("USE_RERANKER", "true").lower() in ("true", "1", "yes"),
            
            max_iterations=int(get_optional("MAX_ITERATIONS", "2")),
            
            llm_max_retries=int(get_optional("LLM_MAX_RETRIES", "3")),
            
            verify_claims=get_optional("VERIFY_CLAIMS", "false").lower() in ("true", "1", "yes"),
            verify_model=get_optional("VERIFY_MODEL", "gpt-4o-mini"),
            verify_confidence_threshold=float(get_optional("VERIFY_CONFIDENCE_THRESHOLD", "0.7")),
            
            prompt_policy_include=get_optional("PROMPT_POLICY_INCLUDE", "true").lower() in ("true", "1", "yes"),
            
            output_dir=Path(get_optional("OUTPUT_DIR", "./reports")),
            log_level=get_optional("LOG_LEVEL", "INFO"),
            report_max_tokens=int(get_optional("REPORT_MAX_TOKENS", "4000")),
            
            # New flags
            output_format=get_optional("OUTPUT_FORMAT", "markdown").lower(),
            preserve_tables=get_optional("PRESERVE_TABLES", "true").lower() in ("true", "1", "yes"),
            
            # Summarizer table handling
            summarizer_enable_table_aware=get_optional("ENABLE_TABLE_AWARE", "true").lower() in ("true", "1", "yes"),
            summarizer_table_topk_rows=int(get_optional("TABLE_TOPK_ROWS", "10")),
            summarizer_table_max_rows_verbatim=int(get_optional("TABLE_MAX_ROWS_VERBATIM", "15")),
            summarizer_table_max_cols_verbatim=int(get_optional("TABLE_MAX_COLS_VERBATIM", "8")),
            
            # Parallelization settings with validation
            search_parallel=get_parallel_setting("SEARCH_PARALLEL", "1"),
            scrape_parallel=get_parallel_setting("SCRAPE_PARALLEL", "5"),  # Match current default
            summary_parallel=get_parallel_setting("SUMMARY_PARALLEL", "1"),
        )
    
    def get_mrs_model_for_content_type(self, content_type: str) -> str:
        """Get the appropriate MRS model for a content type.
        
        Args:
            content_type: Content type from ContentType enum (e.g., 'code', 'research')
            
        Returns:
            Model name to use for this content type
        """
        # Map content type to corresponding model attribute
        content_type_map = {
            'code': self.mrs_model_code,
            'research': self.mrs_model_research,
            'news': self.mrs_model_news,
            'documentation': self.mrs_model_documentation,
            'general': self.mrs_model_general,
        }
        
        # Get content-specific model or fall back to general, then default
        model = content_type_map.get(content_type.lower())
        if model:
            return model
        
        # Fall back to general model if configured
        if self.mrs_model_general:
            return self.mrs_model_general
        
        # Final fallback to default
        return self.mrs_model_default
    
    def ensure_directories(self):
        """Create necessary directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.vector_db_path.parent.mkdir(parents=True, exist_ok=True)
