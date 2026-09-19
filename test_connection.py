import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# لاحظ: base_url لازم يوقف عند /openai/v1 بدون /responses بالآخر
client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url="https://wisecoder.services.ai.azure.com/openai/v1",
)

def test_model(deployment_name, label):
    response = client.responses.create(
        model=deployment_name,
        input="Say: Connection successful",
    )
    print(f"{label}: ✅ {response.output_text}")
    print(f"   Deployment requested: {deployment_name}")
    print(f"   Actual model version returned: {response.model}")
    print()
    return response.model

print("=== اختبار الاتصال بالمودلين ===\n")
red_version = test_model(os.getenv("RED_DEPLOYMENT_NAME"), "🔴 Red Agent")
blue_version = test_model(os.getenv("BLUE_DEPLOYMENT_NAME"), "🔵 Blue Agent")
print("=== اكتمل الاختبار ===")
print(f"\nRED_MODEL_VERSION={red_version}")
print(f"BLUE_MODEL_VERSION={blue_version}")
