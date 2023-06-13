# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory in the container
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Make port 5051 available to the world outside this container
EXPOSE 5051

# Define environment variable
ENV FLASK_APP=app.py

# Run the command to start the Flask application
#CMD ["flask", "run", "--host=0.0.0.0"]
CMD ["python", "app.py"]