# Gemini File Maestro

Gemini File Maestro is a secure, robust, and production-ready web application built with Flask (Python) that allows authenticated users to manage files and folders stored within a PostgreSQL database. It leverages the Gemini API for advanced text-processing capabilities.

## Features

* **Secure User Authentication:** User registration, login, and logout with bcrypt password hashing, secure session management, and brute-force protection.
* **File Management:** Securely store, view, edit, save, and delete files and folders within a PostgreSQL database using Large Objects. Supports various file types and includes client-side validation.
* **Real-time Collaboration:** Multiple users can edit the same file simultaneously with real-time updates.
* **Advanced Text Editor:** Integrated text editor with syntax highlighting for various programming languages and rich text editing capabilities.
* **Gemini API Integration:** Seamless integration with the Gemini API for sentiment analysis, grammar and style checking, text summarization, named entity recognition, and creative text generation.
* **Responsive Web Interface:** Modern and user-friendly interface built with a responsive design framework (e.g., Bootstrap, Tailwind CSS) for optimal viewing on various devices.
* **Production-Ready Deployment:** Includes detailed instructions for deploying the application with Nginx, Gunicorn, and systemd on an Ubuntu 22.04 server.
* **Comprehensive Testing:** Includes a suite of unit and integration tests using pytest to ensure application functionality and security.



## Getting Started

These instructions will guide you through setting up and running Gemini File Maestro on a new Ubuntu 22.04 VM.

### Prerequisites

* Ubuntu 22.04 VM
* Basic familiarity with Linux command-line operations

### Installation

1. **Update System Packages:**
```bash
sudo apt update
```bash
2. **Update System Packages:**
Install Required Packages:
sudo apt install python3.10 python3.10-venv python3-pip postgresql-14 nginx gunicorn libpq-dev build-essential

Set up PostgreSQL: (Refer to the PostgreSQL setup section in the documentation for detailed instructions).
Set up a virtual environment:

python3.10 -m venv .venv
source .venv/bin/activate


Install Project Dependencies:
pip install -r requirements.txt

Configure Nginx and Gunicorn: (Refer to the Nginx and Gunicorn configuration sections in the documentation)
Run Database Migrations:
flask db upgrade

Usage
Register a new user: Access the registration page through the web interface.
Login: Use your credentials to log in.
Manage Files and Folders: Upload, download, edit, and organize your files and folders through the intuitive web interface.
Use the Text Editor: Create and edit text files with syntax highlighting and real-time collaboration features.
Explore Gemini API features: Utilize the integrated Gemini API functionalities for text analysis and creative text generation.
Gemini API Key
You'll need a Gemini API key to use the Gemini API features. Set the GEMINI_API_KEY environment variable with your key.

Testing
Run the test suite using pytest:

pytest -v

Deployment
Detailed deployment instructions are provided in the deployment section of the documentation.

Contributing
Contributions are welcome! Please feel free to submit issues and pull requests.

License
[Specify your license here]

Contact
[Your Name] - [Your Email]

Acknowledgements
[List any libraries or resources used]
Documentation
Detailed documentation is available in the /docs folder. You can also view an online version of the documentation here: [link to online documentation, if any].