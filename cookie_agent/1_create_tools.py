# Databricks notebook source
# MAGIC %md
# MAGIC This notebook creates the functions needed to run the Cookie demo using the data from Marketplace.
# MAGIC
# MAGIC It is assumed that the Marketplace data lives in the databricks_cookies_dais_2024 catalog and that the 'sales' and 'media' schemas exist and can be accessed.
# MAGIC
# MAGIC Run this notebook to create functions *in your own catalog and schema* that reference the data in the Marketplace catalog

# COMMAND ----------

# DBTITLE 1,Create a catalog and schema on your local workspace
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user_email = w.current_user.me().display_name
username = user_email.split("@")[0]

#Catalog and schema have been automatically created.
catalog_name = "bakehouse"
schema_name = "ai"

dbutils.widgets.text("catalog_name", defaultValue=catalog_name, label="Catalog Name")
dbutils.widgets.text("schema_name", defaultValue=schema_name, label="Schema Name")

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG ${catalog_name};
# MAGIC CREATE SCHEMA IF NOT EXISTS ${schema_name};
# MAGIC CREATE VOLUME IF NOT EXISTS ${schema_name}.images;

# COMMAND ----------

# MAGIC %sql
# MAGIC drop function if exists ${catalog_name}.${schema_name}.franchise_by_city;
# MAGIC CREATE OR REPLACE FUNCTION
# MAGIC ${catalog_name}.${schema_name}.franchise_by_city (
# MAGIC   city_name STRING COMMENT 'City to be searched'
# MAGIC )
# MAGIC returns table(franchiseID BIGINT, name STRING, size STRING)
# MAGIC return
# MAGIC (SELECT franchiseID, name, size from databricks_cookies_dais_2024.sales.franchises where city=city_name 
# MAGIC      order by size desc)
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP FUNCTION IF EXISTS ${catalog_name}.${schema_name}.franchise_sales;
# MAGIC CREATE OR REPLACE FUNCTION
# MAGIC ${catalog_name}.${schema_name}.franchise_sales (
# MAGIC   franchise_id BIGINT COMMENT 'ID of the franchise to be searched'
# MAGIC )
# MAGIC returns table(total_sales BIGINT, total_quantity BIGINT, product STRING)
# MAGIC return
# MAGIC (SELECT SUM(totalPrice) AS total_sales, SUM(quantity) AS total_quantity, product 
# MAGIC FROM databricks_cookies_dais_2024.sales.transactions 
# MAGIC WHERE franchiseID = franchise_id GROUP BY product)

# COMMAND ----------

import os

# Get the Databricks host URL from the environment variable
host = "https://" + spark.conf.get("spark.databricks.workspaceUrl")

spark.sql(f'DROP FUNCTION IF EXISTS {catalog_name}.{schema_name}.cookie_reviews_with_secret;')
spark.sql(f'''
CREATE OR REPLACE FUNCTION {catalog_name}.{schema_name}.cookie_reviews_with_secret (short_description STRING, databricks_token STRING)
RETURNS STRING
LANGUAGE PYTHON
COMMENT 'Returns customer reviews for cookies rating the store, the staff, and the product'
AS
$$
  try:
    import requests
    headers = {{"Authorization": "Bearer "+databricks_token}}
    # Call our vector search endpoint via simple SQL statement
    response = requests.get("{host}/api/2.0/vector-search/indexes/agent_sample_data.media.vs_cookie_reviews/query", params ={{"columns":"chunked_text","query_text":short_description, "num_results":1}}, headers=headers).json()

    chunked_texts = [entry[0] for entry in response['result']['data_array']]
    return "Relevant Reviews: " .join(chunked_texts)
  except Exception as e:
    return f"Error calling the vs index {{e}}"
$$;''')

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP FUNCTION IF EXISTS ${catalog_name}.${schema_name}.franchise_reviews;
# MAGIC CREATE OR REPLACE FUNCTION ${catalog_name}.${schema_name}.franchise_reviews (short_description STRING)
# MAGIC RETURNS TABLE (reviews STRING)
# MAGIC LANGUAGE SQL
# MAGIC COMMENT 'Returns customer reviews for each franchise rating the store, the staff, and the product'
# MAGIC RETURN SELECT ${catalog_name}.${schema_name}.cookie_reviews_with_secret(short_description,  secret('dbdemos', 'llm-agent-tools'));

# COMMAND ----------

# MAGIC %md
# MAGIC ## Everything below here doesn't work in the lab environment, but will work on field-eng to expand functionality to generate images using the shutterstock model!

# COMMAND ----------

# Create a new job that runs the image generation function found in /images/image_gen 
# This job will take a prompt as an input and save it to a UC volume under <your_catalog>.ai.generated_images
import requests

token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)
user_email = dbutils.notebook.entry_point.getDbutils().notebook().getContext().tags().get("user").get()

cluster_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterId")

url = f"{host}/api/2.1/jobs/create"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {
  "name": "image_gen",
  "email_notifications": {
    "on_failure": [user_email],
    "no_alert_for_skipped_runs": True
  },
  "format": "MULTI_TASK",
  "max_concurrent_runs": 1,
  "schedule": {
    "quartz_cron_expression": "18 45 23 * * ?",
    "timezone_id": "America/Chicago",
    "pause_status": "PAUSED"
  },
  "tasks": [
    {
      "existing_cluster_id": cluster_id,
      "task_key": "image_gen",
      "run_if": "ALL_SUCCESS",
      "notebook_task": {
        "notebook_path": f"/Users/{user_email}/cookie_agent/images/image_gen",
        "base_parameters": {
          "prompt": "tasty outback oatmeal cookie"
        },
        "source": "WORKSPACE"
      },
      "timeout_seconds": 0,
      "email_notifications": {}
    }
  ],
  "queue": {
    "enabled": True
  }
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())
job_id = response.json()["job_id"]
print(job_id)

# COMMAND ----------

# Get the Databricks host URL from the environment variable
host = "https://" + spark.conf.get("spark.databricks.workspaceUrl")
print(host)
spark.sql(f'''CREATE OR REPLACE FUNCTION bakehouse.ai.backend_img_with_secret(my_prompt STRING, databricks_token STRING)
RETURNS string
LANGUAGE PYTHON
COMMENT 'This function generate an images and returns its content as binary. It also saves the image in the demo volume.'
AS
$$
    import requests, io, base64
    from PIL import Image
    response = requests.post(f"{host}/api/2.1/jobs/run-now", 
                            json={{
                                "job_id": 93995561103355,
                                "notebook_params": {{"prompt": my_prompt}}
                            }}, headers={{"Authorization": "Bearer "+databricks_token}}).json()

    return "Image created for prompt: "+ my_prompt
$$;''')

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP FUNCTION IF EXISTS generate_image;
# MAGIC CREATE OR REPLACE FUNCTION ${catalog_name}.${schema_name}.generate_image(my_prompt STRING)
# MAGIC RETURNS string
# MAGIC LANGUAGE SQL
# MAGIC COMMENT 'This function launches a job that creates a new image using the shutterstock model.'
# MAGIC RETURN
# MAGIC   SELECT ${catalog_name}.${schema_name}.backend_img_with_secret(my_prompt, secret('current-demo', 'llm-agent-token')) as image;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT bakehouse.ai.generate_image('cute brown puppy')

# COMMAND ----------

