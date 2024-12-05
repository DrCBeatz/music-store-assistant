# answer-question.py

from openai import OpenAI
env = Env()
env.read_env()

expert = "aynmhandbookchat"

OPENAI_API_KEY = env("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"
MAX_LEN = 1800
MAX_TOKENS = 300

PROMPT = """Answer the question based on the context below."""

DEBUG = True

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

        response = client.ChatCompletion.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {"role": "user", "content": prompt},
            ],
            model=MODEL,
            temperature=0,
        )

        answer = response["choices"][0]["message"]["content"].strip()
        return answer
    except Exception as e:
        print(e)
        return ""


def main():
    while True:
        question = input(
            "Ask a question for the Music Store Assistant: "
        )
        answer = answer_question(question=question, debug=False)
        print(answer)


if __name__ == "__main__":
    main()
