
# Instagram-Recipe Scraper & Web Publisher

A Python 3.12 utility that fetches recipe posts from Instagram, extracts structured cooking data with an LLM, and publishes beautiful recipe cards to a static website.  
It is designed for food bloggers, meal-prep enthusiasts, and anyone who wants to turn social-media food posts into a searchable, shareable recipe library.

---

## 🌟 Core Features
* **Instagram Fetcher** – downloads media & captions from specified accounts or hashtags.  
* **LLM Processor** – converts unstructured captions into JSON-based recipe objects (ingredients, steps, nutrition, etc.).  
* **Site Generator** – builds a static site with SEO-friendly pages and Open Graph previews.  
* **Retry & Caching Logic** – resilient to rate limits and flaky network calls.  
* **Pluggable Models** – switch between local (`llm_processor_lmstudio.py`) or cloud (`llm_processor_gemini.py`) models via config.

---

## 🚀 Quick Start

## Troubleshooting & FAQ
* **Chromedriver errors** – ensure the driver version matches your local Chrome build.
* **Rate-limits / timeouts** – tweak `max_retries` and `retry_delay` in `main.py`.
* **Model X is slow** – use the performance cards to spot bottlenecks; try `phi3:mini` for speed.
