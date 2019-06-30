# Use an official Python runtime as a parent image
FROM benkalukas/py_weekend_base

# Set the working directory to /app
WORKDIR /app

COPY Pipfile* /app/


# Install any needed packages specified in Pipfile
RUN pipenv install --system --deploy

# Copy the current directory contents into the container at /app
COPY . /app

# Run app.py when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "cd_api:app"]