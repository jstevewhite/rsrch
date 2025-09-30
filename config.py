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
    mrs_model: str
    context_model: str
    reflection_model: str
    report_model: str
    
    # Search Configuration
    serp_api_key: Optional[str]
    rerank_top_k: float
    
    # Vector Database Configuration
    vector_db_path: Path
    embedding_model: str
    
    # Output Configuration
    output_dir: Path
    log_level: str
    
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
            mrs_model=get_optional("MRS_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o-mini")),
            context_model=get_optional("CONTEXT_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o-mini")),
            reflection_model=get_optional("REFLECTION_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o")),
            report_model=get_optional("REPORT_MODEL", os.getenv("DEFAULT_MODEL", "gpt-4o")),
            
            serp_api_key=os.getenv("SERP_API_KEY"),
            rerank_top_k=float(get_optional("RERANK_TOP_K", "0.25")),
            
            vector_db_path=Path(get_optional("VECTOR_DB_PATH", "./research_db.sqlite")),
            embedding_model=get_optional("EMBEDDING_MODEL", "text-embedding-3-small"),
            
            output_dir=Path(get_optional("OUTPUT_DIR", "./reports")),
            log_level=get_optional("LOG_LEVEL", "INFO"),
        )
    
    def ensure_directories(self):
        """Create necessary directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.vector_db_path.parent.mkdir(parents=True, exist_ok=True)
