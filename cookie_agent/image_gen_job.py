# Databricks notebook source
import os
import requests
import numpy as np
import pandas as pd
import json
import matplotlib.pyplot as plt
from PIL import Image

dbutils.widgets.text("prompt", "", "Prompt to create image from")

# Correctly retrieve the value of the widget
my_prompt = dbutils.widgets.get("prompt")

URL = "https://data-ai-lakehouse.cloud.databricks.com/serving-endpoints/sd-endpoint/invocations"
DATABRICKS_TOKEN = dbutils.secrets.get('current-demo', 'image-gen')

INPUT_EXAMPLE = pd.DataFrame({"prompt":[my_prompt]})

def score_model(dataset, url=URL, databricks_token=DATABRICKS_TOKEN):
    headers = {'Authorization': f'Bearer {databricks_token}', 
               'Content-Type': 'application/json'}
    ds_dict = {'dataframe_split': dataset.to_dict(orient='split')}
    data_json = json.dumps(ds_dict, allow_nan=True)
    response = requests.request(method='POST', headers=headers, url=url, data=data_json)
    if response.status_code != 200:
        raise Exception(f'Request failed with status {response.status_code}, {response.text}')

    return response.json()

# scoring the model
t = score_model(INPUT_EXAMPLE)

# visualizing the predictions
image = t['predictions']
image_array = np.array(image, dtype=np.uint8)

img = Image.fromarray(image_array, "RGB")

img.save(f'/Volumes/bakehouse/ai/images/generated_image.jpeg', format='JPEG')
