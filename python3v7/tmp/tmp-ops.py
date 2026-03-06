from influxdb import InfluxDBClient

host = "localhost"
port = 8086
username = "user"
password = "password"
database = "mydb"

host = "piro-atlas-lab.fysik.su.se"
port = 8086
username = "tiledb"
password = "T1le-db-word!"
database = "tiledb"


client = InfluxDBClient(
    host=host,
    port=port,
    username=username,
    password=password,
    database=database
)

print(f"Connected to: {host}, port: {port}, database: {database}")

# Get all fields from CIS measurement
# result = client.query("SHOW FIELD KEYS FROM \"CIS\"")
# print(f"Result: {result}")

# # 1. Copy only valid fields (exclude pulse fields)
# query = """
# SELECT
#     hg_pedestal,
#     hg_peak,
#     hg_peak_idx,
#     hg_center,
#     hg_width,
#     lg_pedestal,
#     lg_peak,
#     lg_peak_idx,
#     lg_center,
#     lg_width,
#     delta_crc
# INTO "CIS_clean"
# FROM "CIS"
# GROUP BY *
# """

# client.query(query)
# print("Copied clean data to CIS_clean")

# # 2. Drop the corrupted measurement
# client.query('DROP MEASUREMENT "CIS"')
# print("Dropped old CIS")

# 3. Rename clean measurement back
# client.query('SELECT * INTO "CIS" FROM "CIS_clean" GROUP BY *')
client.query('DROP MEASUREMENT "CIS_Samples"')

print("Cleanup complete")