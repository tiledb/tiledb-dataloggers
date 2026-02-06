from influxdb import InfluxDBClient


# Function to format data in line protocol for InfluxDB
def format_data_for_influxdb(measurement, tags, fields):
	tag_string = ','.join(["{}={}".format(key, value) for key, value in tags.items()])
	field_string = ','.join(["{}={}".format(key, value) for key, value in fields.items()])
	line = "{} {} {}".format(measurement, tag_string, field_string)
	return line


class tile_influxdbclient:
	def __init__(self, host, port, database, username, password):

		# Initialize the InfluxDB client
		self = InfluxDBClient(host=host, port=port, username=username, password=password, database=database)
		
		print("Connected to: " + host + ", port: " + str(port) + ", database: " + database + "....")
		pass

#influx_client = InfluxDBClient(host=the_host, port=the_port)
#influx_client.switch_database('TileMon')

	
	def publish_datapoints(self, measurement, tag, field, value):
		data = []
#		for i in range(len(field)):
#			data.append(
#				 {
#					  "measurement": measurement,
#					  "tags": {
#							"Device": tag
#					  },
#					  "fields": {
#							field:         float(value),
#					  }
#				 }
#			)
		data.append({
				  "measurement": str(measurement),
				  "tags": {
						"Device": str(tag)
				  },
				  "fields": {
						str(field):         float(value),
				  }
			 })

		try:
			print("Publishing Data")
			#print(data)
			self.influxdbclient.write_points(data,database='TileMon')

		except KeyboardInterrupt:
			print("Influx command crashed")

