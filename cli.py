#!/usr/bin/env python3
"""Command-line interface for the research pipeline."""

import sys
import logging
import argparse
from pathlib import Path

from rsrch.config import Config
from rsrch.pipeline import ResearchPipeline


class ColoredFormatter(logging.Formatter):
    """Logging formatter that adds color to console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[91m',      # Bright Red
        'CRITICAL': '\033[1;91m', # Bold Bright Red
        'RESET': '\033[0m',       # Reset
    }
    
    def format(self, record):
        # Add color to levelname for console output
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging(level: str = "INFO"):
    """Configure logging with colored console output."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    # Console handler with color
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    
    # File handler without color
    file_handler = logging.FileHandler("research_pipeline.log")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    
    logging.basicConfig(
        level=numeric_level,
        handlers=[console_handler, file_handler],
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
    parser.add_argument(
        "--enable-two-pass",
        action="store_true",
        help="Enable two-pass report generation with verification-based revision (requires --verify)",
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
        
        # Override two-pass if specified
        if args.enable_two_pass:
            if not config.verify_claims:
                logger.error("--enable-two-pass requires VERIFY_CLAIMS=true in .env")
                sys.exit(1)
            config.enable_two_pass = True
            logger.info("Two-pass report generation enabled")
        
        # Initialize pipeline
        logger.info("Initializing research pipeline...")
        pipeline = ResearchPipeline(config)
        
        # Run pipeline
        logger.info(f"Processing query: {args.query}")
        print(f"\n{'='*80}")
        print(f"Research Pipeline")
        print(f"{'='*80}")
        print(f"Query: {args.query}\n")
        
        report = pipeline.run(args.query, show_plan=args.show_plan)
        
        print(f"\n{'='*80}")
        print(f"Report Generated Successfully")
        print(f"{'='*80}")
        
        # Build report filename
        report_filename = f"report_{report.generated_at.strftime('%Y%m%d_%H%M%S')}.md"
        report_path = config.output_dir / report_filename
        print(f"Report saved to: {report_path}")
        
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
