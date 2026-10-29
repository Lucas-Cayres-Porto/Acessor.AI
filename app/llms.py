import os
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from app.config import GEMINI_API_KEY, GROQ_API_KEY, NVIDIA_API_KEY
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI



llm_especialista = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.7,
    top_p=0.9,
    google_api_key=GEMINI_API_KEY
)

llm_groq = ChatGroq(
    # model="llama-3.1-8b-instant",
    # max_tokens=60,
    model="openai/gpt-oss-20b",
    temperature=0.7,
    reasoning_format="hidden",
    api_key=GROQ_API_KEY
)

llm_rapido = ChatGroq(
    # model="llama-3.1-8b-instant",
    # max_tokens=60,
    model="openai/gpt-oss-20b",
    temperature=0.0,
    reasoning_format="hidden",
    api_key=GROQ_API_KEY
)

# llm_rapido = ChatOpenAI(
#         model="z-ai/glm-5.3-flash",
#         base_url="https://integrate.api.nvidia.com/v1",
#         api_key=NVIDIA_API_KEY,
#         temperature=0.5,
#         top_p=1,
#         max_tokens=1024,
# )

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview",
    google_api_key=GEMINI_API_KEY
)

llm = llm_especialista.with_fallbacks([llm_groq])