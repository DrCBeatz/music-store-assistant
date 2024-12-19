# Music Store Assistant

The **Music Store Assistant** is a Django-based web application designed to interact with a music store's product catalog. It can perform tasks such as retrieving product information, updating product data, managing inventory, and sending emails. The application integrates with Shopify and uses OpenAI's API to handle user queries in a conversational manner.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Using the Application](#using-the-application)
- [Scheduling Product Updates](#scheduling-product-updates)
- [Email Functionality](#email-functionality)
- [Celery Tasks](#celery-tasks)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- **Conversational Assistant:** Ask questions about the music store's products, request product updates, or schedule CSV imports.
- **Shopify Integration:** Connects to a Shopify store to retrieve and modify product data.
- **OpenAI Integration:** Uses OpenAI's API to handle natural language queries.
- **File Upload Support:** Allows uploading CSV files to create or update multiple products at once.
- **Scheduled Updates:** Use Celery to schedule product updates and roll them back automatically at a later time.
- **Email Sending:** Send emails (optionally with attachments) directly from the assistant interface.

## Architecture

The application is built using:
- **Django:** A high-level Python web framework.
- **Celery + Redis:** For task scheduling and background processing.
- **PostgreSQL:** As the primary database.
- **Shopify API:** For interacting with the store’s products.
- **OpenAI API:** For generating answers to user queries.
- **Docker + Docker Compose:** To containerize the application and its services.

## Project Structure

```bash
.
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── requirements.txt
├── Pipfile
├── Pipfile.lock
├── ec2_deploy.sh
├── accounts/             # Django app for user accounts and authentication
├── assistant/            # Django app containing the assistant logic and views
│   ├── migrations/
│   ├── templates/
│   ├── forms.py
│   ├── models.py
│   ├── tasks.py
│   ├── views.py
│   └── ... (other scripts and utilities)
├── core/                 # Django project settings, URL configuration, WSGI/ASGI
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py
├── static/               # Frontend static assets (CSS, JS, images)
├── media/                # Media directory for file uploads
└── templates/            # HTML templates for rendering views
    └── ... (base and page templates)
```

## Prerequisites

- **Docker and Docker Compose** installed on your machine.
- **OpenAI API Key:** Required for question answering.
- **Shopify Access Token:** Required for product data retrieval and updates.
- **PostgreSQL Database Credentials**
- **Mailgun API Credentials:** For sending emails via the assistant.
- **Redis:** Used as a message broker and result backend for Celery.

## Environment Variables

Create a `.env` file at the project root or use environment variables directly. The following are typical requirements:

```bash
DJANGO_SECRET_KEY=your_secret_key
DJANGO_DEBUG=False
POSTGRES_DB=your_db_name
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=db
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_HOST_USER=your@mailgun.org
EMAIL_HOST_PASSWORD=your_mailgun_password
DEFAULT_FROM_EMAIL=info@yourmusicstore.com
MAILGUN_DOMAIN=your_mailgun_domain
MAILGUN_API_KEY=your_mailgun_api_key
FROM_EMAIL=info@yourmusicstore.com
OPENAI_API_KEY=your_openai_api_key
SHOPIFY_ACCESS_TOKEN=your_shopify_access_token
```

## Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/yourusername/music-store-assistant.git
    cd music-store-assistant
    ```

2. **Set Up Environment Variables:**

    Make sure your `.env` file is properly configured with all the required keys mentioned above.

3. **Install Dependencies (Optional if using Docker):**

    If you are not using Docker, install Python dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

Using Docker Compose is the recommended approach:

```bash
docker-compose build
docker-compose up
```

This will start the following services:

- **web:** The Django application served by gunicorn.
- **db:** PostgreSQL database.
- **redis:** Redis server for Celery.
- **worker:** Celery worker service.
- **beat:** Celery beat scheduler service.

Once running, access the application at `http://localhost:80` (or your assigned port).

## Using the Application

1. **Login:** Register or log in with your admin or created user account.
2. **Home Page:** Once logged in, you’ll see a form that allows you to ask questions or interact with your product data.
3. **Asking Questions:** Input a question, such as "What is the price of SKU ABC123?" and click submit.
4. **File Upload:** For bulk product updates or creation, upload a CSV file. The assistant will automatically detect and call the appropriate function to process it.

## Scheduling Product Updates

The assistant supports scheduling product updates and reverting them at a later time using Celery.

- **Apply Time:** Set a future datetime to apply changes from a CSV file.
- **Revert Time:** Optionally set a future datetime to revert these changes.

Celery beat and worker services will handle these scheduled tasks automatically.

## Email Functionality

You can ask the assistant to send emails (optionally with the file you uploaded) to specified recipients. The app uses Mailgun for sending emails.

**Example query:**

"Send an email with the attached CSV to sales@yourmusicstore.com with subject 'Product Updates' and body 'Please see attached.'"

## Celery Tasks

The app uses Celery to:

- Send scheduled emails.
- Apply and revert CSV-based product updates.
- Perform long-running background operations.

All scheduled and background tasks are monitored and executed by the worker and beat containers.

## Troubleshooting

- **Database Issues:** Check `.env` credentials and ensure the `db` service is running.
- **Celery/Redis Issues:** Confirm that Redis is accessible and that Celery worker and beat services can connect to it.
- **OpenAI / Shopify API Errors:** Check that your API keys are correct and that you have the required permissions.
- **Email Sending:** Ensure Mailgun credentials are correct, and verify your domain is properly set up at Mailgun.

**View logs with:**

```bash
docker-compose logs -f
```

## License

This project is covered by the terms of the MIT License.
