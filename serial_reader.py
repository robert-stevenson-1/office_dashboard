import socket
import serial
import time

# Serial connection settings
SERIAL_PORT = '/dev/ttyUSB0'  # Update with your serial port
BAUD_RATE = 115200

# Socket settings
HOST = '127.0.0.1'  # Localhost
PORT = 5001  # Port to communicate with the Flask server

# Function to read serial data and send it to the server
def send_serial_data():
    # Open serial connection
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        
        while True:
            try:
                if ser.in_waiting > 0:
                    # Read the line from the serial port, decode it, and strip any extraneous characters
                    line = ser.readline().decode('utf-8').strip()

                    # Example format: Temperature: 25.34 °C, Humidity: 60.23 %
                    if "Temperature" in line and "Humidity" in line:
                        # Extract the temperature and humidity values from the string
                        temp_value = line.split(" ")[1]
                        humidity_value = line.split(" ")[4].strip('%')

                        # Send the data to the Flask server via socket
                        message = f"{temp_value},{humidity_value}"
                        s.sendall(message.encode('utf-8'))
                        print(f"Sent data: {message}")
                        
                time.sleep(1)  # Adjust the delay based on how frequently you want to send data
            except Exception as e:
                print(f"Error in serial data reading: {e}")
                time.sleep(2)

if __name__ == "__main__":
    send_serial_data()
