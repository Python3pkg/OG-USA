'''
------------------------------------------------------------------------
This script reads in data generated from the OSPC Tax Calcultor and
the 2009 IRS PUF. It then estimates tax functions tau_{s,t}(x,y), where
tau_{s,t} is the effective tax rate for a given age (s) in a particular
year (t), x is total labor income, and y is total capital income.

This Python script calls the following functions:
    gen_etr_grid:   generates summary grid points for effective tax rate
    gen_dmtrx_grid: generates summary grid points for derivative of
                    marginal tax rate with respect to labor income
    gen_dmtry_grid: generates summary grid points for derivative of
                    marginal tax rate with respect to capital income
    wsumsq:         generates weighted sum of squared residuals

This Python script outputs the following:
    TxFuncEst.pkl: pickle of dictionary with param_arr_S, AvgInc,
                   and elapsed_time
------------------------------------------------------------------------
'''
# Import packages
import time
import numpy as np
import numpy.random as rnd
import scipy.optimize as opt
try:
    import pickle as pickle
except:
    import pickle
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm

'''
------------------------------------------------------------------------
Set parameters and create objects for output
------------------------------------------------------------------------
S           = integer >= 3, number of periods an individual can live. S
              represents the lifespan in years between s_min and s_max
s_min       = integer > 0, minimum age relevant to the model
s_max       = integer > s_min, maximum age relevant to the model
tpers       = integer > 0, number of years to forecast
numparams   = integer > 0, number of parameters to estimate for the tax
              function for each age s and year t
etrparam_arr  = (s_max-s_min+1 x tpers x numparams) array, parameter
                values for the estimated effective tax rate functions
                for each age s and year t
mtrxparam_arr = (s_max-s_min+1 x tpers x numparams) array, parameter
                values for the estimated marginal tax rate functions of
                labor income for each age s and year t
AvgInc      = (tpers,) vector, average income in each year
TotPop_yr   = (tpers,) vector, total population according to Weights
              variable in each year
PopPct_age  = (s_max-s_min+1, tpers) matrix, population percent of each
              age as percent of total population in each year
desc_data   = boolean, =True if print descriptive stats for each age s
              and year t
graph_data  = boolean, =True if print 3D graph of data for each age s
              and year t
graph_est   = boolean, =True if print 3D graph of data and estimated tax
              function for each age s and year t
dmtrgr_est  = boolean, =True if print 3D graph of derivative of
              estimated marginal tax rates for each age s and year t
cmap1       = matplotlib setting, set color map for 3D surface plots
beg_yr      = integer >= 2015, beginning year for forecasts
end_yr      = integer >= beg_yr, ending year for forecasts
years_list  = [beg_yr-end_yr+1,] vector, iterable list of years to be
              forecast
data_folder = string, path of hard drive folder where data files reside
start_time  = scalar, current processor time in seconds (float)
------------------------------------------------------------------------
'''
S = int(80)
s_min = int(21)
s_max = int(100)
tpers = int(10)
numparams = int(10)
etrparam_arr = np.zeros((s_max - s_min + 1, tpers, numparams))
mtrxparam_arr = np.zeros((s_max - s_min + 1, tpers, numparams))
AvgInc = np.zeros(tpers)
TotPop_yr = np.zeros(tpers)
PopPct_age = np.zeros((s_max-s_min+1, tpers))
desc_data = False
graph_data = False
graph_est = False
dmtrgr_est = False
cmap1 = matplotlib.cm.get_cmap('summer')
# cmap1 = matplotlib.cm.get_cmap('jet')
# cmap1 = matplotlib.cm.get_cmap('coolwarm')

beg_yr = int(2015)
end_yr = int(2024)
years_list = np.arange(beg_yr, end_yr + 1)
data_folder = '/Users/rwe2/Documents/Economics/OSPC/Data/micro-dynamic/reform/'
start_time = time.clock()

'''
------------------------------------------------------------------------
Define Functions
------------------------------------------------------------------------
'''

def gen_etr_grid(X, Y, params):
    '''
    --------------------------------------------------------------------
    This function generates a grid of effective tax rates from a grid of
    total labor income (X) and a grid of total capital income (Y).
    --------------------------------------------------------------------
    X        = (N x N) matrix, discretized support (N elements) of
               inc_lab as row vector copied down N rows
    Y        = (N x N) matrix, discretized support (N elements) of
               inc_cap as column vector copied across N columns
    params   = (10,) vector, estimated parameters
               (A, B, C, D, E, F, max_x, min_x, max_y, min_y)
    A        = scalar > 0, polynomial coefficient on X**2
    B        = scalar > 0, polynomial coefficient on Y**2
    C        = scalar > 0, polynomial coefficient on X*Y
    D        = scalar > 0, polynomial coefficient on X
    E        = scalar > 0, polynomial coefficient on Y
    F        = scalar > 0, polynomial constant
    max_x    = scalar > 0, maximum effective tax rate for X given Y=0
    min_x    = scalar, minimum effective tax rate for X given Y=0
    max_y    = scalar > 0, maximum effective tax rate for Y given X=0
    min_y    = scalar, minimum effective tax rate for Y given X=0
    phi      = (N x N) matrix, labor income as percent of total income
    P_num    = (N x N) matrix, numerator values in ratio of polynomials
    P_den    = (N x N) matrix, denominator values in ratio of
               polynomials
    etr_grid = (N x N) matrix, predicted effective tax rates given labor
               income grid (X) and capital income grid (Y)

    returns: etr_grid
    --------------------------------------------------------------------
    '''
    A, B, C, D, E, F, max_x, min_x, max_y, min_y = params
    phi = X / (X + Y)
    P_num = A * (X ** 2) + B * (Y ** 2) + C * (X * Y) + D * X + E * Y
    P_den = (A * (X ** 2) + B * (Y ** 2) + C * (X * Y) + D * X + E * Y
            + F)
    etr_grid = ((phi * (max_x - min_x) + (1 - phi) * (max_y - min_y)) *
        (P_num / P_den) + (phi * min_x + (1 - phi) * min_y))
    return etr_grid


def gen_mtrx_grid_impl(X, Y, params):
    '''
    --------------------------------------------------------------------
    This function generates a grid of marginal tax rates with respect to
    labor income from a grid of total labor income and a grid of total
    capital income. This is the implied grid because it is derived from
    the estimated effective tax rate function
    --------------------------------------------------------------------
    X         = (N x N) matrix, discretized support (N elements) of
                inc_lab as row vector copied down N rows
    Y         = (N x N) matrix, discretized support (N elements) of
                inc_cap as column vector copied across N columns
    params    = (10,) vector, estimated parameters
                (A, B, C, D, E, F, max_x, min_x, max_y, min_y)
    A         = scalar > 0, polynomial coefficient on X**2
    B         = scalar > 0, polynomial coefficient on Y**2
    C         = scalar > 0, polynomial coefficient on X*Y
    D         = scalar > 0, polynomial coefficient on X
    E         = scalar > 0, polynomial coefficient on Y
    F         = scalar > 0, polynomial constant
    max_x     = scalar > 0, maximum effective tax rate for X given Y=0
    min_x     = scalar, minimum effective tax rate for X given Y=0
    max_y     = scalar > 0, maximum effective tax rate for Y given X=0
    min_y     = scalar, minimum effective tax rate for Y given X=0
    Omega     = (N x N) matrix, ratio of polynomials
    dOMdx     = (N x N) matrix, derivative of ratio of polynomials
                (Omega) with respect to labor income (X)
    mtrx_grid = (N x N) matrix, derivative of total tax liability with
                respect to labor income (X)

    returns: mtrx_grid
    --------------------------------------------------------------------
    '''
    A, B, C, D, E, F, max_x, min_x, max_y, min_y = params
    Omega = ((A * X ** 2) + (B * Y ** 2) + (C * X * Y) + (D * X) +
            (E * Y)) / ((A * X ** 2) + (B * Y ** 2) + (C * X * Y) +
            (D * X) + (E * Y) + F)
    dOMdx = ((F * ((2 * A * X) + (C * Y) + D)) /
            (((A * X ** 2) + (B * Y ** 2) + (C * X * Y) + (D * X) +
            (E * Y) + F) **2))
    mtrx_grid = ((max_x - min_x) * Omega + ((max_x - min_x) * X +
                (max_y - min_y) * Y) * dOMdx + min_x)
    return mtrx_grid


def gen_mtrx_grid_est(X, Y, params):
    '''
    --------------------------------------------------------------------
    This function generates a grid of marginal tax rates with respect to
    labor income from a grid of total labor income and a grid of total
    capital income. This is the estimated grid because it is re-
    estimated using the same functional form as the effective tax rate
    --------------------------------------------------------------------
    X         = (N x N) matrix, discretized support (N elements) of
                inc_lab as row vector copied down N rows
    Y         = (N x N) matrix, discretized support (N elements) of
                inc_cap as column vector copied across N columns
    params    = (10,) vector, estimated parameters
                (H, I, J, K, L, M, max_x, min_x, max_y, min_y)
    H         = scalar > 0, polynomial coefficient on X**2
    I         = scalar > 0, polynomial coefficient on Y**2
    J         = scalar > 0, polynomial coefficient on X*Y
    K         = scalar > 0, polynomial coefficient on X
    L         = scalar > 0, polynomial coefficient on Y
    M         = scalar > 0, polynomial constant
    max_x     = scalar > 0, maximum effective tax rate for X given Y=0
    min_x     = scalar, minimum effective tax rate for X given Y=0
    max_y     = scalar > 0, maximum effective tax rate for Y given X=0
    min_y     = scalar, minimum effective tax rate for Y given X=0
    phi      = (N x N) matrix, labor income as percent of total income
    P_num    = (N x N) matrix, numerator values in ratio of polynomials
    P_den    = (N x N) matrix, denominator values in ratio of
               polynomials
    mtrx_grid = (N x N) matrix, derivative of total tax liability with
                respect to labor income (X)

    returns: mtrx_grid
    --------------------------------------------------------------------
    '''
    H, I, J, K, L, M, max_x, min_x, max_y, min_y = params
    phi = X / (X + Y)
    P_num = H * (X ** 2) + I * (Y ** 2) + J * (X * Y) + K * X + L * Y
    P_den = (H * (X ** 2) + I * (Y ** 2) + J * (X * Y) + K * X + L * Y
            + M)
    mtrx_grid = ((phi * (max_x - min_x) + (1 - phi) * (max_y - min_y)) *
        (P_num / P_den) + (phi * min_x + (1 - phi) * min_y))
    return mtrx_grid


def gen_dmtrx_grid(X, Y, params):
    '''
    --------------------------------------------------------------------
    This function generates a grid of derivatives of marginal tax rates
    with respect to labor income from a grid of total labor income and a
    grid of total capital income
    --------------------------------------------------------------------
    X          = (N x N) matrix, discretized support (N elements) of
                 inc_lab as row vector copied down N rows
    Y          = (N x N) matrix, discretized support (N elements) of
                 inc_cap as column vector copied across N columns
    params     = (10,) vector, estimated parameters
                 (A, B, C, D, E, F, max_x, min_x, max_y, min_y)
    A          = scalar > 0, polynomial coefficient on X**2
    B          = scalar > 0, polynomial coefficient on Y**2
    C          = scalar > 0, polynomial coefficient on X*Y
    D          = scalar > 0, polynomial coefficient on X
    E          = scalar > 0, polynomial coefficient on Y
    F          = scalar > 0, polynomial constant
    max_x      = scalar > 0, maximum effective tax rate for X given Y=0
    min_x      = scalar, minimum effective tax rate for X given Y=0
    max_y      = scalar > 0, maximum effective tax rate for Y given X=0
    min_y      = scalar, minimum effective tax rate for Y given X=0
    dOMdx      = (N x N) matrix, derivative of ratio of polynomials
                 (Omega) with respect to labor income (X)
    d2OMd2x    = (N x N) matrix, second derivative of ratio of
                 polynomials (Omega) with respect to labor income (X)
    dmtrx_grid = (N x N) matrix, second derivative of total tax
                 liability with respect to labor income (X)

    returns: dmtrx_grid
    --------------------------------------------------------------------
    '''
    A, B, C, D, E, F, max_x, min_x, max_y, min_y = params
    dOMdx = ((F * ((2 * A * X) + (C * Y) + D)) /
            (((A * X ** 2) + (B * Y ** 2) + (C * X * Y) + (D * X) +
            (E * Y) + F) **2))
    d2OMd2x = ((2 * F * ((-3 * (A ** 2) * (X ** 2)) +
        ((A * B - C ** 2) * (Y ** 2)) - (3 * A * C * X * Y) -
        (3 * A * D * X) + ((A * E - 2 * C * D) * Y) + (A * F - D ** 2)))
        / (((A * X ** 2) + (B * Y ** 2) + (C * X * Y) + (D * X) +
        (E * Y) + F) ** 3))
    dmtrx_grid = (2 * (max_x - min_x) * dOMdx +
                 ((max_x - min_x) * X + (max_y - min_y) * Y) * d2OMd2x)
    return dmtrx_grid


def gen_dmtry_grid(X, Y, params):
    '''
    --------------------------------------------------------------------
    This function generates a grid of derivatives of marginal tax rates
    with respect to capital income from a grid of total labor income and
    a grid of total capital income
    --------------------------------------------------------------------
    X          = (N x N) matrix, discretized support (N elements) of
                 inc_lab as row vector copied down N rows
    Y          = (N x N) matrix, discretized support (N elements) of
                 inc_cap as column vector copied across N columns
    params     = (10,) vector, estimated parameters
                 (A, B, C, D, E, F, max_x, min_x, max_y, min_y)
    A          = scalar > 0, polynomial coefficient on X**2
    B          = scalar > 0, polynomial coefficient on Y**2
    C          = scalar > 0, polynomial coefficient on X*Y
    D          = scalar > 0, polynomial coefficient on X
    E          = scalar > 0, polynomial coefficient on Y
    F          = scalar > 0, polynomial constant
    max_x      = scalar > 0, maximum effective tax rate for X given Y=0
    min_x      = scalar, minimum effective tax rate for X given Y=0
    max_y      = scalar > 0, maximum effective tax rate for Y given X=0
    min_y      = scalar, minimum effective tax rate for Y given X=0
    dOMdy      = (N x N) matrix, derivative of ratio of polynomials
                 (Omega) with respect to capital income (Y)
    d2OMd2y    = (N x N) matrix, second derivative of ratio of
                 polynomials (Omega) with respect to capital income (Y)
    dmtry_grid = (N x N) matrix, second derivative of total tax
                 liability with respect to capital income (Y)

    returns: dmtry_grid
    --------------------------------------------------------------------
    '''
    A, B, C, D, E, F, max_x, min_x, max_y, min_y = params
    dOMdy = ((F * ((2 * B * Y) + (C * X) + E)) /
            (((A * X ** 2) + (B * Y ** 2) + (C * X * Y) + (D * X) +
            (E * Y) + F) **2))
    d2OMd2y = ((2 * F * ((-3 * (B ** 2) * (Y ** 2)) +
        ((A * B - C ** 2) * (X ** 2)) - (3 * B * C * X * Y) -
        (3 * B * E * Y) + ((B * D - 2 * C * E) * X) + (B * F - E ** 2)))
        / (((A * X ** 2) + (B * Y ** 2) + (C * X * Y) + (D * X) +
        (E * Y) + F) ** 3))
    dmtry_grid = (2 * (max_y - min_y) * dOMdy +
                 ((max_x - min_x) * X + (max_y - min_y) * Y) * d2OMd2y)
    return dmtry_grid


def wsumsq(params, *objs):
    '''
    --------------------------------------------------------------------
    This function generates the weighted sum of squared deviations of
    predicted values of either effective or marginal tax rates from the
    effective or marginal tax rates from the data.
    --------------------------------------------------------------------
    params     = (10,) vector, guesses for (Coef1, Coef2, Coef3, Coef4,
                 Coef5, Coef6, max_x, min_x, max_y, min_y)
    objs       = length 5 tuple,
                 (varmat_hat, txrates, wgts, varmat_bar, phi)
    varmat_hat = (N x 6) matrix, percent deviation from mean
                 transformation of original variables (varmat)
    txrates    = (N x 1) vector, either effective tax rate data or
                 marginal tax rate data for parameter estimation
    wgts       = (N x 1) vector, population weights for each observation
                 for parameter estimation
    varmat_bar = (5,) vector, vector of means of the levels of the
                 first 5 variables in varmat_hat [X1,...X5]
    phi        = (N,) vector, percent of total income that is labor
                 income x/(x+y) for each observation
    max_x      = scalar > 0, maximum effective tax rate for X given Y=0
    min_x      = scalar, minimum effective tax rate for X given Y=0
    max_y      = scalar > 0, maximum effective tax rate for Y given X=0
    min_y      = scalar, minimum effective tax rate for Y given X=0
    Coef7      = scalar > 0, sum of Coef1 through Coef5 coefficients
    P_num      = (N x N) matrix, numerator values in ratio of
                 polynomials
    P_den      = (N x N) matrix, denominator values in ratio of
                 polynomials
    txrates_est = (N,) vector, predicted effective or marginal tax rate
                  for each observation
    errors      = (N,) vector, difference between predicted tax rates
                  and the tax rates from the data
    wssqdev     = scalar > 0, weighted sum of squared errors

    returns: wssqdev
    --------------------------------------------------------------------
    '''
    varmat_hat, txrates, wgts, varmat_bar, phi = objs
    max_x, min_x, max_y, min_y = params[-4:]
    Coef7 = params[:5].sum()
    P_num = np.dot(varmat_hat[:,:-1], params[:5]) + Coef7
    P_den = np.dot(varmat_hat, params[:6]) + Coef7
    txrates_est = ((phi * (max_x - min_x) + (1 - phi) * (max_y - min_y))
        * (P_num / P_den) + (phi * min_x + (1 - phi) * min_y))
    errors = txrates_est - txrates
    wssqdev = (wgts * (errors ** 2)).sum()
    return wssqdev


'''
------------------------------------------------------------------------
Solve for tax functions for each year (t) and each age (s)
------------------------------------------------------------------------
'''

for t in years_list:
    '''
    --------------------------------------------------------------------
    Load OSPC Tax Calculator Data into a Dataframe
    --------------------------------------------------------------------
    t          = integer >= 2015, current year of tax functions being
                 estimated
    data_file  = string, name of data file for current year tax data
    data_path  = string, path to directory address of data file
    data_orig  = (I x 12) DataFrame, I observations, 12 variables
    data       = (I x 6) DataFrame, I observations, 6 variables
    data_trnc  = (I2 x 6) DataFrame, I2 observations (I2<I), 6 variables
    min_age    = integer, minimum age in data_trnc that is at least
                 s_min
    max_age    = integer, maximum age in data_trnc that is at most s_max
    ages_list  = [age_max-age_min+1,] vector, iterable list of relevant
                 ages in data_trnc
    NoData_cnt = integer >= 0, number of consecutive ages with
                 insufficient data to estimate parameters
    --------------------------------------------------------------------
    '''
    data_file = str(t) + '_tau_n.csv'
    data_path = data_folder + data_file
    data_orig = pd.read_csv(data_path)
    data_orig['Total Labor Income'] = (data_orig['Wage and Salaries'] +
        data_orig['Self-Employed Income'])
    data_orig['Effective Tax Rate'] = (data_orig['Total Tax Liability']/
        data_orig["Adjusted Total income"])
    data_orig["Total Capital Income"] = \
        (data_orig['Adjusted Total income'] -
        data_orig['Total Labor Income'])
    data_orig['MTR Labor'] = \
        (data_orig['MTR wage'] * (data_orig['Wage and Salaries'] /
        data_orig['Total Labor Income']) +
        data_orig['MTR self-employed Wage'] *
        (data_orig['Self-Employed Income'] /
        data_orig['Total Labor Income']))
    data = data_orig[['Age', 'MTR Labor', 'Total Labor Income',
        'Total Capital Income', 'Adjusted Total income',
        'Effective Tax Rate', 'Weights']]

    # Calculate average total income in each year
    AvgInc[t-beg_yr] = \
        (((data['Adjusted Total income'] * data['Weights']).sum())
        / data['Weights'].sum())

    # Calculate total population in each year
    TotPop_yr[t-beg_yr] = data['Weights'].sum()

    # Clean up the data by dropping outliers
    # drop all obs with AETR > 0.5
    data_trnc = data.drop(data[data['Effective Tax Rate'] >0.5].index)
    # drop all obs with AETR < -0.15
    data_trnc = data_trnc.drop(data_trnc[data_trnc['Effective Tax Rate']
                < -0.15].index)
    # drop all obs with ATI < $5
    data_trnc = \
        data_trnc.drop(data_trnc[data_trnc['Adjusted Total income'] < 5]
        .index)

    # Create an array of the different ages in the data
    min_age = int(np.maximum(data_trnc['Age'].min(), s_min))
    max_age = int(np.minimum(data_trnc['Age'].max(), s_max))
    ages_list = np.arange(min_age, max_age+1)

    NoData_cnt = 0

    # Each age s must be done in serial, but each year can be done in
    # parallel
    for s in ages_list:
        '''
        ----------------------------------------------------------------
        Load OSPC Tax Calculator Data into a Dataframe
        ----------------------------------------------------------------
        s            = integer >= s_min, current age of tax function
                       estimation
        df           = (I3 x 6) DataFrame, data_trnc for age=s
        df_trnc      = (I5 x 6) DataFrame, truncated data for parameter
                       estimation
        inc_lab      = (I5 x 1) vector, total labor income for parameter
                       estimation
        inc_cap      = (I5 x 1) vector, total capital income for
                       parameter estimation
        etr          = (I5 x 1) vector, effective tax rate data for
                       parameter estimation
        mtrx         = (I5 x 1) vector, marginal tax rate data with
                       respect to labor for parameter estimation
        wgts         = (I5 x 1) vector, population weights for each
                       observation for parameter estimation
        Obs          = integer, number of observations in sample
        X1           = (Obs x 1) vector, lab_inc ** 2
        X2           = (Obs x 1) vector, cap_inc ** 2
        X3           = (Obs x 1) vector, lab_inc * cap_inc
        X4           = (Obs x 1) vector, lab_inc
        X5           = (Obs x 1) vector, cap_inc
        X6           = (Obs x 1) vector of ones
        phi          = (Obs,) vector, percent of total income that is
                       labor income x/(x+y) for each observation
        varmat       = (Obs x 6) matrix, variables [X1,...X6]
        varmat_bar   = (6,) vector, mean values of each column of varmat
        varmat_barm1 = (5,) vector, vector of means of [X1,...X5]
        varmat_hat   = (Obs x 6) matrix, percent deviation from mean
                       transformation of varmat
        elapsed_time = scalar > 0, seconds to finish computation
        dict_params  = length 3 dictionary, saves param_arr, AvgInc, and
                       elapsed_time
        ----------------------------------------------------------------
        '''
        print("year=", t, "Age=", s)
        df = data_trnc[data_trnc['Age'] == s]
        PopPct_age[s-s_min, t-beg_yr] = \
            df['Weights'].sum() / TotPop_yr[t-beg_yr]

        if df.shape[0] < 600 and s < max_age:
            '''
            ------------------------------------------------------------
            Don't estimate function on this iteration if obs < 600.
            Will fill in later with interpolated values
            ------------------------------------------------------------
            '''
            NoData_cnt += 1
            etrparam_arr[s-21, t-beg_yr, :] = np.nan
            mtrxparam_arr[s-21, t-beg_yr, :] = np.nan

        elif df.shape[0] < 600 and s == max_age:
            '''
            ------------------------------------------------------------
            If last period does not have sufficient data, fill in final
            missing age data with last positive year
            ------------------------------------------------------------
            lastp_etr  = (10,) vector, vector of parameter estimates
                         from previous age with sufficient observations
            lastp_mtrx = (10,) vector, vector of parameter estimates
                         from previous age with sufficient observations
            ------------------------------------------------------------
            '''
            NoData_cnt += 1
            lastp_etr = etrparam_arr[s-NoData_cnt-21, t-beg_yr, :]
            etrparam_arr[s-NoData_cnt-20:, t-beg_yr, :] = \
                np.tile(lastp_etr.reshape((1, 10)),
                (NoData_cnt, 1))
            lastp_mtrx = mtrxparam_arr[s-NoData_cnt-21, t-beg_yr, :]
            mtrxparam_arr[s-NoData_cnt-20:, t-beg_yr, :] = \
                np.tile(lastp_mtrx.reshape((1, 10)),
                (NoData_cnt, 1))


        else:
            # Estimate parameters for age with sufficient data
            if desc_data == True:
                # print some desciptive stats
                print('Descriptive Statistics for age == ', s)
                print(df.describe())

            if graph_data == True:
                '''
                --------------------------------------------------------
                Create 3-D scatterplot of effective tax rate as a
                function of labor income and capital income
                --------------------------------------------------------
                df_trnc_gph  = (I4 x 6) DataFrame, truncated data for 3D
                               graph
                inc_lab_gph  = (I4 x 1) vector, total labor income for
                               3D graph
                inc_cap_gph  = (I4 x 1) vector, total capital income for
                               3D graph
                etr_data_gph = (I4 x 1) vector, effective tax rate data
                               for 3D graph
                --------------------------------------------------------
                '''
                df_trnc_gph = df[(df['Total Labor Income'] > 5) &
                              (df['Total Labor Income'] < 500000) &
                              (df['Total Capital Income'] > 5) &
                              (df['Total Capital Income'] < 500000)]
                inc_lab_gph = df_trnc_gph['Total Labor Income']
                inc_cap_gph = df_trnc_gph['Total Capital Income']
                etr_data_gph = df_trnc_gph['Effective Tax Rate']

                fig = plt.figure()
                ax = fig.add_subplot(111, projection ='3d')
                ax.scatter(inc_lab_gph, inc_cap_gph, etr_data_gph,
                    c='r', marker='o')
                ax.set_xlabel('Total Labor Income')
                ax.set_ylabel('Total Capital Income')
                ax.set_zlabel('Effective Tax Rate')
                plt.title('ETR, Lab. inc., and Cap. inc., Age=' + str(s) + ', Year=' + str(t))
                plt.show()

                '''
                --------------------------------------------------------
                Create 3-D scatterplot of marginal tax rate on labor
                income as a function of labor income and capital income
                --------------------------------------------------------
                mtrx_data_gph = (I4 x 1) vector, marginal tax rate data
                                for 3D graph
                --------------------------------------------------------
                '''
                mtrx_data_gph = df_trnc_gph['MTR Labor']

                fig = plt.figure()
                ax = fig.add_subplot(111, projection ='3d')
                ax.scatter(inc_lab_gph, inc_cap_gph, mtrx_data_gph,
                    c='r', marker='o')
                ax.set_xlabel('Total Labor Income')
                ax.set_ylabel('Total Capital Income')
                ax.set_zlabel('Marginal Tax Rate (Labor inc.)')
                plt.title('MTRx, Lab. inc., and Cap. inc., Age=' + str(s) + ', Year=' + str(t))
                plt.show()

            df_trnc = df[(df['Total Labor Income'] > 5) &
                      (df['Total Capital Income'] > 5)]
            inc_lab = df_trnc['Total Labor Income']
            inc_cap = df_trnc['Total Capital Income']
            etr = df_trnc['Effective Tax Rate']
            mtrx = df_trnc['MTR Labor']
            wgts = df_trnc['Weights']
            Obs = inc_lab.shape[0]
            X1 = (inc_lab ** 2).reshape((Obs, 1))
            X2 = (inc_cap ** 2).reshape((Obs, 1))
            X3 = (inc_lab * inc_cap).reshape((Obs, 1))
            X4 = inc_lab.reshape((Obs, 1))
            X5 = inc_cap.reshape((Obs, 1))
            X6 = np.ones((Obs, 1))
            phi = (X4 / (X4 + X5)).reshape(Obs)
            varmat = np.hstack((X1, X2, X3, X4, X5, X6))
            varmat_bar = varmat.mean(axis=0)
            varmat_barm1 = varmat_bar[:-1]
            varmat_hat = (varmat - varmat_bar)/varmat_bar
            varmat_hat[:, 5] = np.ones(Obs)

            '''
            ------------------------------------------------------------
            Estimate effective tax rate function tau(x,y)
            ------------------------------------------------------------
            Atil_init      = scalar > 0, initial guess for A tilde
            Btil_init      = scalar > 0, initial guess for B tilde
            Ctil_init      = scalar > 0, initial guess for C tilde
            Dtil_init      = scalar > 0, initial guess for D tilde
            Etil_init      = scalar > 0, initial guess for E tilde
            F_init         = scalar > 0, initial guess for F constant
            maxetr_x_init  = scalar > 0, initial guess for max_x (labor
                             income)
            minetr_x_init  = scalar > 0, initial guess for min_x (labor
                             income)
            maxetr_y_init  = scalar > 0, initial guess for max_y
                             (capital income)
            minetr_y_init  = scalar > 0, initial guess for min_y
                             (capital income)
            etrparams_init = (10,) vector, initial parameter guesses
            etr_objs       = length 5 tuple, inputs for minimizer
                             (varmat_hat, etr, wgts, varmat_barm1, phi)
            bnds           = length 10 tuple, max and min parameter
                             bounds
            etrparams_til  = length 8 tuple, output from minimizer.
                             Object with the estimated param values is
                             etrparams_til.x
            Atil           = scalar > 0, estimated value for A tilde
            Btil           = scalar > 0, estimated value for B tilde
            Ctil           = scalar > 0, estimated value for C tilde
            Dtil           = scalar > 0, estimated value for D tilde
            Etil           = scalar > 0, estimated value for E tilde
            F              = scalar > 0, estimated value for F constant
            maxetr_x       = scalar > 0, estimated value for max_x
                             (labor income)
            minetr_x       = scalar, estimated value for min_x (labor
                             income)
            maxetr_y       = scalar > 0, estimated value for max_y
                             (capital income)
            minetr_y       = scalar, estimated value for min_y (capital
                             income)
            Gtil           = scalar > 0, sum of Atil through Etil
            P_num          = (Obs,) vector, value of the numerator of
                             the ratio of polynomials for each obs
            P_den          = (Obs,) vector, value of the denominator of
                             the ratio of polynomials for each obs
            etr_est        = (Obs,) vector, predicted effective tax
                             rates for each observation
            etrparams      = (10,) vector, estimated parameters (A, B,
                             C, D, E, F, max_x, min_x, max_y, min_y)
            A              = scalar > 0, estimated polynomial
                             coefficient on x**2
            B              = scalar > 0, estimated polynomial
                             coefficient on y**2
            C              = scalar > 0, estimated polynomial
                             coefficient on x*y
            D              = scalar > 0, estimated polynomial
                             coefficient on x
            E              = scalar > 0, estimated polynomial
                             coefficient on y
            ------------------------------------------------------------
            '''
            Atil_init = 0.5
            Btil_init = 0.5
            Ctil_init = 0.5
            Dtil_init = 0.5
            Etil_init = 0.5
            F_init = 0.5
            maxetr_x_init = etr[(df_trnc['Total Capital Income']
                            <3000)].max()
            minetr_x_init = etr[(df_trnc['Total Capital Income']
                            <3000)].min()
            maxetr_y_init = etr[(df_trnc['Total Labor Income']
                            <3000)].max()
            minetr_y_init = etr[(df_trnc['Total Labor Income']
                            <3000)].min()
            etrparams_init = np.array([Atil_init, Btil_init, Ctil_init,
                Dtil_init, Etil_init, F_init, maxetr_x_init,
                minetr_x_init, maxetr_y_init, minetr_y_init])
            etr_objs = (varmat_hat, etr, wgts, varmat_barm1, phi)
            bnds = ((1e-12, None), (1e-12, None), (1e-12, None),
                   (1e-12, None), (1e-12, None), (1e-12, None),
                   (1e-12, None), (None, None), (1e-12, None),
                   (None, None))
            etrparams_til = opt.minimize(wsumsq, etrparams_init,
                args=(etr_objs), method="L-BFGS-B", bounds=bnds,
                tol=1e-15)
            (Atil, Btil, Ctil, Dtil, Etil, F, maxetr_x, minetr_x,
                maxetr_y, minetr_y) = etrparams_til.x
            Gtil = etrparams_til.x[:5].sum()
            P_num = (np.dot(varmat_hat[:, :-1], etrparams_til.x[:5])
                    + Gtil)
            P_den = np.dot(varmat_hat, etrparams_til.x[:6]) + Gtil
            etr_est = \
                ((phi * (maxetr_x - minetr_x) + (1 - phi) * (maxetr_y
                - minetr_y)) * (P_num / P_den) + (phi * minetr_x +
                (1 - phi) * minetr_y))
            etrparams = np.zeros(numparams)
            etrparams[:5] = etrparams_til.x[:5] / varmat_bar[:5]
            A, B, C, D, E = etrparams[:5]
            etrparams[5] = F
            etrparams[6:] = [maxetr_x, minetr_x, maxetr_y, minetr_y]
            etrparam_arr[s-21, t-beg_yr, :] = etrparams

            '''
            ------------------------------------------------------------
            Estimate marg. tax rate of labor income function MTRx(x,y)
            ------------------------------------------------------------
            Htil_init       = scalar > 0, initial guess for H tilde
            Itil_init       = scalar > 0, initial guess for I tilde
            Jtil_init       = scalar > 0, initial guess for J tilde
            Ktil_init       = scalar > 0, initial guess for K tilde
            Ltil_init       = scalar > 0, initial guess for L tilde
            M_init          = scalar > 0, initial guess for M constant
            maxmtrx_x_init  = scalar > 0, initial guess for max_x (labor
                              income)
            minmtrx_x_init  = scalar > 0, initial guess for min_x (labor
                              income)
            maxmtrx_y_init  = scalar > 0, initial guess for max_y
                              (capital income)
            minmtrx_y_init  = scalar > 0, initial guess for min_y
                              (capital income)
            mtrxparams_init = (10,) vector, initial parameter guesses
            mtrx_objs       = length 5 tuple, inputs for minimizer
                              (varmat_hat,mtrx,wgts,varmat_barm1,phi)
            mtrxparams_til  = length 8 tuple, output from minimizer.
                              Object with the estimated param values is
                              mtrxparams_til.x
            Htil            = scalar > 0, estimated value for H tilde
            Itil            = scalar > 0, estimated value for I tilde
            Jtil            = scalar > 0, estimated value for J tilde
            Ktil            = scalar > 0, estimated value for K tilde
            Ltil            = scalar > 0, estimated value for L tilde
            M               = scalar > 0, estimated value for M constant
            maxmtrx_x       = scalar > 0, estimated value for max_x
                              (labor income)
            minmtrx_x       = scalar, estimated value for min_x (labor
                              income)
            maxmtrx_y       = scalar > 0, estimated value for max_y
                              (capital income)
            minmtrx_y       = scalar, estimated value for min_y (capital
                              income)
            Ntil            = scalar > 0, sum of Htil through Ltil
            P_num           = (Obs,) vector, value of the numerator of
                              the ratio of polynomials for each obs
            P_den           = (Obs,) vector, value of the denominator of
                              the ratio of polynomials for each obs
            mtrx_est        = (Obs,) vector, predicted marginal tax
                              rates of labor income for each obs
            mtrxparams      = (10,) vector, estimated parameters (H, I,
                              J, K, L, M, max_x, min_x, max_y, min_y)
            H               = scalar > 0, estimated polynomial
                              coefficient on x**2
            I               = scalar > 0, estimated polynomial
                              coefficient on y**2
            J               = scalar > 0, estimated polynomial
                              coefficient on x*y
            K               = scalar > 0, estimated polynomial
                              coefficient on x
            L               = scalar > 0, estimated polynomial
                              coefficient on y
            ------------------------------------------------------------
            '''
            Htil_init = 0.5
            Itil_init = 0.5
            Jtil_init = 0.5
            Ktil_init = 0.5
            Ltil_init = 0.5
            M_init = 0.5
            maxmtrx_x_init = mtrx[(df_trnc['Total Capital Income']
                             <3000)].max()
            minmtrx_x_init = mtrx[(df_trnc['Total Capital Income']
                             <3000)].min()
            maxmtrx_y_init = mtrx[(df_trnc['Total Labor Income']
                             <3000)].max()
            minmtrx_y_init = mtrx[(df_trnc['Total Labor Income']
                             <3000)].min()
            mtrxparams_init = np.array([Htil_init, Itil_init, Jtil_init,
                Ktil_init, Ltil_init, M_init, maxmtrx_x_init,
                minmtrx_x_init, maxmtrx_y_init, minmtrx_y_init])
            mtrx_objs = (varmat_hat, mtrx, wgts, varmat_barm1, phi)
            mtrxparams_til = opt.minimize(wsumsq, mtrxparams_init,
                args=(mtrx_objs), method="L-BFGS-B", bounds=bnds,
                tol=1e-15)
            (Htil, Itil, Jtil, Ktil, Ltil, M, maxmtrx_x, minmtrx_x,
                maxmtrx_y, minmtrx_y) = mtrxparams_til.x
            Ntil = mtrxparams_til.x[:5].sum()
            P_num = (np.dot(varmat_hat[:, :-1], mtrxparams_til.x[:5])
                    + Ntil)
            P_den = np.dot(varmat_hat, mtrxparams_til.x[:6]) + Ntil
            mtrx_est = ((phi * (maxmtrx_x - minmtrx_x) +
                (1 - phi) * (maxmtrx_y - minmtrx_y)) * (P_num / P_den) +
                (phi * minmtrx_x + (1 - phi) * minmtrx_y))
            mtrxparams = np.zeros(numparams)
            mtrxparams[:5] = mtrxparams_til.x[:5] / varmat_bar[:5]
            H, I, J, K, L = mtrxparams[:5]
            mtrxparams[5] = M
            mtrxparams[6:] = [maxmtrx_x, minmtrx_x, maxmtrx_y, minmtrx_y]
            mtrxparam_arr[s-21, t-beg_yr, :] = mtrxparams

            if NoData_cnt > 0 & NoData_cnt == s-21:
                '''
                --------------------------------------------------------
                Fill in initial blanks with first positive data
                estimates
                --------------------------------------------------------
                '''
                etrparam_arr[:s-21, t-beg_yr, :] = \
                    np.tile(etrparams.reshape((1, 10)), (s-21, 1))
                mtrxparam_arr[:s-21, t-beg_yr, :] = \
                    np.tile(mtrxparams.reshape((1, 10)), (s-21, 1))

            elif NoData_cnt > 0 & NoData_cnt < s-21:
                '''
                --------------------------------------------------------
                Fill in interior data gaps with linear interpolation
                between bracketing positive data ages
                --------------------------------------------------------
                tvals        = (NoData_cnt+2,) vector, linearly space
                               points between 0 and 1
                x0_etr       = (NoData_cnt x 10) matrix, positive
                               estimates at beginning of no data spell
                x1_etr       = (NoData_cnt x 10) matrix, positive
                               estimates at end (current period) of no
                               data spell
                lin_int_etr  = (NoData_cnt x 10) matrix, linearly
                               interpolated etr parameters between
                               x0_etr and x1_etr
                x0_mtrx      = (NoData_cnt x 10) matrix, positive
                               estimates at beginning of no data spell
                x1_mtrx      = (NoData_cnt x 10) matrix, positive
                               estimates at end (current period) of no
                               data spell
                lin_int_mtrx = (NoData_cnt x 10) matrix, linearly
                               interpolated mtrx parameters between
                               x0_mtrx and x1_mtrx
                --------------------------------------------------------
                '''
                tvals = np.linspace(0, 1, NoData_cnt+2)
                x0_etr = np.tile(etrparam_arr[
                         s-NoData_cnt-22, t-beg_yr, :].reshape((1, 10)),
                         (NoData_cnt, 1))
                x1_etr = np.tile(etrparams.reshape((1, 10)),
                         (NoData_cnt, 1))
                lin_int_etr = \
                    (x0_etr + tvals[1:-1].reshape((NoData_cnt, 1))
                    * (x1_etr - x0_etr))
                etrparam_arr[s-NoData_cnt-21:s-21, t-beg_yr, :] = \
                    lin_int_etr
                x0_mtrx = np.tile(mtrxparam_arr[
                    s-NoData_cnt-22, t-beg_yr, :].reshape((1, 10)),
                    (NoData_cnt, 1))
                x1_mtrx = np.tile(mtrxparams.reshape((1, 10)),
                          (NoData_cnt, 1))
                lin_int_mtrx = \
                    (x0_mtrx + tvals[1:-1].reshape((NoData_cnt, 1))
                    * (x1_mtrx - x0_mtrx))
                mtrxparam_arr[s-NoData_cnt-21:s-21, t-beg_yr, :] = \
                    lin_int_mtrx

            NoData_cnt == 0

            if s == max_age and max_age < s_max:
                etrparam_arr[s-20:, t-beg_yr, :] = \
                    np.tile(etrparams.reshape((1, 10)),
                    (s_max-max_age, 1))
                mtrxparam_arr[s-20:, t-beg_yr, :] = \
                    np.tile(mtrxparams.reshape((1, 10)),
                    (s_max-max_age, 1))

            if graph_est == True:
                '''
                --------------------------------------------------------
                Generate 3-D graph of predicted surface and scatterplot
                of data
                --------------------------------------------------------
                gridpts      = integer >= 2, number of gridpoint in
                               each dimension to plot
                inc_lab_vec  = (gridpts,) vector, points in support of
                               inc_lab to plot
                inc_cap_vec  = (gridpts,) vector, points in support of
                               inc_cap to plot
                inc_lab_grid = (gridpts x gridpts) matrix, row vector of
                               inc_lab_vec copied down gridpts rows
                inc_cap_grid = (gridpts x gridpts) matrix, column vector
                               of inc_cap_vec copied across gridpts
                               columns
                etr_grid     = (gridpts x gridpts) matrix, predicted
                               effective tax rates given inc_lab_grid
                               and inc_cap_grid
                --------------------------------------------------------
                '''
                fig = plt.figure()
                ax = fig.add_subplot(111, projection ='3d')
                ax.scatter(inc_lab, inc_cap, etr, c='r', marker='o')
                ax.set_xlabel('Total Labor Income')
                ax.set_ylabel('Total Capital Income')
                ax.set_zlabel('Effective Tax Rate')
                plt.title('ETR vs. Predicted ETR: Age=' + str(s) + ', Year=' + str(t))

                gridpts = 50
                inc_lab_vec = np.exp(np.linspace(np.log(5),
                              np.log(inc_lab.max()), gridpts))
                inc_cap_vec = np.exp(np.linspace(np.log(5),
                              np.log(inc_cap.max()), gridpts))
                inc_lab_grid, inc_cap_grid = np.meshgrid(inc_lab_vec,
                                             inc_cap_vec)
                etr_grid = gen_etr_grid(inc_lab_grid, inc_cap_grid,
                           etrparams)
                ax.plot_surface(inc_lab_grid, inc_cap_grid, etr_grid,
                    cmap=cmap1, linewidth=0)
                plt.show()

            if dmtrgr_est == True:
                '''
                --------------------------------------------------------
                Generate 3-D graph of predicted derivative of marginal
                tax rates
                --------------------------------------------------------
                gridpts      = integer >= 2, number of gridpoint in
                               each dimension to plot
                inc_lab_vec  = (gridpts,) vector, points in support of
                               inc_lab to plot
                inc_cap_vec  = (gridpts,) vector, points in support of
                               inc_cap to plot
                inc_lab_grid = (gridpts x gridpts) matrix, row vector of
                               inc_lab_vec copied down gridpts rows
                inc_cap_grid = (gridpts x gridpts) matrix, column vector
                               of inc_cap_vec copied across gridpts
                               columns
                dmtrx_grid   = (gridpts x gridpts) matrix, predicted
                               derivative of marginal tax rates with
                               respect to labor income given
                               inc_lab_grid and inc_cap_grid
                dmtry_grid   = (gridpts x gridpts) matrix, predicted
                               derivative of marginal tax rates with
                               respect to capital income given
                               inc_lab_grid and inc_cap_grid
                --------------------------------------------------------
                '''
                df_trnc_gph = df[(df['Total Labor Income'] > 5) &
                              (df['Total Labor Income'] < 500000) &
                              (df['Total Capital Income'] > 5) &
                              (df['Total Capital Income'] < 500000)]
                inc_lab_gph = df_trnc_gph['Total Labor Income']
                inc_cap_gph = df_trnc_gph['Total Capital Income']
                mtrx_gph = df_trnc_gph['MTR Labor']
                gridpts = 50
                # inc_lab_vec = np.exp(np.linspace(np.log(5),
                #               np.log(inc_lab.max()), gridpts))
                # inc_cap_vec = np.exp(np.linspace(np.log(5),
                #               np.log(inc_cap.max()), gridpts))
                inc_lab_vec = np.exp(np.linspace(np.log(5),
                              np.log(500000), gridpts))
                inc_cap_vec = np.exp(np.linspace(np.log(5),
                              np.log(500000), gridpts))
                inc_lab_grid, inc_cap_grid = np.meshgrid(inc_lab_vec,
                                             inc_cap_vec)

                mtrx_grid_impl = \
                    gen_mtrx_grid_impl(inc_lab_grid, inc_cap_grid,
                    etrparams)
                mtrx_grid_est = \
                    gen_mtrx_grid_est(inc_lab_grid, inc_cap_grid,
                    mtrxparams)
                fig = plt.figure()
                ax = fig.add_subplot(111, projection ='3d')
                ax.scatter(inc_lab_gph, inc_cap_gph, mtrx_gph, c='r', marker='o')
                ax.set_xlabel('Total Labor Income')
                ax.set_ylabel('Total Capital Income')
                ax.set_zlabel('MTR labor inc.')
                plt.title('Implied MTR labor inc.: Age=' + str(s) + ', Year=' + str(t))
                ax.plot_surface(inc_lab_grid, inc_cap_grid, mtrx_grid_impl,
                    cmap=cmap1, linewidth=0)
                print(mtrx_grid_impl.min(), mtrx_grid_impl.max())
                plt.show()

                fig = plt.figure()
                ax = fig.add_subplot(111, projection ='3d')
                ax.scatter(inc_lab_gph, inc_cap_gph, mtrx_gph, c='r', marker='o')
                ax.set_xlabel('Total Labor Income')
                ax.set_ylabel('Total Capital Income')
                ax.set_zlabel('MTR labor inc.')
                plt.title('Estimated MTR labor inc.: Age=' + str(s) + ', Year=' + str(t))
                ax.plot_surface(inc_lab_grid, inc_cap_grid, mtrx_grid_est,
                    cmap=cmap1, linewidth=0)
                print(mtrx_grid_est.min(), mtrx_grid_est.max())
                plt.show()

                dmtrx_grid = gen_dmtrx_grid(inc_lab_grid, inc_cap_grid,
                             etrparams)
                fig = plt.figure()
                ax = fig.add_subplot(111, projection ='3d')
                ax.plot_surface(inc_lab_grid, inc_cap_grid, dmtrx_grid,
                    cmap=cmap1, linewidth=0)
                ax.set_xlabel('Total Labor Income')
                ax.set_ylabel('Total Capital Income')
                ax.set_zlabel('d MTR labor inc.')
                plt.title('d MTR labor inc.: Age=' + str(s) + ', Year=' + str(t))
                print(dmtrx_grid.min(), dmtrx_grid.max())
                plt.show()

                dmtry_grid = gen_dmtry_grid(inc_lab_grid, inc_cap_grid,
                             etrparams)
                fig = plt.figure()
                ax = fig.add_subplot(111, projection ='3d')
                ax.plot_surface(inc_lab_grid, inc_cap_grid, dmtry_grid,
                    cmap=cmap1, linewidth=0)
                ax.set_xlabel('Total Labor Income')
                ax.set_ylabel('Total Capital Income')
                ax.set_zlabel('d MTR capital inc.')
                plt.title('d MTR capital inc.: Age=' + str(s) + ', Year=' + str(t))
                print(dmtry_grid.min(), dmtry_grid.max())
                plt.show()

elapsed_time = time.clock() - start_time

# Print tax function computation time
if elapsed_time < 60: # seconds
    secs = round(elapsed_time, 3)
    print('Tax function estimation time: ', secs, ' sec.')
elif elapsed_time >= 60 and elapsed_time < 3600: # minutes
    mins = int(elapsed_time / 60)
    secs = round(((elapsed_time / 60) - mins) * 60, 1)
    print('Tax function estimation time: ', mins, ' min, ', secs, ' sec')

'''
------------------------------------------------------------------------
Generate tax function parameters for S < s_max - s_min + 1
------------------------------------------------------------------------
etrparam_arr_S  = S x tpers x 10 array, this is an array in which S is
                  less-than-or-equal-to s_max-s_min+1. We use weighted
                  averages of parameters in relevant age groups
mtrxparam_arr_S = S x tpers x 10 array, this is an array in which S is
                  less-than-or-equal-to s_max-s_min+1. We use weighted
                  averages of parameters in relevant age groups
age_cuts     = (S+1,) vector, linspace of age cutoffs of S+1 points
               between 0 and S+1
yrcut_lb     = integer >= 0, index of lower bound age for S bin
yrcut_ub     = integer >= 0, index of upper bound age for S bin
rmndr_pct_lb = scalar in [0,1], discounted weight on lower bound age
rmndr_pct_ub = scalar in [0,1], discounted weight on upper bound age
age_wgts     = ages x tpers x 10 array, age weights for each age in each
               year copied back 10 times in the 3rd dimension
------------------------------------------------------------------------
'''
if S == s_max - s_min + 1:
    etrparam_arr_S = etrparam_arr
    mtrxparam_arr_S = mtrxparam_arr

elif S < s_max - s_min + 1:
    etrparam_arr_S = np.zeros((S, tpers, numparams))
    mtrxparam_arr_S = np.zeros((S, tpers, numparams))
    age_cuts = np.linspace(0, s_max-s_min+1, S+1)
    yrcut_lb = int(age_cuts[0])
    rmndr_pct_lb = 1.
    for s in np.arange(S):
        yrcut_ub = int(np.floor(age_cuts[s+1]))
        rmndr_pct_ub = age_cuts[s+1] - np.floor(age_cuts[s+1])
        if rmndr_pct_ub == 0.:
            rmndr_pct_ub = 1.
            yrcut_ub -= 1
        age_wgts = np.dstack([PopPct_age[yrcut_lb:yrcut_ub+1, :]]*10)
        # print yrcut_lb, yrcut_ub, rmndr_pct_lb, rmndr_pct_ub, age_wgts.shape
        age_wgts[0, :, :] *= rmndr_pct_lb
        age_wgts[yrcut_ub-yrcut_lb, :, :] *= rmndr_pct_ub
        etrparam_arr_S[s, :, :] = (etrparam_arr[yrcut_lb:yrcut_ub+1, :, :] * age_wgts).sum(axis=0)
        mtrxparam_arr_S[s, :, :] = (mtrxparam_arr[yrcut_lb:yrcut_ub+1, :, :] * age_wgts).sum(axis=0)
        yrcut_lb = yrcut_ub
        rmndr_pct_lb = 1 - rmndr_pct_ub


# Save tax function parameters array and computation time in pickle
dict_params = dict([('tfunc_params_S', etrparam_arr_S),
    ('tfunc_params_S', mtrxparam_arr_S), ('tfunc_avginc', AvgInc),
    ('tfunc_time', elapsed_time)])
pkl_path = "TxFuncEst.pkl"
pickle.dump(dict_params, open(pkl_path, "wb"))
