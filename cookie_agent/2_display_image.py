# Databricks notebook source
# DBTITLE 1,Display Generated Image
from PIL import Image
import io

# Read the image file from DBFS
image_path = "/Volumes/bakehouse/ai/images/positive_image.jpeg"
with open(image_path, "rb") as f:
    image = Image.open(io.BytesIO(f.read()))

# Display the image
display(image)