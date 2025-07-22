import os
from langchain_openai import ChatOpenAI  # Changed import
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()

# It's better to get the API key from environment variables
# as good practice for security and deployment.
try:
    # OpenAI API key is usually named OPENAI_API_KEY
    api_key = os.environ["OPENAI_API_KEY"] 
except KeyError:
    raise ValueError("OPENAI_API_KEY environment variable not set. Please set it to your OpenAI API key.")

# Initialize the GPT-4.1 nano model
# Model name changed to "gpt-4.1-nano"
# The API key parameter for OpenAI is automatically picked up from OPENAI_API_KEY
llm = ChatOpenAI(model="gpt-4.1-nano") 

# Define your message
message = HumanMessage(content="do you know my name? Reply in 1 word")

# Get the response from the model
response = llm.invoke([message])

# Print the response
print(response.content)