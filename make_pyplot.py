import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd


readings: pd.DataFrame = pd.read_csv("./sensor_data.csv");
readings.columns = ["time", "temp", "humidity"];
# Parse the dateimte, and require an exact format match
# readings.time = pd.to_datetime(readings.time, format="%Y-%m-%d %H:%M:%S", exact=True).astype(int);

# print(readings[readings.temp == 21.87]);
sns.set_theme();

plt.figure();
ax = plt.subplot(2, 1, 1);
ax.set_title("Temprature");
sns.lineplot(readings[["time", "temp"]], ax=ax);

ax = plt.subplot(2, 1, 2);
ax.set_title("Humidity");
sns.lineplot(readings[["time", "humidity"]], ax=ax);


plt.tight_layout();
plt.savefig("plot.png");
plt.show();
