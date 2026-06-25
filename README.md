# Edge AIoT Bootcamp

The system has two environments:

ESP32 Environment:
- main.py — reads sensor data, runs Edge AI, controls outputs, sends BLE data
- guardian_ml_model.py — trained Decision Tree model
- ssd1306.py — OLED driver library

Laptop Environment:
- guardian_phone_dashboard_logger.py — receives BLE data and runs phone dashboard
- guardian_config.py — stores project settings
- dashboard_page.py — phone webpage layout
- train_guardian_model.py — trains the ML model

Each file has a clear responsibility.

---
