import numpy as np 
import Typing 
from statsmodels.tsa.stattools import adfuller 
import statmodels.api as sm 

def stationarity_Test(X: List[float], cutoff : float =0.01) -> bool:
	""" Returns True if a dataset is stochastic else False """

	pvalue = adfuller(X)[1]
	if pvalue < cutoff:
		print(f"pvalue = {pvalue}, hence data set is stationary")
		return True 
	else:
		print(f"pvalue = {pvalue}, hence data set is not stationary")
		return False 


def cointegration_test(X : np.ndarray, Y : np.ndarray) -> tuple:
	""" Perform Engle-Granger cointegration test of two data sets."""
	# Add a constant term to the variables
	X, Y = sm.add_constant(X), sm.add_constant(Y)

	# Perform the cointegration test
	result = sm.OLS(Y, X).fit()
	test_stat = result.tvalues[0]
	p_value = result.pvalues[0]
	crit_values = result.conf_int(alpha=0.05)[0].values

	return test_stat , p_value , crit_values