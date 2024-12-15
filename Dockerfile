# Dockerfile

FROM python:3.10.4-slim-bullseye

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Create a non-root user and group (e.g., 'celeryuser')
RUN useradd -ms /bin/bash celeryuser

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure that the non-root user owns the application files
RUN chown -R celeryuser:celeryuser /code

# Switch to the non-root user
USER celeryuser
