import os
import sys
import json
import logging
from dotenv import load_dotenv

from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Add mcp-server directory to system path for tool imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'mcp-server'))
from job_search import job_search as do_job_search
from resume_analyzer import analyze_resume as do_analyze_resume
from fit_score import get_job_fit_score as do_fit_score

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

# Multi-provider fallback configuration for the orchestrator
# Format: (display_name, base_url, api_key, model)
ORCHESTRATOR_PROVIDERS = [
    (
        "GitHub GPT-4.1 (Primary)",
        "https://models.inference.ai.azure.com",
        os.getenv('GITHUB_TOKEN'),
        "gpt-4.1",
    ),
    (
        "GitHub GPT-4.1 (Backup)",
        "https://models.inference.ai.azure.com",
        os.getenv('GITHUB_TOKEN1'),
        "gpt-4.1",
    ),
    (
        "GitHub GPT-4o (Primary)",
        "https://models.inference.ai.azure.com",
        os.getenv('GITHUB_TOKEN'),
        "gpt-4o",
    ),
    (
        "GitHub GPT-4o (Backup)",
        "https://models.inference.ai.azure.com",
        os.getenv('GITHUB_TOKEN1'),
        "gpt-4o",
    ),
    (
        "OpenRouter Llama-4-Maverick",
        "https://openrouter.ai/api/v1",
        os.getenv('OPENROUTER_API_KEY'),
        "meta-llama/llama-4-maverick:free",
    ),
    (
        "OpenRouter Qwen3-235B",
        "https://openrouter.ai/api/v1",
        os.getenv('OPENROUTER_API_KEY'),
        "qwen/qwen3-235b-a22b:free",
    ),
    (
        "OpenRouter DeepSeek-R1",
        "https://openrouter.ai/api/v1",
        os.getenv('OPENROUTER_API_KEY'),
        "deepseek/deepseek-r1:free",
    ),
    (
        "SambaNova Llama-70B",
        "https://api.sambanova.ai/v1",
        os.getenv('SAMBANOVA_API_KEY'),
        "Meta-Llama-3.3-70B-Instruct",
    ),
]

# Filter providers with valid API keys
ORCHESTRATOR_PROVIDERS = [(n, u, k, m) for (n, u, k, m) in ORCHESTRATOR_PROVIDERS if k]

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "job_search",
            "description": "Search for jobs by role and location using JSearch API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Job title e.g. 'ML Engineer'"},
                    "location": {"type": "string", "description": "City/region e.g. 'Pune, India'"},
                    "num_results": {"type": "integer", "description": "Number of results (1-10, default 5)"}
                },
                "required": ["role", "location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_resume",
            "description": "Analyze a resume against a job description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "Text content of the resume"},
                    "job_description": {"type": "string", "description": "Text content of the job description"}
                },
                "required": ["resume_text", "job_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_fit_score",
            "description": "Calculate a fit score (0-100) between a resume and a job description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "Text content of the resume"},
                    "job_description": {"type": "string", "description": "Text content of the job description"}
                },
                "required": ["resume_text", "job_description"]
            }
        }
    }
]

def execute_tool(tool_name, kwargs):
    try:
        if tool_name == "job_search":
            return str(do_job_search(**kwargs))
        elif tool_name == "analyze_resume":
            return str(do_analyze_resume(**kwargs))
        elif tool_name == "get_job_fit_score":
            return str(do_fit_score(**kwargs))
    except Exception as e:
        return f"Error executing {tool_name}: {e}"
    return "Unknown tool"

active_chats = {}

# Load optional user profile for better context
user_profile = ""
if os.path.exists("my_profile.txt"):
    with open("my_profile.txt", "r", encoding="utf-8") as f:
        user_profile = f.read().strip()

SYSTEM_PROMPT = (
    "You are an autonomous AI Job Scout. Assist users with job discovery and resume analysis. "
    "Maintain a clear and professional tone.\n"
    "CRITICAL RULES:\n"
    "1. Always include the raw apply_link for every job on its own line: Apply: <URL>\n"
    "2. Never truncate or modify URLs.\n"
    "3. If no link is available, use: Apply: N/A\n"
    "4. Search Precision: If the user specifies an experience level (e.g., 1 year, entry level, junior), "
    "   ALWAYS include those keywords (e.g., 'Junior', 'Entry Level') in the 'role' parameter of the job_search tool.\n"
)
if user_profile:
    SYSTEM_PROMPT += f"\nUSER PROFILE (Use this to tailor your results and provide better analysis):\n{user_profile}"

def _call_with_fallback(messages):
    last_error = None
    for name, base_url, api_key, model in ORCHESTRATOR_PROVIDERS:
        try:
            logger.info(f"[Orchestrator] Attempting {name} ({model})")
            client = OpenAI(base_url=base_url, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                max_tokens=2048,
            )
            logger.info(f"[Orchestrator] Success via {name}")
            return response
        except Exception as e:
            logger.warning(f"[Orchestrator] {name} fail: {e}")
            last_error = e
            continue
    raise RuntimeError(f"All providers failed. Last error: {last_error}")

def process_chat(chat_id, user_text):
    if chat_id not in active_chats:
        active_chats[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    messages = active_chats[chat_id]
    messages.append({"role": "user", "content": user_text})

    while True:
        response = _call_with_fallback(messages)
        msg = response.choices[0].message
        
        if msg.tool_calls:
            messages.append(msg)
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                try:
                    kwargs = json.loads(tool_call.function.arguments)
                except Exception:
                    kwargs = {}
                
                result_str = execute_tool(func_name, kwargs)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": result_str
                })
        else:
            messages.append({"role": "assistant", "content": msg.content})
            return msg.content

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Job Scout active. How can I assist your career search?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.message.chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    try:
        response_text = process_chat(chat_id, user_text)
        await update.message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Message handling error: {e}")
        await update.message.reply_text(f"Error: {e}")

def main() -> None:
    port = int(os.getenv("PORT", 8080))
    # Render URL provided by user or environment variable
    url = os.getenv("RENDER_EXTERNAL_URL", "https://openclaw-integrated-mcp-server-for-job.onrender.com")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info(f"Starting webhook on port {port}")
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TELEGRAM_BOT_TOKEN,
        webhook_url=f"{url}/{TELEGRAM_BOT_TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()

