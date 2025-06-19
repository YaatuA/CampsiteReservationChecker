# Use an official Python image as a base
FROM python:3.11-slim-bookworm

# Set the working directory inside the container
WORKDIR /app

# Prevent prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install Google Chrome and its dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    # Add Google's official key
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    # Add Google's repository
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    # Install Chrome
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Copy your requirements file into the container
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Set the command to run your script
CMD ["python", "check_campsites_selenium.py"]