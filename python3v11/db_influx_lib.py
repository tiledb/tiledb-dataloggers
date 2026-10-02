from influxdb import InfluxDBClient

# Function to format data in line protocol for InfluxDB
def format_data_for_influxdb(measurement, tags, fields):
    tag_string = ','.join([f"{key}={value}" for key, value in tags.items()])
    field_string = ','.join([f"{key}={value}" for key, value in fields.items()])
    line = f"{measurement} {tag_string} {field_string}"
    return line


class TileInfluxDBClient:
    def __init__(self, host, port, database, username, password):
        # Initialize the InfluxDB client
        self.influxdbclient = InfluxDBClient(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database
        )
        print(f"Connected to: {host}, port: {port}, database: {database}....")

    def publish_datapoints(self, measurement, tag, field, value):
        data = [{
            "measurement": str(measurement),
            "tags": {
                "Device": str(tag)
            },
            "fields": {
                str(field): float(value),
            }
        }]

        try:
            print("Publishing Data")
            # write data points to database
            self.influxdbclient.write_points(data, database='TileMon')
        except KeyboardInterrupt:
            print("Influx command crashed")
