# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

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
RUN echo "0 0 */2 * * cd /app && python3 main.py >> /var/log/scout/cron.log 2>&1" > /etc/cron.d/scout-cron
RUN chmod 0644 /etc/cron.d/scout-cron
RUN crontab /etc/cron.d/scout-cron

# Create entrypoint script
RUN echo '#!/bin/sh' > /entrypoint.sh
RUN echo 'echo "Starting cron service..."' >> /entrypoint.sh
RUN echo 'cron' >> /entrypoint.sh
RUN echo 'echo "Cron service started"' >> /entrypoint.sh
RUN echo 'echo "Creating log file..."' >> /entrypoint.sh
RUN echo 'touch /var/log/scout/cron.log' >> /entrypoint.sh
RUN echo 'chmod 0777 /var/log/scout/cron.log' >> /entrypoint.sh
RUN echo 'echo "Starting log tail..."' >> /entrypoint.sh
RUN echo 'tail -f /var/log/scout/cron.log' >> /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
