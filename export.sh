#!/usr/bin/env sh

if [ -z "$1" ]; then
    echo "Usage: $0 <properties file>"
    exit 1
fi

PROPERTY_FILE=$1

OS=$(uname -s)
if [ $OS == "Darwin" ]; then
  echo "==> Detected MacOS"
  BASE64_FLAG="-b 0"
else
  echo "==> Detected Linux"
  BASE64_FLAG="-w 0"
fi

echo "==> Loading properties from $PROPERTY_FILE"

while read -r line;
do
  key=$(echo "$line" | awk -F "=" '{print $1}' | tr '[:lower:]' '[:upper:]')
  value=$(echo -n "$line" | awk -F "=" '{print $2}' | base64 $BASE64_FLAG | tr -d '\n')
  echo "==> Exporting '$key':'$value'"

  export "${key}"="$value"
done < "$PROPERTY_FILE"
