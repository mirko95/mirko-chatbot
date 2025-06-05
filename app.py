from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import streamlit as st

# Load environment variables
load_dotenv(override=True)

# Pushover notification
def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )

# Function to record an interested user
def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

# Function to record an unknown question
def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}

# Define tools for GPT
record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The email address of this user"},
            "name": {"type": "string", "description": "The user's name, if they provided it"},
            "notes": {"type": "string", "description": "Any additional information about the conversation that's worth recording to give context"}
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question that couldn't be answered"}
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_unknown_question_json}
]

# Main class
class Me:
    def __init__(self):
        self.openai = OpenAI()
        self.name = "Mirko Messina"
        reader = PdfReader("me/CV_ENG.pdf")
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("me/summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()

    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call.id
            })
        return results

    def system_prompt(self):
        return f"""You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
If you don't know the answer to any question, use your record_unknown_question tool to record it. \
If the user is engaging in discussion, try to steer them toward getting in touch via email and record it.

## Summary:
{self.summary}

## LinkedIn Profile:
{self.linkedin}

Stay in character as {self.name}.
"""

    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools
            )
            if response.choices[0].finish_reason == "tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content

# STREAMLIT UI
st.set_page_config(page_title="Mirko Messina AI Chat", page_icon="💬")

# Initialize session
if "me" not in st.session_state:
    st.session_state.me = Me()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Sidebar with profile and contact form
with st.sidebar:
    image_path = "me/profile_photo.png"
    if os.path.exists(image_path):
        st.image(image_path, width=150)
    else:
        st.image("https://via.placeholder.com/150", width=150)

    st.markdown("### 👤 Mirko Messina")
    st.markdown("AI developer and web engineer passionate about building human-friendly tools.")
    st.markdown("📄 [Download CV](https://drive.google.com/file/d/1rWT7HKpBta1RovfErGCdApqu-wRk4RvM/view?usp=drive_link)")
    st.markdown("[🌐 LinkedIn](https://www.linkedin.com/in/mirko-messina95/)")

    with st.form("contact_form"):
        st.markdown("### 📬 Contact Me")
        email = st.text_input("Your email")
        name = st.text_input("Your name")
        notes = st.text_area("Message or notes")
        if st.form_submit_button("Send"):
            if email.strip():
                result = record_user_details(email, name, notes)
                st.success("Message sent!" if result["recorded"] == "ok" else "Something went wrong.")
            else:
                st.warning("Please enter your email.")

# Main Chat Area
st.markdown("<h1 style='text-align: center;'>💬 Chat with Mirko (AI)</h1>", unsafe_allow_html=True)

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])

# User input
user_input = st.chat_input("Type your question here...")

if user_input:
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # Get response
    response = st.session_state.me.chat(user_input, st.session_state.chat_history[:-1])
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(response)
    st.session_state.chat_history.append({"role": "assistant", "content": response})