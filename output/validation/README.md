# LLM Model Validation Benchmarks

This directory contains benchmark files for evaluating different LLM models' performance in recipe extraction from Instagram captions.

## Files Structure

- `summary.md` - Overview of model performance statistics and evaluation guidelines
- `recipe_01.md` through `recipe_05.md` - Individual recipe evaluations with model outputs

## Usage

These files are optimized for evaluation by external powerful LLMs to score and compare model performance across different metrics including:

- Recipe structure completeness
- Ingredient parsing accuracy  
- Step clarity and logical ordering
- Language quality (for German recipes)
- Data consistency and formatting
- Information extraction from Instagram captions

## Auto-Generation

These files are automatically generated when the main processing pipeline completes, selecting 5 random recipes that have been processed by at least 3 different models.
