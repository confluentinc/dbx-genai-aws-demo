# Databricks notebook source
# MAGIC %pip install --quiet -U databricks-sdk==0.23.0 langchain-community langchain-openai==0.1.19 mlflow==2.15.1 databricks-agents
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import EndpointStatusState, EndpointType
from databricks.sdk.service.serving import EndpointCoreConfigInput, EndpointStateReady
from databricks.sdk.errors import ResourceDoesNotExist, NotFound, PermissionDenied
import os

# COMMAND ----------

#Grabs the username without the full email address. 
w = WorkspaceClient()
user_email = w.current_user.me().display_name
username = user_email.split("@")[0]


#Catalog and schema have been automatically created.
catalog_name = "bakehouse"
schema_name = "ai"

# COMMAND ----------

import os
import mlflow
from databricks import agents

# Use the Unity Catalog model registry
mlflow.set_registry_uri('databricks-uc')

# COMMAND ----------

# For this first basic demo, we'll keep the configuration as a minimum. In real app, you can make all your RAG as a param (such as your prompt template to easily test different prompts!)
agent_config = {
    "llm_model_serving_endpoint_name": "databricks-meta-llama-3-1-70b-instruct",  # the foundation model we want to use
    "uc_function_list": f"{catalog_name}.{schema_name}.*",
}

# COMMAND ----------


host = "https://" + spark.conf.get("spark.databricks.workspaceUrl")
display(host)

# COMMAND ----------

import os
import mlflow
from mlflow.models.signature import ModelSignature
from mlflow.models.rag_signatures import ChatCompletionRequest, StringResponse, ChatCompletionResponse

input_example = {"messages": "Create a social media post that promotes the best selling cookie for our Chicago store while showing we listen to customer feedback."}
# Specify the full path to the chain notebook
chain_notebook_file = "2_create_agent"
chain_notebook_path = os.path.join(os.getcwd(), chain_notebook_file)

host = "https://" + spark.conf.get("spark.databricks.workspaceUrl")

print(f"Chain notebook path: {chain_notebook_path}")

def deploy_chain():
  # Log the model to MLflow
  with mlflow.start_run(run_name="cookie_agent"):
    logged_chain_info = mlflow.langchain.log_model(
            #Note: In classical ML, MLflow works by serializing the model object.  In generative AI, chains often include Python packages that do not serialize.  Here, we use MLflow's new code-based logging, where we saved our chain under the chain notebook and will use this code instead of trying to serialize the object.
            lc_model=chain_notebook_path,  # Chain code file e.g., /path/to/the/chain.py 
            model_config=agent_config, # Chain configuration 
            artifact_path="agent", # Required by MLflow, the chain's code/config are saved in this directory
            input_example=input_example,
            example_no_conversion=True,  # Required by MLflow to use the input_example as the chain's schema
            signature=ModelSignature(
            inputs=ChatCompletionRequest(),
            #outputs=ChatCompletionResponse(),
            outputs=StringResponse(),
            ),
            pip_requirements=["langchain", "langchain-community", "langchain-openai"],
        )

  MODEL_NAME = "cookie_agent_demo"
  MODEL_NAME_FQN = f"{catalog_name}.{schema_name}.{MODEL_NAME}"
  # Register to UC
  uc_registered_model_info = mlflow.register_model(model_uri=logged_chain_info.model_uri, name=MODEL_NAME_FQN)

  environment_vars = {
        "DATABRICKS_TOKEN": "{{secrets/current-demo/llm-agent-token}}",
        "DATABRICKS_HOST": host
      }

  environment_vars = dict(environment_vars)

  from databricks import agents
  # Deploy to enable the Review APP and create an API endpoint
  # Note: scaling down to zero will provide unexpected behavior for the chat app. Set it to false for a prod-ready application.
  deployment_info = agents.deploy(MODEL_NAME_FQN, model_version=uc_registered_model_info.version, scale_to_zero=True, environment_vars=environment_vars)

  instructions_to_reviewer = f"""## Instructions for Testing our Databricks Agent with Compound AI system

  Your inputs are invaluable for the development team. By providing detailed feedback and corrections, you help us fix issues and improve the overall quality of the application. We rely on your expertise to identify any gaps or areas needing enhancement."""

  # Add the user-facing instructions to the Review App
  agents.set_review_instructions(MODEL_NAME_FQN, instructions_to_reviewer)

# Uncomment to deploy
deploy_chain()