"""Configuration management for the research pipeline."""

import os
from pathlib import Path
from typing import Optional
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
    serp_api_key: Optional[str]
    rerank_top_k_url: float  # Ratio of search results to scrape (Stage 4.5)
    rerank_top_k_sum: float  # Ratio of summaries to include in report (Stage 7)
    
    # Vector Database Configuration
    vector_db_path: Path
    embedding_model: str
    embedding_url: str
    embedding_api_key: Optional[str]
    
    # Reranker Configuration
    reranker_url: Optional[str]
    reranker_model: Optional[str]
    reranker_api_key: Optional[str]
    use_reranker: bool
    
    # Reflection Configuration
    max_iterations: int  # Maximum research iterations (including initial)
    
    # Output Configuration
    output_dir: Path
    log_level: str
    report_max_tokens: int
    
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
            
            serp_api_key=os.getenv("SERP_API_KEY"),
            rerank_top_k_url=float(get_optional("RERANK_TOP_K_URL", "0.25")),
            rerank_top_k_sum=float(get_optional("RERANK_TOP_K_SUM", "0.25")),
            
            vector_db_path=Path(get_optional("VECTOR_DB_PATH", "./research_db.sqlite")),
            embedding_model=get_optional("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_url=get_optional("EMBEDDING_URL", os.getenv("API_ENDPOINT", "https://api.openai.com/v1")),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("API_KEY")),
            
            reranker_url=os.getenv("RERANKER_URL"),
            reranker_model=os.getenv("RERANKER_MODEL"),
            reranker_api_key=os.getenv("RERANKER_API_KEY"),
            use_reranker=get_optional("USE_RERANKER", "true").lower() in ("true", "1", "yes"),
            
            max_iterations=int(get_optional("MAX_ITERATIONS", "2")),
            
            output_dir=Path(get_optional("OUTPUT_DIR", "./reports")),
            log_level=get_optional("LOG_LEVEL", "INFO"),
            report_max_tokens=int(get_optional("REPORT_MAX_TOKENS", "4000")),
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
