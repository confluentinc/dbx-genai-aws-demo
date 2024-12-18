# Databricks notebook source
# MAGIC %md
# MAGIC # Databricks Compound AI Systems - Cookie Agent
# MAGIC
# MAGIC ###The overall goal of this agent is to react to an enriched stream of social media posts and take action based on the sentiment.
# MAGIC ###For a given review the agent is expected to:
# MAGIC - Retrieve details about the store where a review was placed
# MAGIC - Look up latest sales data for given store to figure out best selling product
# MAGIC - Look up other reviews related to that store and product
# MAGIC - Craft an image generation prompt based on those reviews
# MAGIC - Execute a job that uses an open source image generation model to produce and send image

# COMMAND ----------

# DBTITLE 1,Install dependancies
# MAGIC %pip install --quiet -U langchain-community langchain-openai==0.1.19 mlflow==2.15.1 databricks-agents langchain
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Enable MLflow Tracing
import mlflow
mlflow.langchain.autolog(disable=False)

# COMMAND ----------

# DBTITLE 1,Setup Env Variables
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user_email = w.current_user.me().display_name
username = user_email.split("@")[0]

catalog_name = "bakehouse"
schema_name = "ai"

print(catalog_name)

# COMMAND ----------

# DBTITLE 1,Define Compute
import pandas as pd
import yaml

# Ideally grab user warehouse but fallback to anything else available
def get_shared_warehouse():
    w = WorkspaceClient()
    warehouses = w.warehouses.list()
    for wh in warehouses:
        if wh.name.lower() == user_email:
            return wh
    for wh in warehouses:
        if wh.num_clusters > 0:
            return wh 
    raise Exception("Couldn't find any Warehouse to use. Please create a wh first to run the demo and add the id here")

# COMMAND ----------

# DBTITLE 1,Define Unity Catalog Functions as Tools
from langchain_community.tools.databricks import UCFunctionToolkit

wh_id = get_shared_warehouse().id

def get_tools():
    return (
        UCFunctionToolkit(warehouse_id=wh_id)
        # Include functions as tools using their qualified names.
        # You can use "{catalog_name}.{schema_name}.*" to get all functions in a schema.
        .include(f"{catalog_name}.{schema_name}.*")
        .get_tools())

# COMMAND ----------

# DBTITLE 1,Choose LLM for Agent
from langchain_community.chat_models.databricks import ChatDatabricks

llm = ChatDatabricks(endpoint="databricks-meta-llama-3-1-70b-instruct",
    temperature=0.0,
    streaming=False)

# COMMAND ----------

# DBTITLE 1,Define Agent System Prompt
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatDatabricks

#This defines our agent's system prompt. Here we can tell it what we expect it to do and guide it on using specific functions. 

def get_prompt(history = [], prompt = None):
    if not prompt:
            prompt = """You are a helpful assistant for a global company that oversees cookie stores. Your task is to help store owners understand more about their products and sales metrics. You're going to be passed a payload the represents a customer's review and you need to generate a prompt for an image.

            To do this, you first must look up sales for the given store. If the user left reviews 3 or more times, send them a badge featuring their last reviewed cookie. If sentiment is negative, look up the best selling cookie for that store and send them a coupon for that cookie.

            In either case, the prompt should include the cookie that has the most sales in the provided city. To look up the best selling cookie, you can use the following functions:

            franchise_by_city(city) - This returns the franchise_id for the store in a given city. This franchise_id is needed to look up the sales.

            franchise_sales(franchise_id) - This returns the sales for a given franchise_id. You can use this to look up the best selling cookie for a given franchise_id.

            image_gen(prompt) - This will launch a job that creates and saves an image for the provided prompt.

            Return the action taken based on sentiment (i.e. an apology or a thank you) and repeat the prompt that you passed to an image generation model. Explain nothing else. Do not ask the image generation model to include any text in the image. Aim for a nice product photo, 50mm lens, and a blurred background. Be very detailed with the prompt.
            """

    return ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", "{messages}"),
            ("placeholder", "{agent_scratchpad}"),
    ])

# COMMAND ----------

# DBTITLE 1,Collect and Define Agent Objects
from langchain.agents import AgentExecutor, create_openai_tools_agent

prompt = get_prompt()
tools = get_tools()
agent = create_openai_tools_agent(llm, tools, prompt)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# COMMAND ----------

# DBTITLE 1,Define Agent Architecture
from operator import itemgetter
from langchain.schema.runnable import RunnableLambda
from langchain_core.output_parsers import StrOutputParser

agent_str = ({ "messages": itemgetter("messages")} | agent_executor | itemgetter("output") | StrOutputParser())

# COMMAND ----------

# DBTITLE 1,Example Payload

payload = """ Payload: {
  "review": "The cookies were excellent, we'll definitely be coming back!",
  "date": "2024-09-10 14:31:45.596956",
  "franchise_id": "3000020",
  "sentiment": "Positive",
  "franchise": {
    "franchiseID": 3000020,
    "name": "Sapporo Sweets",
    "city": "Sapporo",
    "district": "Pearl District",
    "zipcode": "97209",
    "country": "Japan",
    "size": "L",
    "longitude": -122.6809,
    "latitude": 45.5311,
    "supplierID": 4000019
  }
}"""

# COMMAND ----------

# DBTITLE 1,Call Agent
#Call Agent with example payload

answer=agent_str.invoke({"messages": payload})

# COMMAND ----------

# DBTITLE 1,Log Agent
# Tell MLflow logging where to find your chain.
mlflow.models.set_model(model=agent_str)