import matplotlib.pyplot as plt
import matplotlib

import seaborn as sns
import pandas as pd

import datetime


readings: pd.DataFrame = pd.read_csv("./sensor_data.csv");
readings.columns = ["time", "temp", "humidity"];
# Parse the dateimte, and require an exact format match
readings.time = pd.to_datetime(readings.time, format="%Y-%m-%d %H:%M:%S", exact=True);

readings = readings[readings.time > datetime.datetime.fromtimestamp(1729184400.0)];
sns.set_theme();

plt.figure(figsize=[10, 5.62]);
ax = plt.subplot(2, 1, 1);
plt.xticks(rotation=90);
ax.set_title("Temprature");

sns.lineplot(readings[["time", "temp"]], x="time", y="temp", ax=ax);

ax = plt.subplot(2, 1, 2);
plt.xticks(rotation=90);
ax.set_title("Humidity");
sns.lineplot(readings[["time", "humidity"]], x="time", y="humidity", ax=ax);


plt.tight_layout();
plt.savefig("plot.png");
plt.show();
