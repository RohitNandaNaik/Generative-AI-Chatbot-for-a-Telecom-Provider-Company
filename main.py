from flask import Flask, render_template, request, jsonify  
import pandas as pd
import requests  
from dotenv import load_dotenv 
import os
import json

load_dotenv()
app = Flask(__name__)

# Load Data -----------------------------------------------------------------
def load_data():  
    hardware_df = pd.read_excel("data/Hardware_Product_Data.xlsx")
    infra_faq_df = pd.read_excel("data/Infra_FAQ_Data.xlsx")
    maintenance_df = pd.read_excel("data/Installation_Maintenance_Data.xlsx")
    billing_faq_df = pd.read_excel("data/Billing_Payments_FAQ_Data.xlsx")
    
    return hardware_df, infra_faq_df, maintenance_df, billing_faq_df

hardware_df, infra_faq_df, maintenance_df, billing_faq_df = load_data()

# Prepare contexts ----------------------------------------------------------------------------------------

faq_dict = dict(zip(infra_faq_df['Question'], infra_faq_df['Answer']))

hardware_context = "\n".join([
    f"Product: {row['Name']} | Type: {row['Type']} | Model: {row['Model']} | Support: {row['SupportContact']} | Warranty: {row['Warranty']}"
    for _, row in hardware_df.iterrows()
])

maintenance_context = "\n".join([
    f"Task: {row['Task Name']} | Estimated Time: {row['Estimated Time']} | Technicians: {row['Technician Required']} | Support: {row['SupportContact']}"
    for _, row in maintenance_df.iterrows()
])

billing_faq_context = "\n".join([
    f"Q: {row['Question']} \nA: {row['Answer']}"
    for _, row in billing_faq_df.iterrows()
])


# Session memory and feedback -----------------------------------------------------------------------------------------

session_memory = {} 
feedback_log = []    

# GPT function ----------------------------------------------------------------------------

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def generate_response(user_query, session_id="default"):
    feedback_file = "feedback_log.json"
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, "r") as f:
                feedback_list = json.load(f)  
                for fb in feedback_list:
                    if (
                        fb.get("message", "").strip().lower() == user_query.strip().lower()
                        and fb.get("rating") == "👍"
                    ):
                        return fb["response"]
        except Exception as e:
            print(f"[Error reading feedback log]: {e}")

    memory = session_memory.get(session_id, [])

# Build context -----------------------------------------------------------------------------

    context = f"""
You are a friendly and helpful telecom infrastructure customer support chatbot. Keep your replies short, clear, and easy to understand. Avoid technical jargon unless necessary:

=== Hardware Products ===
{hardware_context}

=== FAQs ===
{str(faq_dict)}

=== Installation & Maintenance ===
{maintenance_context}

=== Billing & Payments FAQs ===
{billing_faq_context}

Recent Conversation:
{format_chat_memory(memory)}

User: {user_query}
Assistant:"""
    
#------------------------------------------------------------------------------------------------

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {
                "role": "system",
                "content": "You assist telecom customers with simple, helpful answers using the product and FAQ context provided."
            },
            {
                "role": "user",
                "content": context
            }
        ]
    }

    try:
        response = requests.post(BASE_URL, headers=headers, json=payload)
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
        memory.append({"user": user_query, "bot": answer})
        session_memory[session_id] = memory[-5:]
        return answer

    except Exception as e:
        return f"Sorry, an error occurred: {e}"

def format_chat_memory(memory):
    return "\n".join([f"User: {m['user']}\nAssistant: {m['bot']}" for m in memory])

# Routes ----------------------------------------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    session_id = request.json.get("session_id", "default")
    bot_reply = generate_response(user_message, session_id)
    return jsonify({"response": bot_reply})

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    message = data.get("message")
    response = data.get("response")
    rating = data.get("rating")

    if message and response and rating:
        feedback_entry = {
            "message": message.strip(),
            "response": response.strip(),
            "rating": rating
        }

        feedback_log_path = "feedback_log.json"

        if os.path.exists(feedback_log_path):
            with open(feedback_log_path, "r") as f:
                try:
                    feedback_data = json.load(f)
                except json.JSONDecodeError:
                    feedback_data = []
        else:
            feedback_data = []

        feedback_data.append(feedback_entry)

        with open(feedback_log_path, "w") as f:
            json.dump(feedback_data, f, indent=2)

        return jsonify({"status": "feedback received"})
    else:
        return jsonify({"status": "invalid feedback", "received": data}), 400
    
    #we are getting jsonify from flask, jaonify takes two arguments in a form of key value pair 

# Run -----------------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)