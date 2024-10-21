from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import datetime
import csv
import os
import socket
import requests
from xml.etree import ElementTree as ET

app = Flask(__name__)
socketio = SocketIO(app)

# Lists to store temperature, humidity, and timestamps for plotting
temperature_data = []
humidity_data = []
timestamps = []

# CSV file to store the sensor data
CSV_FILE = 'sensor_data.csv'

# Socket settings (to communicate with serial_reader.py)
HOST = '127.0.0.1'
PORT = 5001

# API endpoints and keys
BBC_RSS_FEED = "http://feeds.bbci.co.uk/news/rss.xml"
OPENWEATHER_API_KEY = "your_openweather_api_key"
WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"
HUMBERSIDE_AIRPORT_CODE = "HUY"
FLIGHT_API_URL = "http://api.aviationstack.com/v1/flights"
FLIGHT_API_KEY = "your_flightstack_api_key"  # Replace with your AviationStack API key

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

# Function to receive data from the socket connection
def receive_socket_data():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        print(f"Listening on {HOST}:{PORT} for serial data...")

        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    # Parse received data (temperature, humidity)
                    temp_value, humidity_value = data.decode('utf-8').strip().split(',')
                    log_and_send_data(float(temp_value), float(humidity_value))
                except Exception as e:
                    print(f"Error receiving socket data: {e}")

# Route to serve the main webpage
@app.route('/')
def home():
    return render_template('index.html')

# Route to fetch latest BBC news
@app.route('/news')
def news():
    try:
        # Fetch the BBC feed
        bbc_response = requests.get(BBC_RSS_FEED)
        bbc_response.raise_for_status()

        # Parse the RSS feed
        bbc_root = ET.fromstring(bbc_response.content)
        bbc_items = bbc_root.findall(".//item")[:5]  # Get the latest 5 articles
        news = []

        for item in bbc_items:
            title = item.find("title").text 
            link = item.find("link").text
            news.append({"title": title, "link": link})

        return jsonify(news)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to fetch weather information
@app.route('/weather/<city>')
def get_weather(city):
    params = {
        'q': city,
        'appid': OPENWEATHER_API_KEY,
        'units': 'metric'  # Get temperature in Celsius
    }
    try:
        response = requests.get(WEATHER_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Extract relevant weather information
        weather = {
            'city': data['name'],
            'temperature': data['main']['temp'],
            'description': data['weather'][0]['description'],
            'icon': data['weather'][0]['icon']
        }
        return jsonify(weather)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to fetch flight departure information from Humberside Airport
@app.route('/departures')
def departures():
    try:
        # Fetch flight data
        response = requests.get(FLIGHT_API_URL, params={"access_key": FLIGHT_API_KEY, "dep_iata": HUMBERSIDE_AIRPORT_CODE})
        response.raise_for_status()
        
        data = response.json()
        departures = []

        # Extract departure information
        for flight in data.get("data", []):
            departures.append({
                "flight_number": flight["flight"]["iata"],
                "destination": flight["departure"]["iata"],
                "departure_time": flight["departure"]["estimated"],
            })

        return jsonify(departures)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# WebSocket connection handler to send historical data to newly connected clients
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

    # Start a background thread to receive data from the internal socket
    socket_thread = threading.Thread(target=receive_socket_data)
    socket_thread.daemon = True
    socket_thread.start()

    # Start the Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
