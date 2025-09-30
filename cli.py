#!/usr/bin/env python3
"""Command-line interface for the research pipeline."""

import sys
import logging
import argparse
from pathlib import Path

from config import Config
from pipeline import ResearchPipeline


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("research_pipeline.log"),
        ],
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Research Pipeline - Generate comprehensive reports from queries"
    )
    parser.add_argument(
        "query",
        type=str,
        help="Research query to investigate",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to .env configuration file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for reports (overrides config)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--show-plan",
        action="store_true",
        help="Display the research plan before proceeding",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = Config.from_env(args.config)
        
        # Override output directory if specified
        if args.output:
            config.output_dir = Path(args.output)
        
        # Initialize pipeline
        logger.info("Initializing research pipeline...")
        pipeline = ResearchPipeline(config)
        
        # Run pipeline
        logger.info(f"Processing query: {args.query}")
        print(f"\n{'='*80}")
        print(f"Research Pipeline")
        print(f"{'='*80}")
        print(f"Query: {args.query}\n")
        
        report = pipeline.run(args.query)
        
        print(f"\n{'='*80}")
        print(f"Report Generated Successfully")
        print(f"{'='*80}")
        print(f"Report saved to: {config.output_dir / f'report_{report.generated_at.strftime(\"%Y%m%d_%H%M%S\")}.md'}")
        print(f"\nPreview:")
        print(f"{'-'*80}")
        
        # Print first 500 characters of report
        preview = report.content[:500]
        if len(report.content) > 500:
            preview += "..."
        print(preview)
        print(f"{'-'*80}\n")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        print("\n\nPipeline interrupted by user.")
        return 1
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\n\nError: {e}")
        print("Check research_pipeline.log for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
