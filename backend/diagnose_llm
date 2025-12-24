from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

pdf_data = open("EID.pdf", "rb").read()

parts = [
    types.Part.from_text("Extract the name and date of birth."),
    types.Part.from_bytes(data=pdf_data, mime_type="application/pdf")
]

resp = client.models.generate_content(
    model="models/gemini-2.5-pro",
    contents=[types.Content(role="user", parts=parts)]
)

print(resp.text)
