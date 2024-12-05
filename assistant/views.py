from django.shortcuts import render
from openai import OpenAI
from .forms import QuestionForm
from .models import Contact, Conversation, Message
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from environs import Env
import requests

tools = [
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a recipient",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["recipient", "subject", "body"],
            },
        }
    }
]

env = Env()
env.read_env()

DEBUG = True

OPENAI_API_KEY = env("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"
MAX_LEN = 1800
MAX_TOKENS = 300

PROMPT = """Answer the question based on the context below."""

DEBUG = True

def send_email(recipient, subject, body):
    mailgun_domain = env("MAILGUN_DOMAIN")
    mailgun_api_key = env("MAILGUN_API_KEY")
    from_email = env("FROM_EMAIL")

    try:
        print(f"Sending email to: {recipient}, Subject: {subject}, Body: {body}")
        response = requests.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", mailgun_api_key),
            data={"from": from_email, "to": recipient, "subject": subject, "text": body},
        )
        response.raise_for_status()
        return {"status": "success", "details": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "details": str(e)}

def answer_question(
    model=MODEL,
    question="What is your store phone number?",
    max_len=MAX_LEN,
    size="ada",
    debug=False,
    max_tokens=MAX_TOKENS,
    stop_sequence=None,
):
    """
    Answer a question based on the most similar context from the dataframe texts
    """
    context = ""
    # If debug, print the raw model response
    if debug:
        print("Context:\n" + context)
        print("\n\n")

    try:
        # Create a completions using the question and context
        prompt = f"""{PROMPT}```Context: {context}```\n\n---\n\n``Question: {question}```\n Answer:"""

        if debug:
            print(f"\n***\n{prompt}\n***\n")

        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Use the 'send_email' function when the user asks to send an email.",
                },
                {"role": "user", "content": prompt},
            ],
            model=MODEL,
            tools=tools,
            temperature=0,
        )
        message = response.choices[0].message
        answer = message.content
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function.name == "send_email":
                    args = eval(tool_call.function.arguments)  # Parse arguments as a dictionary
                    response = send_email(args["recipient"], args["subject"], args["body"])
                    print(f"Email response: {response}")
        else:
            pass
        if answer == None or answer == "": 
            answer = ""
        return answer
    except Exception as e:
        print(e)
        return ""

@login_required
def home(request):
    
    if request.htmx and request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.cleaned_data.get("question")

            answer = answer_question(question=question, debug=DEBUG)

            if (
                "conversation_id"
                not in request.session
            ):
                user = request.user
                conversation = Conversation.objects.create(
                    title=question, user=user
                )
                request.session["conversation_id"] = conversation.id
            else:
                # This is an existing session, get the current conversation
                conversation_id = request.session["conversation_id"]
                conversation = get_object_or_404(Conversation, id=conversation_id)

            message = Message.objects.create(
                conversation=conversation,
                question=question,
                answer=answer,
                context="",
            )
            

            message.save()
            
            return render(
                request, "answer.html", {"answer": answer, "question": question}
            )
    else:
        form = QuestionForm()
    return render(
        request,
        "home.html",
        {"form": form, "title": "Music Store Assistant"},
    )
