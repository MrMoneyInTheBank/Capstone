import pandas as pd
import numpy as np
import statsmodels.api as sm
import seaborn as sns
import matplotlib.pyplot as plt

# Load the historical cryptocurrency data from the CSV file
df = pd.read_csv('historical_cryptocurrency_data.csv', index_col=0)
rows_with_missing_values = df.index[df.isnull().any(axis=1)]
df = df.drop(rows_with_missing_values)


results = {}

for i in range(len(df.columns)):
    for j in range(i+1, len(df.columns)):
        coin1 = df.columns[i]
        coin2 = df.columns[j]
        coint_rest = sm.tsa.stattools.coint(df[coin1], df[coin2])
        results[(coin1, coin2)] = coint_rest

p_values = {}
for coin1, coin2 in results:
    p_values[(coin1, coin2)] = results[(coin1, coin2)][1]


# Convert the dictionary to a DataFrame
results_df = pd.DataFrame(list(p_values.items()), columns=[
                          'Cryptocurrency Pair', 'p-value'])

# Split the cryptocurrency pair into separate columns
results_df[['Cryptocurrency 1', 'Cryptocurrency 2']] = pd.DataFrame(
    results_df['Cryptocurrency Pair'].tolist(), index=results_df.index)
results_df = results_df.drop(columns='Cryptocurrency Pair')

# Pivot the DataFrame to create a matrix suitable for a heatmap
heatmap_data = results_df.pivot(
    index='Cryptocurrency 1', columns='Cryptocurrency 2', values='p-value')

# Generate the heatmap
sns.heatmap(heatmap_data, annot=True, cmap="coolwarm",
            cbar_kws={'label': 'p-value'})
plt.title('Cointegration Heatmap')
plt.xlabel('Cryptocurrency 2')
plt.ylabel('Cryptocurrency 1')

plt.savefig('cointegration_heatmap.png')

plt.show()


