# Use Python 3.11 slim-bullseye image as base
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Install Chrome dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    curl \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libfontconfig \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-archive-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_VERSION=$(google-chrome-stable --version | awk '{ print $3 }' | awk -F'.' '{ print $1 }') \
    && wget -q -O /tmp/chromedriver.zip "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_VERSION.0.6943.0/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && rm -rf /usr/local/bin/chromedriver-linux64 \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create log directory and file with proper permissions
RUN mkdir -p /var/log/scout
RUN touch /var/log/scout/cron.log
RUN chmod -R 0777 /var/log/scout

# Create cron job
RUN echo "0 0 */2 * * cd /app && /usr/local/bin/python3 main.py >> /var/log/scout/cron.log 2>&1" > /etc/cron.d/scout-cron
RUN chmod 0644 /etc/cron.d/scout-cron
RUN crontab /etc/cron.d/scout-cron

# Create entrypoint script
RUN echo '#!/bin/sh' > /entrypoint.sh \
    && echo 'cron' >> /entrypoint.sh \
    && echo 'tail -f /var/log/scout/cron.log' >> /entrypoint.sh \
    && chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
