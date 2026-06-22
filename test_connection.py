# test_connection.py
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# عميل مشترك (نفس الـ endpoint)
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("RED_API_VERSION"),
)

def test_model(deployment_name, label):
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "user", "content": "Say: Connection successful"}],
      
    )
    print(f"{label}: ✅ {response.choices[0].message.content}")
    print(f"   Tokens: {response.usage.total_tokens}\n")

print("=== اختبار الاتصال بالمودلين ===\n")
test_model(os.getenv("RED_DEPLOYMENT_NAME"), "🔴 Red Agent (GPT-4o)")
test_model(os.getenv("BLUE_DEPLOYMENT_NAME"), "🔵 Blue Agent (gpt-5.2)")
print("=== اكتمل الاختبار ===")
