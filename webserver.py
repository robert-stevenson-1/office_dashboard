# TODO: Create seperate log files for each day to reduce load time
# TODO: Auto swap the log time on day change
# TODO: Display only the current day's data in the graphs

from flask import Flask, render_template, jsonify, request, url_for
from flask_socketio import SocketIO, emit
import threading
import time
import datetime
import random
import csv
import os
import socket
import requests
import json
import signal
from xml.etree import ElementTree as ET
from lxml import etree
import pyttsx3

app = Flask(__name__)
socketio = SocketIO(app)

# Define a shutdown flag to signal the thread to stop
shutdown_flag = threading.Event()

# Lists to store temperature, humidity, and timestamps for plotting
temperature_data = []
humidity_data = []
timestamps = []

# CSV file to store the sensor data
CSV_FILE = 'sensor_data.csv'

# Socket settings (to communicate with serial_reader.py)
HOST = '127.0.0.1'
PORT = 5001
# PORT = 5002
# PORT = 65432

# API endpoints and keys
BBC_RSS_FEED = "http://feeds.bbci.co.uk/news/rss.xml"
ONION_RSS_FEED = "https://www.theonion.com/rss"
DAILY_MASH_RSS_FEED = "https://www.thedailymash.co.uk/feed"
WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"
AIRPORT_CODE = "HUY"
FLIGHT_API_URL = "http://api.aviationstack.com/v1/flights"
TRAIN_API_URL = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/ldb11.asmx"

# Load the configuration data
with open('config/config.json', 'r') as file:
    config = json.load(file)

# Access API keys
TRAIN_API_KEY = config.get("TRAIN_API_KEY")
FLIGHT_API_KEY = config.get("FLIGHT_API_KEY")
OPENWEATHER_API_KEY = config.get("OPENWEATHER_API_KEY")
OPEN_BUS_DATA_API_KEY = config.get("OPEN_BUS_DATA_API_KEY")

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

# Function to filter data from the last 'n' hours
def filter_last_n_hours(n_hours):
    now = datetime.datetime.now()
    time_ago = now - datetime.timedelta(hours=n_hours)

    filtered_timestamps = []
    filtered_temperature_data = []
    filtered_humidity_data = []

    # Load data from the CSV file and filter out entries older than 'n' hours
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                timestamp_str, temperature, humidity = row
                timestamp_str_cleaned = timestamp_str.replace('\x00', '')
                timestamp = datetime.datetime.strptime(timestamp_str_cleaned, "%Y-%m-%d %H:%M:%S")
                
                if timestamp >= time_ago:
                    filtered_timestamps.append(timestamp.strftime("%Y-%m-%d %H:%M:%S"))
                    filtered_temperature_data.append(float(temperature))
                    filtered_humidity_data.append(float(humidity))

    return filtered_timestamps, filtered_temperature_data, filtered_humidity_data

# Quote of the Day - updated with the new list
quotes = [
    {"quote": "I’d explain it to you, but I left my English-to-Dingbat dictionary at home."},
    {"quote": "You bring everyone so much joy... when you leave the room."},
    {"quote": "I’d agree with you, but then we’d both be wrong."},
    {"quote": "You’re proof that even evolution makes mistakes."},
    {"quote": "Your secrets are always safe with me. I never even listen when you tell me them."},
    {"quote": "I’m not saying you’re stupid; I’m just saying you have bad luck when it comes to thinking."},
    {"quote": "You have the perfect face for radio."},
    {"quote": "I don’t know what makes you so dumb, but it really works."},
    {"quote": "I’m not insulting you; I’m describing you."},
    {"quote": "You’re like a software update. Whenever I see you, I think, 'Not now.'"},
    {"quote": "I thought of you today. It reminded me to take out the trash."},
    {"quote": "You’re like a cloud. When you disappear, it’s a beautiful day."},
    {"quote": "I don’t have the energy to pretend to like you today."},
    {"quote": "You’re the reason God created the middle finger."},
    {"quote": "If I had a dollar for every time I saw you, I’d be broke."},
    {"quote": "You’re as useless as the 'ueue' in 'queue.'"},
    {"quote": "I’m jealous of people who don’t know you."},
    {"quote": "You’re like a slinky; not really good for much, but you bring a smile when you fall down the stairs."},
    {"quote": "You have a nice face. I’d like to keep it in a jar."},
    {"quote": "Some day you’ll go far... and I hope you stay there."},
    {"quote": "I’d call you a tool, but that implies you’re useful."},
    {"quote": "If laughter is the best medicine, your face must be curing the world."},
    {"quote": "A clear conscience is usually the sign of a bad memory."},
    {"quote": "I used to think I was indecisive, but now I’m not too sure."},
    {"quote": "You’re as welcome as a skunk at a garden party."},
    {"quote": "If you were any more inbred, you’d be a sandwich."},
    {"quote": "You’re as useful as a screen door on a submarine."},
    {"quote": "You’re not stupid; you just have bad luck when it comes to thinking."},
    {"quote": "You bring so much joy... when you leave the room."},
    {"quote": "I can see why people hate you."},
    {"quote": "If I wanted to hear from an asshole, I’d fart."},
    {"quote": "You’re the reason God created the middle finger."},
    {"quote": "I’d agree with you, but then we’d both be wrong."},
    {"quote": "You’re like a broken pencil: pointless."},
    {"quote": "I’d explain it to you, but I don’t have any crayons."},
    {"quote": "You’re the human version of a participation trophy."},
    {"quote": "You’re like a cloud; when you disappear, it’s a beautiful day."},
    {"quote": "Your face makes onions cry."},
    {"quote": "I’m not lazy; I’m on energy-saving mode."},
    {"quote": "If at first you don’t succeed, then skydiving definitely isn’t for you."},
    {"quote": "You’re as pleasant as a root canal."},
    {"quote": "I’d like to see things from your perspective, but I can’t get my head that far up my own ass."},
    {"quote": "You’re like a slinky; not really good for much, but you bring a smile when you fall down the stairs."},
    {"quote": "I hope your day is as pleasant as your personality."},
    {"quote": "You have the perfect face for radio."},
    {"quote": "You’re proof that even evolution makes mistakes."},
    {"quote": "You bring everyone so much joy... when you leave the room."},
    {"quote": "I’d call you a tool, but that implies you’re useful."},
    {"quote": "If I wanted to hear from an asshole, I’d fart."},
    {"quote": "You have a nice face. I’d like to keep it in a jar."},
    {"quote": "If you were any more dense, we could put you in a black hole."},
    {"quote": "You’re as useful as a chocolate teapot."},
    {"quote": "You’re not even wrong."},
    {"quote": "You’re the human version of a participation trophy."},
    {"quote": "You’re like a cloud; when you disappear, it’s a beautiful day."},
    {"quote": "I’d explain it to you, but I don’t have the crayons."},
    {"quote": "You’re the reason they put instructions on shampoo."},
    {"quote": "You’re as useless as a screen door on a submarine."},
    {"quote": "I’d agree with you, but then we’d both be wrong."},
    {"quote": "You’re like a software update; whenever I see you, I think, 'Not now.'"},
    {"quote": "I can see why people hate you."},
    {"quote": "If you were any more inbred, you’d be a sandwich."},
    {"quote": "You’re the human version of a participation trophy."},
    {"quote": "You’re like a slinky; not really good for much, but you bring a smile when you fall down the stairs."},
    {"quote": "If I had a dollar for every time I saw you, I’d be broke."},
    {"quote": "You’re as welcome as a skunk at a garden party."},
    {"quote": "I’d like to see things from your perspective, but I can’t get my head that far up my own ass."},
    {"quote": "I thought of you today. It reminded me to take out the trash."},
    {"quote": "You’re like a cloud; when you disappear, it’s a beautiful day."},
    {"quote": "I’d explain it to you, but I don’t have the crayons."},
    {"quote": "You’re the reason they put instructions on shampoo."},
    {"quote": "You’re the reason God created the middle finger."},
    {"quote": "You bring everyone so much joy... when you leave the room."},
    {"quote": "You’re not stupid; you just have bad luck when it comes to thinking."},
    {"quote": "You’re proof that even evolution makes mistakes."},
    {"quote": "If I wanted to hear from an asshole, I’d fart."},
    {"quote": "You’re about as useful as a chocolate teapot."},
    {"quote": "You have a nice face. I’d like to keep it in a jar."},
    {"quote": "You’re like a software update; whenever I see you, I think, 'Not now.'"},
    {"quote": "You’re like a broken pencil: pointless."},
    {"quote": "You’re as useful as a screen door on a submarine."},
    {"quote": "You bring everyone so much joy... when you leave the room."},
    {"quote": "You’re the human version of a participation trophy."},
    {"quote": "You’re as welcome as a skunk at a garden party."},
    {"quote": "I hope your day is as pleasant as your personality."},
    {"quote": "I’d like to see things from your perspective, but I can’t get my head that far up my own ass."},
    {"quote": "If you were any more inbred, you’d be a sandwich."},
    {"quote": "I’m not insulting you; I’m describing you."},
    {"quote": "You have the perfect face for radio."},
    {"quote": "I’d call you a tool, but that implies you’re useful."},
    {"quote": "You’re like a software update. Whenever I see you, I think, 'Not now.'"},
    {"quote": "You’re proof that even evolution makes mistakes."},
    {"quote": "I’d agree with you, but then we’d both be wrong."},
    {"quote": "You’re the reason they put instructions on shampoo."},
    {"quote": "I’d explain it to you, but I don’t have the crayons."},
    {"quote": "You’re like a slinky; not really good for much, but you bring a smile when you fall down the stairs."},
    {"quote": "If laughter is the best medicine, your face must be curing the world."},
    {"quote": "You bring so much joy... when you leave the room."},
    {"quote": "You’re the reason God created the middle finger."},
    {"quote": "If at first you don’t succeed, then skydiving definitely isn’t for you."},
    {"quote": "You’re like a cloud; when you disappear, it’s a beautiful day."},
    {"quote": "I thought of you today. It reminded me to take out the trash."},
    {"quote": "I can see why people hate you."},
    {"quote": "I’d like to see things from your perspective, but I can’t get my head that far up my own ass."},
    {"quote": "You’re as useless as a chocolate teapot."},
    {"quote": "I’d agree with you, but then we’d both be wrong."},
    {"quote": "You’re proof that even evolution makes mistakes."},
    {"quote": "You’re the reason they put instructions on shampoo."},
    {"quote": "You’re like a software update; whenever I see you, I think, 'Not now.'"},
    {"quote": "I hope your day is as pleasant as your personality."},
    {"quote": "You’re about as useful as a screen door on a submarine."},
    {"quote": "I’d explain it to you, but I don’t have the crayons."},
    {"quote": "You have a nice face. I’d like to keep it in a jar."},
    {"quote": "You’re the human version of a participation trophy."},
    {"quote": "You’re not stupid; you just have bad luck when it comes to thinking."},
    {"quote": "You bring so much joy... when you leave the room."},
    {"quote": "You’re like a broken pencil: pointless."},
    {"quote": "I’d call you a tool, but that implies you’re useful."},
    {"quote": "I’m not saying you’re stupid; I’m just saying you have bad luck when it comes to thinking."},
    {"quote": "You’re the reason God created the middle finger."},
    {"quote": "You’re like a slinky; not really good for much, but you bring a smile when you fall down the stairs."},
    {"quote": "You’re the human version of a participation trophy."},
    {"quote": "I’d agree with you, but then we’d both be wrong."},
    {"quote": "I’d explain it to you, but I don’t have any crayons."},
    {"quote": "You’re like a cloud; when you disappear, it’s a beautiful day."},
    {"quote": "I thought of you today. It reminded me to take out the trash."},
    {"quote": "You bring everyone so much joy... when you leave the room."}
]
 
# Route to get a random quote
@app.route('/random_quote')
def random_quote():
    # Seed random number generator with today's date
    # today = datetime.date.today()
    # seed_value = today.toordinal()  # Converts to an ordinal number
    # random.seed(seed_value)
    # Select a random quote
    quote = random.choice(quotes)
    return jsonify(quote)

# Dynamic route to serve data from the last 'n' hours
@app.route('/get_last_hours/<int:hours>')
def get_last_hours(hours):
    timestamps, temperature_data, humidity_data = filter_last_n_hours(hours)
    return jsonify({
        'timestamps': timestamps,
        'temperature_data': temperature_data,
        'humidity_data': humidity_data
    })

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
    """Function to receive data from the internal socket connection."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow socket reuse
    s.bind((HOST, PORT))
    s.listen()

    print(f"Listening on {HOST}:{PORT} for serial data...")

    while not shutdown_flag.is_set():
        try:
            # Wait for a client connection
            # print("Waiting for client to connect...")
            s.settimeout(1.0)  # Timeout to check shutdown flag
            try:
                conn, addr = s.accept()
                print(f"Connected by {addr}")
                with conn:
                    while not shutdown_flag.is_set():
                        try:
                            conn.settimeout(1.0)  # Set timeout to avoid blocking
                            data = conn.recv(1024)
                            if not data:
                                print("Connection lost. Waiting for reconnection...")
                                break  # Client disconnected, retry to accept a new connection
                            
                            # Parse received data (temperature, humidity)
                            temp_value, humidity_value = data.decode('utf-8').strip().split(',')
                            log_and_send_data(float(temp_value), float(humidity_value))

                        except socket.timeout:
                            # Timeout allows the loop to check shutdown_flag regularly
                            continue

                        except Exception as e:
                            print(f"Error receiving socket data: {e}")
                            break
            except socket.timeout:
                # No client connected yet, retry after timeout
                continue

        except Exception as e:
            print(f"Error with socket server: {e}")
            time.sleep(1)  # Wait a moment before retrying in case of an error
    
    s.close()
    print("Socket server closed.")

# Route to serve the main webpage
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/temperature/')
@app.route('/temperature/<int:hours>')
def temperature(hours=24):  # Default to 24 hours if not provided
    return render_template('temperature.html', input_hours=hours)

@app.route('/printers')
def printers():
    return render_template('printers.html')

@app.route('/leaderboard')
def leaderboard():
    # Sample leaderboard data
    ## OLD BEFORE RESET
    # players = [
    #     {'name': 'Aura', 'team_f_wins': 4, 'team_l_wins': 7, 'games_played': 15, 'h_count': 0},
    #     {'name': 'Ben', 'team_f_wins': 0, 'team_l_wins': 3, 'games_played': 8, 'h_count': 0},
    #     {'name': 'Emlyn', 'team_f_wins': 0, 'team_l_wins': 1, 'games_played': 3, 'h_count': 0},
    #     {'name': 'Jonathan', 'team_f_wins': 2, 'team_l_wins': 9, 'games_played': 19, 'h_count': 0},
    #     {'name': 'Omar', 'team_f_wins': 4, 'team_l_wins': 2, 'games_played': 9, 'h_count': 1},
    #     {'name': 'Rajitha', 'team_f_wins': 0, 'team_l_wins': 0, 'games_played': 6, 'h_count': 0},
    #     {'name': 'Riccardo', 'team_f_wins': 1, 'team_l_wins': 0, 'games_played': 1, 'h_count': 1},
    #     {'name': 'Rob', 'team_f_wins': 4, 'team_l_wins': 5, 'games_played': 19, 'h_count': 2},
    #     {'name': 'Roopika', 'team_f_wins': 1, 'team_l_wins': 2, 'games_played': 6, 'h_count': 0},
    #     {'name': 'Sarah', 'team_f_wins': 1, 'team_l_wins': 6, 'games_played': 16, 'h_count': 3},
    #     {'name': 'Villanelle', 'team_f_wins': 2, 'team_l_wins': 3, 'games_played': 12, 'h_count': 0},
    # ]
    ## APRIL RESET    
    players = [
        {'name': 'Aura', 'team_f_wins'      : 0, 'team_l_wins': 0, 'games_played': 0, 'h_count': 0},
        {'name': 'Ben', 'team_f_wins'       : 0, 'team_l_wins': 0, 'games_played': 0, 'h_count': 0},
        {'name': 'Emlyn', 'team_f_wins'     : 0, 'team_l_wins': 0, 'games_played': 0, 'h_count': 0},
        {'name': 'Jonathan', 'team_f_wins'  : 0, 'team_l_wins': 2, 'games_played': 4, 'h_count': 1},
        {'name': 'Omar', 'team_f_wins'      : 0, 'team_l_wins': 0, 'games_played': 0, 'h_count': 0},
        {'name': 'Rajitha', 'team_f_wins'   : 0, 'team_l_wins': 1, 'games_played': 4, 'h_count': 0},
        {'name': 'Riccardo', 'team_f_wins'  : 0, 'team_l_wins': 0, 'games_played': 0, 'h_count': 0},
        {'name': 'Rob', 'team_f_wins'       : 0, 'team_l_wins': 0, 'games_played': 0, 'h_count': 0},
        {'name': 'Roopika', 'team_f_wins'   : 1, 'team_l_wins': 2, 'games_played': 4, 'h_count': 1},
        {'name': 'Sarah', 'team_f_wins'     : 0, 'team_l_wins': 2, 'games_played': 4, 'h_count': 0},
        {'name': 'Villanelle', 'team_f_wins': 1, 'team_l_wins': 2, 'games_played': 4, 'h_count': 2},
    ]

    # Calculate total wins and win ratio for each player
    for player in players:
        total_wins = player['team_f_wins'] + player['team_l_wins']
        player['total_wins'] = total_wins
        if player['games_played'] > 0:
            player['win_ratio'] = round(total_wins / player['games_played'], 2)
        else:
            player['win_ratio'] = 0.0  # Handle case where no games have been played

    # Sort players by win ratio in descending order
    players.sort(key=lambda x: x['win_ratio'], reverse=True)

    # Calculate total wins for F and L teams
    total_f_wins = 0    # total_f_wins = 9
    total_l_wins = 0    # total_l_wins = 9

    return render_template('leaderboard.html', players=players, total_f_wins=total_f_wins, total_l_wins=total_l_wins)

# Route to fetch latest news
@app.route('/news')
def news():
    try:
        news = []

        # Function to fetch and parse RSS feed
        def fetch_rss(url):
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for bad response
            root = ET.fromstring(response.content)
            return root.findall(".//item")[:6]  # Get latest 6 articles

        # Fetch articles from both RSS feeds
        bbc_items = fetch_rss(BBC_RSS_FEED)
        onion_items = fetch_rss(ONION_RSS_FEED)
        mash_items = fetch_rss(DAILY_MASH_RSS_FEED)

        # Extract and combine articles from all sources
        for item in bbc_items + onion_items + mash_items:
            title = item.find("title").text
            link = item.find("link").text
            news.append({"title": title, "link": link})

        # Shuffle the combined list to mix news randomly
        random.shuffle(news)

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

        # Extract relevant weather information safely
        weather = {
            'city': data.get('name', 'Unknown'),
            'temperature': data['main'].get('temp', 'N/A'),
            'description': data['weather'][0].get('description', 'N/A').title(),
            'id': data['weather'][0].get('id', 0),
            'icon': data['weather'][0].get('icon', '')
        }
        return jsonify(weather)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/departures/', defaults={'departure_station': 'LCN', 'number_of_departures': 6}, methods=['GET'])
@app.route('/departures/<departure_station>/', defaults={'number_of_departures': 6}, methods=['GET'])
@app.route('/departures/<departure_station>/<number_of_departures>', methods=['GET'])
def departures(departure_station, number_of_departures):
    # departure_station = "LCN"  # Set your departure station here

    # Ensure the departure_station is in uppercase
    departure_station = departure_station.upper()

    # Ensure the number_of_departures is an int
    number_of_departures = int(number_of_departures)

    if not departure_station:
        return "Please provide a departureStation parameter", 400

    # Subtract 1 due to the random train added
    APIRequest = f"""
        <x:Envelope xmlns:x="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ldb="http://thalesgroup.com/RTTI/2017-10-01/ldb/" xmlns:typ4="http://thalesgroup.com/RTTI/2013-11-28/Token/types">
            <x:Header>
                <typ4:AccessToken>
                    <typ4:TokenValue>{TRAIN_API_KEY}</typ4:TokenValue>
                </typ4:AccessToken>
            </x:Header>
            <x:Body>
                <ldb:GetDepBoardWithDetailsRequest>
                    <ldb:numRows>{number_of_departures - 1}</ldb:numRows>
                    <ldb:crs>{departure_station}</ldb:crs>
                    <ldb:filterCrs></ldb:filterCrs>
                    <ldb:filterType>to</ldb:filterType>
                    <ldb:timeOffset>0</ldb:timeOffset>
                    <ldb:timeWindow>120</ldb:timeWindow>
                </ldb:GetDepBoardWithDetailsRequest>
            </x:Body>
        </x:Envelope>
    """

    headers = {'Content-Type': 'text/xml'}

    # try:
    response = requests.post(TRAIN_API_URL, data=APIRequest, headers=headers)
    response.raise_for_status()

    # Parse the XML response
    departure_station_name, departure_station_code, departure_data = parse_departures(response.text)
    if departure_data == None:
        raise Exception("parsing returned None. Rob's Fault")
    
    # Render the departures template with the parsed data
    # threading.Thread(target=speak_first_train, args=(departure_data,), daemon=True).start()
    # speak_first_train(departure_data)
    
    # return response.text
    
    # Render the departures template with the parsed data
    return render_template('departures.html', 
                           departure_data = departure_data, 
                           departure_station_name = departure_station_name)

@app.route('/train_departures/<departure_station>', methods=['GET'])
def train_departures(departure_station):
    # Ensure the departure_station is in uppercase
    departure_station = departure_station.upper()

    # You can set a default value here if needed
    # departure_station = departure_station or "LCN"  # Uncomment if you want a default value

    # Prepare the XML request
    APIRequest = f"""
        <x:Envelope xmlns:x="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ldb="http://thalesgroup.com/RTTI/2017-10-01/ldb/" xmlns:typ4="http://thalesgroup.com/RTTI/2013-11-28/Token/types">
            <x:Header>
                <typ4:AccessToken>
                    <typ4:TokenValue>{TRAIN_API_KEY}</typ4:TokenValue>
                </typ4:AccessToken>
            </x:Header>
            <x:Body>
                <ldb:GetDepBoardWithDetailsRequest>
                    <ldb:numRows>10</ldb:numRows>
                    <ldb:crs>{departure_station}</ldb:crs>
                    <ldb:filterCrs></ldb:filterCrs>
                    <ldb:filterType>to</ldb:filterType>
                    <ldb:timeOffset>0</ldb:timeOffset>
                    <ldb:timeWindow>120</ldb:timeWindow>
                </ldb:GetDepBoardWithDetailsRequest>
            </x:Body>
        </x:Envelope>
    """

    headers = {'Content-Type': 'text/xml'}

    try:
        response = requests.post(TRAIN_API_URL, data=APIRequest, headers=headers)
        response.raise_for_status()

        # Parse the XML response
        departure_station_name, departure_station_code, departure_data = parse_departures(response.text)
        if departure_data is None:
            return jsonify({"error": "Parsing returned None."}), 500

        # Return a JSON response
        return jsonify({
            "station_name": departure_station_name,
            "station_code": departure_station_code,
            "departures": departure_data  # Ensure this is a list of departures
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def parse_departures(xml_data):

    # Parse the XML
    root = ET.fromstring(xml_data)

    # Use the namespaces defined in the XML to correctly access elements
    namespaces = {
        'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
        'ldb': 'http://thalesgroup.com/RTTI/2017-10-01/ldb/',
        'lt4': 'http://thalesgroup.com/RTTI/2015-11-27/ldb/types',
        'lt5': 'http://thalesgroup.com/RTTI/2016-02-16/ldb/types',
        'lt7': 'http://thalesgroup.com/RTTI/2017-10-01/ldb/types'
    }
    
    departure_data = []

    # Extract station details
    departure_station_name = (name_element.text if (name_element := root.find('.//lt4:locationName', namespaces)) is not None else "Unknown")
    departure_station_code = (code_element.text if (code_element := root.find('.//lt4:crs', namespaces)) is not None else "Unknown")
    # print(f"Departure Station: {departure_station_name} ({departure_station_code})")

    # Extract train services
    services = root.findall('.//lt7:service', namespaces)
    for service in services:
        std = (std_element.text if (std_element := service.find('.//lt4:std', namespaces)) is not None else "Unknown")
        etd = (etd_element.text if (etd_element := service.find('.//lt4:etd', namespaces)) is not None else "Unknown")
        platform = (platform_element.text if (platform_element := service.find('.//lt4:platform', namespaces)) is not None else "No Platform Yet")
        operator = (operator_element.text if (operator_element := service.find('.//lt4:operator', namespaces)) is not None else "Unknown")
        destination_name = (std_element.text if (std_element := service.find('.//lt5:destination/lt4:location/lt4:locationName', namespaces)) is not None else "Unknown")
        calling_points = service.findall('.//lt7:callingPoint', namespaces)
        # Extract (locationName, st) for each calling point or provide fallback
        intermediate_destinations = [
            (cp.find('lt7:locationName', namespaces).text, 
            cp.find('lt7:st', namespaces).text)
            for cp in calling_points
            if cp.find('lt7:locationName', namespaces) is not None and
            cp.find('lt7:st', namespaces) is not None
        ] if calling_points else [("Unknown", "Unknown")]  

        # print(f"\nTrain at {std} (Expected: {etd}) on Platform {platform}")
        # print(f"Operator: {operator}")
        # print(f"Destination: {destination_name}")

        departure_data.append({'std': std, 'etd': etd, 'platform': platform, 'operator': operator, 'destination_name': destination_name, 'intermediate_destinations': intermediate_destinations})

    # Check if there are at least 4 trains in the departure_data
    if len(departure_data) >= 4:
        # Extract std times from the 2nd and 3rd entries
        std_time_1 = datetime.datetime.strptime(departure_data[2]['std'], '%H:%M')
        std_time_2 = datetime.datetime.strptime(departure_data[3]['std'], '%H:%M')
        
        # Generate a random std time between the 2nd and 3rd trains' std times
        random_std_time = random_time_between(std_time_1, std_time_2)
        random_std = random_std_time.strftime('%H:%M')
    else:
        # Handle cases with fewer than 4 trains
        current_time = datetime.datetime.now()
        one_hour_later = current_time + datetime.timedelta(hours=1)
        random_std = one_hour_later.strftime('%H:%M')  # Format the time as HH:MM

    # Randomly choose between trains to add
    train_options = [
        {'platform': '9¾', 'operator': 'Hogwarts Express', 'destination_name': 'Hogsmeade'},
        {'platform': '6', 'operator': 'Polar Express', 'destination_name': 'North Pole'},
        {'platform': '6', 'operator': 'Thomas The Tank Engine', 'destination_name': 'Vicarstown'},
        {'platform': '6', 'operator': 'Snowpiercer', 'destination_name': 'New Eden'},
        {'platform': '6', 'operator': 'Orient Express', 'destination_name': 'Istanbul'},
        {'platform': '6', 'operator': 'Amtrak California Zephyr', 'destination_name': 'Chicago Union Station'},
        {'platform': '6', 'operator': 'VIA Rail The Canadian', 'destination_name': 'Vancouver Pacific Central Station'},
        {'platform': '6', 'operator': 'Metro-North Railroad', 'destination_name': 'Grand Central'},
        {'platform': '6', 'operator': 'NSW TrainLink', 'destination_name': 'Melbourne Southern Cross'},
        {'platform': '6', 'operator': 'The Ghan', 'destination_name': 'Darwin'},
        {'platform': '6', 'operator': 'Kiwi Rail', 'destination_name': 'Auckland Strand'},
        {'platform': '6', 'operator': 'Deutsche Bahn', 'destination_name': 'Bielefeld Hbf'},
        {'platform': '6', 'operator': 'ОАО Trans-Siberian', 'destination_name': 'Vladivostok'},
        {'platform': '6', 'operator': 'Trenes Argentinos', 'destination_name': 'Buenos Aires Retiro'}
    ]

    random_train = random.choice(train_options)

    # Insert the randomly chosen train into the departure_data
    departure_data.insert(min(3, len(departure_data)), 
                        {'std': random_std, 'etd': 'On time', **random_train})

    return departure_station_name, departure_station_code, departure_data

engine = pyttsx3.init()

def speak_first_train(departure_data):
    # while True:
        # Wait for 5 minutes        
        # time.sleep(300)  # 300 seconds = 5 minutes

    if departure_data and len(departure_data) > 0:
        # Get the first train's details
        first_train = departure_data[0]
        std = first_train['std']
        destination_name = first_train['destination_name']
        platform = first_train['platform']
        operator = first_train['operator']
        
        # Construct the speech text
        speech_text = f"The next train to depart from platform {platform} will be the {std} {operator} service to {destination_name}."
        
        # Speak the text
        engine.say(speech_text)
        engine.runAndWait()

@app.route('/flights')
def flights():
    return render_template('flights.html')

def get_humberside_flight_data():
    """
    Fetches live flight data from Humberside's API and parses the flight departures.

    Returns:
        list: A list of dictionaries containing departure flight details.
    """
    url = "https://hum.hangar.kmp.co.uk/api/liveflightsapi/retrieveliveflights?iataCode=hum"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        # Add other headers here if required (e.g., Authorization)
    }
    
    try:
        # Fetch the JSON data from the API
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for HTTP request issues
        flight_data = response.json()
        
        # Extract departures
        departures = flight_data.get("departures", [])
        
        # Parse relevant details
        parsed_departures = []
        for flight in departures:
            # Format scheduledDateTime and aggregatedDateTime to show only the time
            scheduled_time = (
                datetime.datetime.strptime(flight.get("scheduledDateTime"), "%Y-%m-%dT%H:%M:%S").strftime("%H:%M")
                if flight.get("scheduledDateTime")
                else None
            )
            aggregated_time = (
                datetime.datetime.strptime(flight.get("aggregatedDateTime"), "%Y-%m-%dT%H:%M:%S").strftime("%H:%M")
                if flight.get("aggregatedDateTime")
                else None
            )

            # Capitalize the location names
            parsed_departures.append({
                "flightNumber": flight.get("flightNumber"),
                "scheduledDateTime": scheduled_time,
                "aggregatedDateTime": aggregated_time,
                "location": flight.get("location", "").title(),  # Capitalize first letter of each word
                "airlineName": flight.get("airlineName"),
                "airlineLogo": flight.get("airlineLogo"),
                "statusMessage": flight.get("statusMessage", {}).get("mainMessage"),
            })

        # List of custom flights
        custom_flights = [
            {
                "location": "Lompoc Penitentiary",
                "flightNumber": "C-123",
                "airlineName": "Con Air",
                "airlineLogo": "static/airlines/Con_air_logo.png",                
                "statusMessage": "On Time",
            },
            {
                "location": "Los Angeles",
                "flightNumber": "OA815",
                "airlineName": "Oceanic Airlines",
                "airlineLogo": "static/airlines/Oceanic_airlines_logo.png",     
                "statusMessage": "Cancelled",
            },
            {
                "location": "Los Angeles",
                "flightNumber": "NWA121",
                "airlineName": "Northwest Airlines",
                "airlineLogo": "static/airlines/Snakes_on_a_plane_logo.png",     
                "statusMessage": "Delayed",
            }
        ]

        # Randomly select a custom flight
        custom_flight = random.choice(custom_flights)

        # Generate the departure time for the custom flight based on conditions
        if len(parsed_departures) == 0:
            # If it's the only flight, set the time to 1 hour from now
            custom_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M")
        elif len(parsed_departures) == 1 or len(parsed_departures) == 2:
            # If there's only one or two flights, set the time to 1 hour from now
            custom_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M")
        else:
            # If there are more than two flights, set the time between the 3rd and 4th flight
            flight_3_time = datetime.datetime.strptime(parsed_departures[2]["aggregatedDateTime"], "%H:%M")
            flight_4_time = datetime.datetime.strptime(parsed_departures[3]["aggregatedDateTime"], "%H:%M")
            
            # Check if there is enough time between flight 3 and flight 4 to generate a random time
            time_diff = (flight_4_time - flight_3_time).total_seconds() // 60  # in minutes

            # If the difference is less than 1 minute, set a default time or adjust as needed
            if time_diff < 1:
                custom_time = (flight_3_time + datetime.timedelta(minutes=1)).strftime("%H:%M")
            else:
                # Generate a random departure time between the 3rd and 4th flights
                random_time_delta = random.randint(1, int(time_diff))  # Random minutes
                custom_time = (flight_3_time + datetime.timedelta(minutes=random_time_delta)).strftime("%H:%M")

        custom_flight["aggregatedDateTime"] = custom_time  # Assign the generated time to the custom flight

        # Manually add the custom flight between the 3rd and 4th flights in the list
        if len(parsed_departures) >= 3:
            parsed_departures.insert(3, custom_flight)  # Insert after the 3rd flight
        else:
            parsed_departures.append(custom_flight)  # Add to the end if fewer than 3 flights
        
        return parsed_departures
    
    except requests.RequestException as e:
        print(f"Error fetching flight data: {e}")
        return []

@app.route('/humberside_airport')
def humberside_airport():
    try:
        # Use the helper function to get the flights with the custom flight added
        departures = get_humberside_flight_data()

        # Render template with data
        return render_template(
            'humberside_airport.html',
            departures=departures
        )
    except Exception as e:
        # Handle error case, such as API failure
        return jsonify({"error": str(e)}), 500

@app.route('/flight_departures')
def flight_departures():
    try:
        # Fetch the departure data (assuming this function is defined)
        departures = get_humberside_flight_data()  # Should return a list of flight data
        
        # Prepare the data to send back to the client
        departures_data = {
            "departures": [
                {
                    "flightNumber": flight.get("flightNumber", ""),
                    "scheduledDateTime": flight.get("scheduledDateTime", ""),
                    "aggregatedDateTime": flight.get("aggregatedDateTime", ""),
                    "location": flight.get("location", "").title(),  # Capitalize location
                    "airlineName": flight.get("airlineName", ""),
                    "airlineLogo": flight.get("airlineLogo", ""),
                    "statusMessage": flight.get("statusMessage", "")
                }
                for flight in departures
            ]
        }

        return jsonify(departures_data)
    
    except Exception as e:
        # Handle errors and return an error message
        return jsonify({"error": str(e)}), 500

def get_heathrow_flight_data():
    """
    Fetches live flight data from Heathrow's API and parses the flight departures.

    Returns:
        list: A list of dictionaries containing departure flight details.
    """
    # Get the current date and time in UTC
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=0.05)

    # Define the URL with query parameters
    url = 'https://api-dp-prod.dp.heathrow.com/pihub/flights/departures'
    params = {
        'date': now.strftime("%Y-%m-%d"),
        'orderBy': 'localDepartureTime',
        'excludeCodeShares': 'true'
    }
    headers = {
        'Origin': 'https://www.heathrow.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Encoding': 'gzip, deflate',
        'Accept': 'application/json',
    }

    try:
        # Make the GET request
        response = requests.get(url, params=params, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()

            parsed_departures = []

            for flight in data:
                flight_service = flight.get('flightService', {})

                # Extract flight number
                flight_number = flight_service.get('icaoFlightIdentifier')

                # Extract flight status message
                status_message = flight_service.get('aircraftMovement', {}).get('aircraftMovementStatus', [{}])[0].get('message')

                # Handling departure time
                departure_time_str = None
                if flight_service.get('aircraftMovement', {}).get('aircraftMovementStatus', [{}])[0].get('statusData'):
                    departure_time_data = flight_service.get('aircraftMovement', {}).get('aircraftMovementStatus', [{}])[0].get('statusData')[0]
                    departure_time_str = departure_time_data.get('data')  # e.g., '06:16'
                
                # If we have a valid time string, convert it to datetime
                departure_time = None
                if departure_time_str:
                    try:
                        departure_time = datetime.datetime.strptime(departure_time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                        departure_time = departure_time.replace(tzinfo=datetime.timezone.utc)  # Make departure time UTC aware
                    except ValueError:
                        departure_time = None

                # Only proceed if the flight departs after the current time
                if departure_time and departure_time > now and departure_time <= now + datetime.timedelta(hours=1):
                    # Extract destination location
                    ports_of_call = flight_service.get('aircraftMovement', {}).get('route', {}).get('portsOfCall', [])
                    destination_location = 'Unknown'  # Default value

                    # Search for the DESTINATION portOfCall
                    for port in ports_of_call:
                        if port.get('portOfCallType') == 'DESTINATION':
                            destination_location = port.get('airportFacility', {}).get('airportCityLocation', {}).get('name', 'Unknown')
                            break  # Exit loop once the destination is found

                    # Extract airline info
                    airline_name = flight_service.get('airlineParty', {}).get('name', 'Unknown')
                    airline_logo_url = flight_service.get('airlineParty', {}).get('tailfinImageUrl', '')

                    # Appending the parsed departure
                    parsed_departures.append({
                        "flightNumber": flight_number,
                        "aggregatedDateTime": departure_time.strftime("%H:%M") if departure_time else 'Unknown',
                        "location": destination_location,
                        "airlineName": airline_name,
                        "airlineLogo": airline_logo_url,
                        "statusMessage": status_message
                    })    

            # List of custom flights
            custom_flights = [
                {
                    "location": "Lompoc Penitentiary",
                    "flightNumber": "C-123",
                    "airlineName": "Con Air",
                    "airlineLogo": "static/airlines/Con_air_logo.png",                
                    "statusMessage": "On Time",
                },
                {
                    "location": "Los Angeles",
                    "flightNumber": "OA815",
                    "airlineName": "Oceanic Airlines",
                    "airlineLogo": "static/airlines/Oceanic_airlines_logo.png",     
                    "statusMessage": "Cancelled",
                },
                {
                    "location": "Los Angeles",
                    "flightNumber": "NWA121",
                    "airlineName": "Northwest Airlines",
                    "airlineLogo": "static/airlines/Snakes_on_a_plane_logo.png",     
                    "statusMessage": "Delayed",
                }
            ]

            # Randomly select a custom flight
            custom_flight = random.choice(custom_flights)

            # Generate the departure time for the custom flight based on conditions
            if len(parsed_departures) == 0:
                # If it's the only flight, set the time to 1 hour from now
                custom_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M")
            elif len(parsed_departures) == 1 or len(parsed_departures) == 2:
                # If there's only one or two flights, set the time to 1 hour from now
                custom_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M")
            else:
                # If there are more than two flights, set the time between the 3rd and 4th flight
                flight_3_time = datetime.datetime.strptime(parsed_departures[2]["aggregatedDateTime"], "%H:%M")
                flight_4_time = datetime.datetime.strptime(parsed_departures[3]["aggregatedDateTime"], "%H:%M")
                
                # Ensure there is enough time between the 3rd and 4th flight
                time_difference = (flight_4_time - flight_3_time).total_seconds() // 60
                if time_difference > 0:
                    # Generate a random departure time between the 3rd and 4th flights
                    random_time_delta = random.randint(1, int(time_difference))  # Random minutes
                    custom_time = (flight_3_time + datetime.timedelta(minutes=random_time_delta)).strftime("%H:%M")
                else:
                    # Default behavior if there's no valid time difference
                    custom_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M")

            custom_flight["aggregatedDateTime"] = custom_time  # Assign the generated time to the custom flight

            # Manually add the custom flight between the 3rd and 4th flights in the list
            if len(parsed_departures) >= 3:
                parsed_departures.insert(3, custom_flight)  # Insert after the 3rd flight
            else:
                parsed_departures.append(custom_flight)  # Add to the end if fewer than 3 flights        

        return parsed_departures
    
    except requests.RequestException as e:
        print(f"Error fetching flight data: {e}")
        return []

@app.route('/heathrow_airport')
def heathrow_airport():
    try:
        # Use the helper function to get the flights with the custom flight added
        departures = get_heathrow_flight_data()

        # Render template with data
        return render_template(
            'heathrow_airport.html',
            departures=departures
        )
    except Exception as e:
        # Handle error case, such as API failure
        return jsonify({"error": str(e)}), 500   

northbound = [
    {"LAC": "07:30", "train_station": "07:40", "lincoln_hotel": "07:45", "lawress_hall": "07:55"},
    {"LAC": "08:30", "train_station": "08:40", "lincoln_hotel": "08:45", "lawress_hall": "08:55"},
    {"LAC": "13:00", "train_station": "13:10", "lincoln_hotel": "13:15", "lawress_hall": "13:25"},
    {"LAC": "16:30", "train_station": "16:40", "lincoln_hotel": "16:45", "lawress_hall": "16:55"},
    {"LAC": "17:30", "train_station": "17:40", "lincoln_hotel": "17:45", "lawress_hall": "17:55"}
]

southbound = [
    {"lawress_hall": "08:05", "lincoln_hotel": "08:15", "train_station": "08:20", "LAC": "08:25"},
    {"lawress_hall": "12:30", "lincoln_hotel": "12:40", "train_station": "12:45", "LAC": "12:55"},
    {"lawress_hall": "16:05", "lincoln_hotel": "16:15", "train_station": "16:20", "LAC": "16:25"},
    {"lawress_hall": "17:05", "lincoln_hotel": "17:15", "train_station": "17:20", "LAC": "17:25"}
]

@app.route('/campus_linc_bus')
def campus_linc_bus():
    current_time = datetime.datetime.now().strftime('%H:%M')

    def get_next_departure(times):
        for time in times:
            if time > current_time:
                return time
        return None

    stop_keys = ['LAC', 'train_station', 'lincoln_hotel', 'lawress_hall']

    # Build dictionaries of next departures for each stop
    next_north_times = {}
    next_south_times = {}

    for key in stop_keys:
        north_times = [row[key] for row in northbound if row[key]]
        south_times = [row[key] for row in southbound if row[key]]
        next_north_times[key] = get_next_departure(north_times)
        next_south_times[key] = get_next_departure(south_times)

    return render_template(
        'campus_linc_bus.html',
        northbound=northbound,
        southbound=southbound,
        current_time=current_time,
        next_north_times=next_north_times,
        next_south_times=next_south_times
    )


@app.route('/campus_linc_bus_stop/<stop_name>')
def stop_info(stop_name):
    stop_labels = {
        'LAC': 'LAC (UoL)',
        'train_station': 'Train Station',
        'lincoln_hotel': 'Lincoln Hotel',
        'lawress_hall': 'Lawress Hall'
    }

    label = stop_labels.get(stop_name)
    if not label:
        return f"<h1>Unknown stop: {stop_name}</h1>", 404

    # Initialize empty lists for times
    north_times = []
    south_times = []

    # Get current time in format HH:MM
    current_time = datetime.datetime.now().strftime('%H:%M')

    # Northbound departures logic
    if stop_name in ['LAC', 'train_station', 'lincoln_hotel']:
        north_times = [trip[stop_name] for trip in northbound if stop_name in trip]

    # Southbound departures logic
    if stop_name in ['lawress_hall', 'train_station', 'lincoln_hotel']:
        south_times = [trip[stop_name] for trip in southbound if stop_name in trip]

    # Find the next departure time
    def get_next_departure(times):
        for time in times:
            if time > current_time:
                return time
        return None  # In case no times are left

    next_north_time = get_next_departure(north_times)
    next_south_time = get_next_departure(south_times)

    return render_template(
        'campus_linc_bus_stop.html',
        label=label,
        north_times=north_times,
        south_times=south_times,
        current_time=current_time,
        next_north_time=next_north_time,
        next_south_time=next_south_time
    )


@app.route('/bus_map')
def bus_map():
    return render_template('bus_map.html')

@app.route('/bus_data')
def bus_data():
    # Define the bounding box coordinates [minLongitude, minLatitude, maxLongitude, maxLatitude]
    bounding_box = "-0.60,53.20,-0.47,53.28"

    url_pc_coaches = "https://data.bus-data.dft.gov.uk/api/v1/datafeed/7861/?api_key=" + OPEN_BUS_DATA_API_KEY + "&boundingBox=" + bounding_box
    url_stagecoach_east_midlands = "https://data.bus-data.dft.gov.uk/api/v1/datafeed/7035/?api_key=" + OPEN_BUS_DATA_API_KEY + "&boundingBox=" + bounding_box

    response_pc_coaches = requests.get(url_pc_coaches)
    response_stagecoach_east_midlands = requests.get(url_stagecoach_east_midlands)

    geojson_pc_coaches = vehicle_data_xml_to_geojson(response_pc_coaches.content)
    geojson_stagecoach_east_midlands = vehicle_data_xml_to_geojson(response_stagecoach_east_midlands.content)

    # Combine features from both GeoJSON responses
    combined_features = geojson_pc_coaches['features'] + geojson_stagecoach_east_midlands['features']
    combined_geojson = {
        "type": "FeatureCollection",
        "features": combined_features
    }

    return jsonify(combined_features)

def vehicle_data_xml_to_geojson(xml_data):
    """Convert the XML vehicle data to GeoJSON format."""
    root = ET.fromstring(xml_data)
    namespace = {"siri": "http://www.siri.org.uk/siri"}
    
    features = []
    for vehicle in root.findall(".//siri:VehicleActivity", namespace):
        location = vehicle.find(".//siri:VehicleLocation", namespace)
        longitude = float(location.find("siri:Longitude", namespace).text)
        latitude = float(location.find("siri:Latitude", namespace).text)

        # Extract recorded time and format it
        recorded_time = vehicle.find(".//siri:RecordedAtTime", namespace).text
        formatted_time = format_time(recorded_time)

        # Build GeoJSON feature
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [longitude, latitude]
            },
            "properties": {
                "vehicleRef": vehicle.find(".//siri:VehicleRef", namespace).text,
                "lineRef": vehicle.find(".//siri:LineRef", namespace).text,
                "originName": vehicle.find(".//siri:OriginName", namespace).text,
                "destinationName": vehicle.find(".//siri:DestinationName", namespace).text,
                "operatorRef": vehicle.find(".//siri:OperatorRef", namespace).text,
                "recordedAtTime": formatted_time
            }
        }

        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}
    return geojson

def format_time(iso_time):
    """Convert ISO 8601 time to a more readable format."""
    dt = datetime.datetime.fromisoformat(iso_time)
    return dt.strftime('%d %b %Y, %I:%M %p')  # Example: 21 Oct 2024, 08:53 AM

# Generate a random time between two given times
def random_time_between(start, end):
    """Generate a random time between two datetime objects."""
    delta = end - start
    if delta.total_seconds() <= 0:
        raise ValueError("End time must be greater than start time.")
    random_seconds = random.randint(1, int(delta.total_seconds() - 1))  # Ensure the random time is strictly between
    return start + datetime.timedelta(seconds=random_seconds)
        
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

def shutdown_gracefull(signum, frame):
    """Signal handler to stop the socket thread and clean up."""
    print("Shutdown signal received. Stopping socket thread and Flask server...")
    
    # Stop the socket thread
    shutdown_flag.set()
    if socket_thread.is_alive():
        socket_thread.join()
    print("Socket thread stopped.")
    
    # Forcefully stop the Flask-SocketIO server
    os._exit(0)  # Forcefully exit the Flask application


# Register signal handlers for SIGINT and SIGTERM
signal.signal(signal.SIGINT, shutdown_gracefull)
signal.signal(signal.SIGTERM, shutdown_gracefull)

@app.route('/image/<image_name>')
def image(image_name):
    """
    This route handles the image display.

    The primary issue in your original code was the line:
    `image_name = image_name.get(image_name)`

    The `image_name` variable is already a string containing the value from the URL.
    You cannot call `.get()` on a string, as that method is for dictionaries.
    This corrected code simply uses the `image_name` variable directly.
    """

    # The image exists, so render the template and pass the necessary variables.
    image_url = url_for('static', filename=f"{image_name}.jpg")
    return render_template('image.html', image_name=image_name, image_url=image_url)

if __name__ == '__main__':

    # Load historical data from the CSV file when the server starts
    # load_data_from_csv()

    print("Socket Thead Starting")
    # Start a background thread to receive data from the internal socket
    socket_thread = threading.Thread(target=receive_socket_data)
    socket_thread.daemon = True
    socket_thread.start()


    print("Flask App Starting")
    # Start the Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
