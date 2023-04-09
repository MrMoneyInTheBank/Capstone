import pandas as pd
import yfinance as yf

# Define the list of cryptocurrencies
cryptocurrencies = ['BTC-USD', 'ETH-USD', 'XRP-USD', 'BCH-USD', 'LTC-USD',
                    'EOS-USD', 'XTZ-USD', 'LINK-USD', 'XLM-USD', 'ADA-USD']

# Fetch historical price data for each cryptocurrency
historical_data = {}

for symbol in cryptocurrencies:
    data = yf.download(symbol, period="max")
    historical_data[symbol] = data

# Find the minimum length of data for all cryptocurrencies
min_length = min([len(historical_data[symbol]) for symbol in cryptocurrencies])

# Slice the data to have equal amount of data for every coin
for symbol in cryptocurrencies:
    historical_data[symbol] = historical_data[symbol].tail(min_length)

# Create a DataFrame to store the closing prices
df = pd.DataFrame()

# Extract the closing prices for each cryptocurrency
for symbol in cryptocurrencies:
    df[symbol] = historical_data[symbol]['Close']

# Save the DataFrame as a CSV file
df.to_csv('historical_cryptocurrency_data.csv', index=True)
