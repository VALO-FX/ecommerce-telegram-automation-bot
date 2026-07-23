# Telegram E-Commerce & Order Automation Bot 🤖🛍️

An end-to-end, asynchronous Telegram bot designed for automated order management, OCR-based payment receipt verification, and real-time Google Sheets synchronization.

---

## ✨ Key Features

* **Interactive Shopping Flow:** Dynamic product navigation and FSM-driven order processing via `aiogram 3.x`.
* **OCR Payment Verification:** Automated receipt text extraction using OpenCV and Tesseract OCR to process transaction proof.
* **Google Sheets Integration:** Seamless real-time order logging via Google Sheets API (`gspread`).
* **Concurrency & Safety:** Order locking mechanism to prevent multiple employees from overlapping on the same pending order.
* **Role-Based Access Control:** Dedicated admin workflows for product management and pending order approval/rejection.
* **Automated Cron Reports:** Scheduled daily analytics reporting using `APScheduler`.

---

## 🛠️ Tech Stack & Architecture

* **Language:** Python 3.10+
* **Framework:** `aiogram` (v3.x)
* **Database:** SQLite3
* **Image Processing:** OpenCV, PyTesseract
* **Integrations:** Google Drive & Sheets API, APScheduler

---

## 🚀 Quick Start & Setup

### 1. System Requirements

Install the Tesseract-OCR engine on your host server:
```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr
2. Installation
​Clone the repository and install Python dependencies:
git clone [https://github.com/VALO-FX/ecommerce-telegram-automation-bot.git](https://github.com/VALO-FX/ecommerce-telegram-automation-bot.git)
cd ecommerce-telegram-automation-bot
pip install -r requirements.txt
3. Environment Setup
​Configure your bot credentials in config.py or export them as environment variables:
export BOT_TOKEN="your_telegram_bot_token"
export ADMIN_PASSWORD="your_admin_password"
4. Running the Application
​Grant execution permissions and launch the process runner:
chmod +x run.sh
./run.sh
📄 License
​This project is licensed under the MIT License - see the LICENSE file for details.
