# **Instagram Recipe Parser**

This project provides a complete Python solution to parse your saved Instagram collections, extract food-related posts, use a local LLM to structure them as recipes, and generate public URLs for easy import into services like Samsung Food.

## **Features**

* **Modular Code**: The project is split into logical modules for configuration, parsing, caption fetching, LLM interaction, and page generation.  
* **Intelligent Caption Scraping**: Uses Selenium to automate a web browser, successfully bypassing cookie and login popups for reliable caption fetching.  
* **Structured LLM Output**: Leverages Pydantic and the ollama library to enforce a strict JSON schema, ensuring clean and predictable recipe data from the LLM.  
* **Automated Progress Saving**: Creates a processing\_progress.json file to track fetched captions, processed recipes, and generated URLs. If the script is stopped, it resumes exactly where it left off, avoiding redundant work.  
* **Public URL Generation**: Automatically creates a public, shareable webpage for each recipe using Telegra.ph, making it easy to import into services that require a URL.  
* **Robust Error Handling**: Includes comprehensive logging to track progress and diagnose issues. Failed posts are logged to failed.log.

## **Setup and Installation**

### **1\. Install Python**

Ensure you have Python 3.11 or newer installed on your system.

### **2\. Install Dependencies**

Navigate to the project directory in your terminal and install the required Python libraries using the requirements.txt file. It's highly recommended to do this within a virtual environment.

\# Create a virtual environment (optional but recommended)  
python \-m venv .venv  
source .venv/bin/activate  \# On Windows use \` .venv\\Scripts\\activate \`

\# Install dependencies  
pip install \-r requirements.txt

The webdriver-manager library will automatically download and manage the correct browser driver (e.g., chromedriver) for you.

### **3\. Set Up a Local LLM with Ollama**

This script requires a local language model to be running and accessible via the Ollama API.

**a. Install Ollama:**

* Go to [ollama.com](https://ollama.com/) and download the installer for your operating system (Windows, macOS, or Linux).  
* Run the installer. Ollama will run as a background service.

**b. Download a Model:**

* For this recipe parsing task, **Llama 3** is highly recommended due to its excellent ability to follow formatting instructions.  
* Open your terminal or command prompt and pull the model:  
  ollama pull llama3

* This will download the model (several gigabytes). You can also try other models like gemma3:12b if you prefer.

**c. Verify the Model is Running:**

* After pulling, ensure the Ollama service is running. You can test it by running ollama list in your terminal to see the downloaded models.

## **How to Use the Script**

1. **Place Your Instagram Data**:  
   * Find the saved\_collections.json file from your official Instagram data export.  
   * Place this file in the root directory of the project.  
2. **Configure the Script**:  
   * Open the config.py file.  
   * Change COLLECTION\_NAME to the exact name of your food collection (e.g., "Food", "Recipes").  
   * Ensure LLM\_MODEL matches the model you downloaded with Ollama (e.g., "llama3").  
3. **Run the Main Script**:  
   * Execute the main.py script from your terminal:  
     python main.py

4. **Check the Output**:  
   * **processing\_progress.json**: This file will be created and updated in real-time as the script works.  
   * **samsung\_food\_recipes.json**: Once the script is finished, this file will contain the final list of all successfully parsed recipes, including their public Telegra.ph URLs.  
   * **failed.log**: Any posts that could not be processed will be logged here for review.  
   * **Terminal**: The script will print its progress, so you can monitor it as it runs.

## **Samsung Food Import**

Since Samsung Food does not offer a batch import feature, you can use the generated Telegra.ph URLs for manual import:

1. Open the final samsung\_food\_recipes.json file.  
2. For each recipe, copy the public\_url.  
3. In Samsung Food, choose the option to add a recipe from a URL and paste the link.