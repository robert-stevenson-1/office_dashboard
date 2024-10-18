from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import serial
import threading
import time
import datetime
import csv
import os
import asyncio
import aiohttp

app = Flask(__name__)
socketio = SocketIO(app)

# Lists to store temperature, humidity, and timestamps for plotting
temperature_data = []
humidity_data = []
timestamps = []

# CSV file to store the sensor data
CSV_FILE = 'sensor_data.csv'

# Replace with your actual serial port and baud rate
SERIAL_PORT = '/dev/ttyUSB0'  # Update with your serial port
BAUD_RATE = 115200

# API endpoints and keys
BBC_RSS_FEED = "http://feeds.bbci.co.uk/news/rss.xml"
OPENWEATHER_API_KEY = "your_openweather_api_key"
WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"


# Function to load historical data from the CSV file when the server starts
def load_data_from_csv():
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                timestamp_str, temperature, humidity = row
                timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                timestamps.append(timestamp)
                temperature_data.append(float(temperature))
                humidity_data.append(float(humidity))

    # Keep only the data points from the last 5 minutes for plotting
    filter_old_data()

# Function to log data to file and send it via WebSocket
def log_and_send_data(temperature, humidity):
    timestamp = datetime.datetime.now()

    # Append data to the lists
    timestamps.append(timestamp)
    temperature_data.append(temperature)
    humidity_data.append(humidity)

    # Save the new data to the CSV file
    with open(CSV_FILE, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp.strftime("%Y-%m-%d %H:%M:%S"), temperature, humidity])

    # Remove data points older than 5 minutes for real-time display
    filter_old_data()

    # Calculate the 5-minute average temperature
    average_temperature_5min = sum(temperature_data) / len(temperature_data) if len(temperature_data) > 0 else 0

    # Calculate the 5-day average temperature
    average_temperature_5days = calculate_5_day_average()

    # Emit the current and average temperatures along with the latest data points
    socketio.emit('new_data', {
        'time': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        'temperature': temperature,
        'humidity': humidity,
        'current_temperature': temperature,
        'average_temperature_5min': average_temperature_5min,
        'average_temperature_5days': average_temperature_5days
    })

# Function to filter out data older than 5 minutes for chart plotting
def filter_old_data():
    current_time = datetime.datetime.now()
    five_minutes_ago = current_time - datetime.timedelta(minutes=5)

    # Keep only the data points within the last 5 minutes
    while len(timestamps) > 0 and timestamps[0] < five_minutes_ago:
        timestamps.pop(0)
        temperature_data.pop(0)
        humidity_data.pop(0)

# Function to calculate the average temperature over the last 5 days
def calculate_5_day_average():
    current_time = datetime.datetime.now()
    five_days_ago = current_time - datetime.timedelta(days=5)

    # Filter data within the last 5 days
    temperatures_last_5days = [temp for i, temp in enumerate(temperature_data) if timestamps[i] >= five_days_ago]

    # Calculate the average temperature over the last 5 days
    if len(temperatures_last_5days) > 0:
        return sum(temperatures_last_5days) / len(temperatures_last_5days)
    else:
        return 0  # Return 0 if no data is available for the last 5 days

# Function to read data from the serial port
def read_serial_data():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
    while True:
        try:
            if ser.in_waiting > 0:
                # Read the line from the serial port, decode it, and strip any extraneous characters
                line = ser.readline().decode('utf-8').strip()

                # Example format: Temperature: 25.34 °C, Humidity: 60.23 %
                if "Temperature" in line and "Humidity" in line:
                    # Extract the temperature and humidity values from the string
                    temp_value = float(line.split(" ")[1])
                    humidity_value = float(line.split(" ")[4].strip('%'))

                    # Log and broadcast the data
                    log_and_send_data(temp_value, humidity_value)
        except Exception as e:
            print(f"Error reading serial data: {e}")

# Asynchronous function to fetch BBC News
async def fetch_bbc_news():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(BBC_RSS_FEED) as response:
                response_text = await response.text()
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response_text)
                items = root.findall(".//item")
                news = []
                for item in items[:5]:  # Get the latest 5 articles
                    title = item.find("title").text
                    link = item.find("link").text
                    news.append({"title": title, "link": link})
                return news
        except Exception as e:
            print(f"Error fetching BBC News: {e}")
            return []

# Asynchronous function to fetch weather data
async def fetch_weather(city_id):
    async with aiohttp.ClientSession() as session:
        params = {
            'id': city_id,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric'
        }
        try:
            async with session.get(WEATHER_URL, params=params) as response:
                data = await response.json()
                weather = {
                    'city': data['name'],
                    'temperature': data['main']['temp'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon']
                }
                return weather
        except Exception as e:
            print(f"Error fetching weather: {e}")
            return {}

# Route to serve the main webpage
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/bbc-news')
async def bbc_news():
    news = await fetch_bbc_news()
    return jsonify(news)

@app.route('/weather/<int:city_id>')
async def get_weather_by_id(city_id):
    weather = await fetch_weather(city_id)
    return jsonify(weather)

@socketio.on('connect')
def handle_connect():
    # Send the historical data (last 5 minutes) to the newly connected client
    recent_timestamps = [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps]
    emit('historical_data', {
        'timestamps': recent_timestamps,
        'temperature_data': temperature_data,
        'humidity_data': humidity_data
    })

if __name__ == '__main__':
    # Load historical data from the CSV file when the server starts
    load_data_from_csv()

    # Start a background thread to read serial data
    serial_thread = threading.Thread(target=read_serial_data)
    serial_thread.daemon = True
    serial_thread.start()

    # Start the Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=5000)
