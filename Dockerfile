# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask port
EXPOSE 5000

# Run the app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--worker-class", "gevent", "app:app"]
