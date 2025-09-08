# **Instagram to Samsung Food Recipe Parser**

This project provides a complete Python solution to process your Instagram saved collections, extract food-related posts, structure them into detailed recipes using a local LLM, and generate public web pages for easy import into services like Samsung Food.

## **Features**

* **Modular Codebase**: The project is split into logical modules for configuration, parsing, data fetching, LLM interaction, and page generation.  
* **Structured Data Extraction**: Uses a local LLM (like Llama 3 or Gemma 3\) with Pydantic to enforce a strict, detailed JSON schema for recipes.  
* **Samsung Food Optimized**: The schema includes optional fields for prep time, cook time, servings, notes, and grouped ingredients, based on Samsung Food's best practices.  
* **Automatic Page Generation**: Creates a clean, public Telegra.ph page for each recipe, providing a URL perfect for Samsung Food's "import from website" feature.  
* **Resumable Progress**: Automatically saves progress after each major step. If the script is interrupted, it will resume where it left off, avoiding redundant work.  
* **Robust Error Handling**: Logs failures and skips problematic posts, ensuring the script can run through large collections.

## **Project Structure**

The project is organized into several Python modules for clarity and maintainability:

* main.py: The main entry point that orchestrates the entire process.  
* config.py: Contains all user-configurable settings like file paths and model names.  
* models.py: Defines the Pydantic data models that enforce the recipe schema.  
* instagram\_parser.py: Handles loading and parsing your saved\_collections.json file.  
* caption\_fetcher.py: Manages the web scraping logic to get post captions.  
* llm\_processor.py: Contains the logic for interacting with the Ollama LLM.  
* page\_generator.py: Creates the public recipe pages using the Telegra.ph API.  
* utils.py: Provides helper functions for file I/O and progress management.  
* requirements.txt: Lists all the necessary Python packages.

## **Setup**

### **1\. Install Ollama and a Model**

Follow the guide below to install Ollama on your machine and download a powerful language model. llama3 is highly recommended for its excellent ability to follow JSON formatting instructions.

* **Install Ollama**: Download and install from [ollama.com](https://ollama.com/).  
* **Pull a Model**: Open your terminal or command prompt and run:  
  ollama pull llama3

* **Ensure Ollama is Running**: The Ollama application must be running in the background for the script to connect to it.

### **2\. Set Up the Python Environment**

* **Prerequisites**: Python 3.11+ is required.  
* **Project Files**: Place all the project files (main.py, config.py, etc.) into a single folder.  
* **Install Dependencies**: Open a terminal in your project folder and run the following command to install the required Python packages:  
  pip install \-r requirements.txt

## **How to Use**

1. **Get Your Instagram Data**:  
   * Request your data download from Instagram (Settings \-\> Accounts Center \-\> Your information and permissions \-\> Download your information).  
   * Choose the **JSON** format.  
   * Once downloaded, find the saved\_collections.json file inside the saved directory and place it in your project folder.  
2. **Configure the Script**:  
   * Open config.py.  
   * Verify the COLLECTION\_NAME. The default is "Food". Change it if your collection has a different name.  
   * Ensure the INPUT\_JSON\_PATH points to your Instagram data file.  
3. **Run the Script**:  
   * Execute the main script from your terminal:  
     python main.py

The script will now begin processing. You will see progress updates in the console.

## **Output Files**

* **samsung\_food\_recipes.json**: The final, structured JSON file containing all successfully processed recipes, including their new public Telegra.ph URL.  
* **processing\_progress.json**: A cache file that stores the state of the script. You can safely delete this to start the process from scratch.  
* **failed.log**: A log of any posts that could not be processed, with details about the error.