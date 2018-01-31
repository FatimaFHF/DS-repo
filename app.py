#Drag/drop files, time pickup from a calendar, showing idle cars with red markers on map
#A first Dwell time table also shows but does not get updated

import dash_html_components as html
import dash_core_components as dcc
import dash

import plotly
import dash_table_experiments as dte
from dash.dependencies import Input, Output, State

import pandas as pd
import numpy as np

import json
import datetime
from datetime import datetime, timedelta
import operator
import os

import base64
import io

import plotly.plotly as py
from plotly.graph_objs import *
import plotly.graph_objs as go

from geopy.distance import vincenty

app = dash.Dash()

app.scripts.config.serve_locally = True
app.config['suppress_callback_exceptions'] = True

mapbox_access_token = "pk.eyJ1IjoibXlkYXNoYW5hbHlzaXMiLCJhIjoiY2pjcDAzbW91MGdibDMybWlocTVjeGMxNyJ9.VzA-rhWiCG4MsRRaeJfvvw"

TOTAL_NUMBER_OF_ASSETS = 14
############################## (1) CLEANING DATA ##############################
# 1-1) Adding new rows for dates not available for each ASSET

#first: finding out the date range in the input file
def range_date(date_list):
    return(min(date_list) , max(date_list))

#range_dates = range_date(list(df['utc_time']))

#returns list of dates that should be added to each asset (missing dates)
#inputs: dataframe and a string that shows the daily time (7:59), time range of the input file
def list_of_dates_to_be_added (asset_data_frame, daily_hour, min_time_range_input_file, max_time_range_input_file):     
    #converting the daily_hour to datetime object
    morning_time = datetime.strptime(daily_hour, '%H:%M').time()
    range_dates_max_date = datetime.fromtimestamp(max_time_range_input_file.timestamp()).date()
    range_dates_max_morning_date = datetime.combine(range_dates_max_date, morning_time)
    #changing the times of the input asset dataframe to date type
    time_list = []
    for item in list(asset_data_frame['utc_time']):
        time_list.append(datetime.fromtimestamp(item.timestamp()).date())

    #making a uniques list of the time_list
    unique_time_list = list(set(time_list))
    #creating list of dates in the time range of the input file
    dates_list = []
    for i in range(1, (max_time_range_input_file - min_time_range_input_file).days + 1):
        dates_list.append( (range_dates_max_morning_date - timedelta(days = i)).date())
    #finding out the dates that are present it time range of the input file but not in the input asset dataframe
    new_list_dates = [item for item in dates_list if item not in unique_time_list]
    new_list_datetimes=[]
    for item in new_list_dates:
        new_list_datetimes.append(datetime.combine(item, morning_time))
    
    return new_list_datetimes


#insert a row in the input dataframe, for every date that does not exist in the input data frame, but is in the time period of thw whole df
def insert_row(data_frame, list_of_dates):
    last_row = len(data_frame) - 1
    list_of_dict = []
    d = {}
    #set this to turn off the warning error
    data_frame.is_copy = False
    for i in range(0, len(list_of_dates)):
        data_frame.loc[i + last_row] = [data_frame.iloc[last_row]['AssetID'], list_of_dates[i], data_frame.iloc[last_row]['City'], data_frame.iloc[last_row]['Province'],data_frame.iloc[last_row]['Country'], data_frame.iloc[last_row]['Latitude'], data_frame.iloc[last_row]['Longitude']] 
    return data_frame


#grouped_df = df.groupby('AssetID')
#input_dates = list_of_dates_to_be_added(my_df, "7:59", range_dates[0], range_dates[1])
#my_df = df[df['AssetID'] == 'CGEX1797']
#insert_row(my_df, input_dates)

#returns a new data frame where new rows are added for the input_range for all Assets
#input range is a pair of newest and oldest date in the whole data frame
def data_frame_by_new_dates_added(grouped_input_data_frame, input_range):
    #make a list of dataframes
    appended_data = []
    for name, group in grouped_input_data_frame:
        input_dates = list_of_dates_to_be_added(grouped_input_data_frame.get_group(name), "7:59", input_range[0], input_range[1])
        n_df = insert_row(grouped_input_data_frame.get_group(name), input_dates)
        appended_data.append(n_df)
    #Make a dataframe out of the list
    #set ignore_index= True to return unique values
    grouped_input_data_frame_result = pd.concat(appended_data, ignore_index =True)
    return grouped_input_data_frame_result


# 1-2) Remove duplicates
def remove_duplicate_rows(data_frame_new_dates_added , set_of_columns):
    #set_of_columns = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
    return data_frame_new_dates_added.drop_duplicates(subset= set_of_columns)

# 1-3) Add row_index
#returning the row name, in this case indexes
def rowIndex(row):
    return row.name

def add_row_index_column(cleaned_data_frame):
    row_index = cleaned_data_frame.apply(rowIndex, axis=1)
    #adding indexes as keys to the data frame
    cleaned_data_frame.loc[:,'row_index'] = row_index
    #return cleaned_data_frame


# 1-4) slice the dataframe by the list of columns required for analysis
def slice_data_frame_by_required_columns(cleaned_data_frame_, required_columns_list):
    #required_columns_list = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
    required_data_frame  = cleaned_data_frame_.loc[:,required_columns_list]
    return required_data_frame


############################## (2) LOCATION ANALYSIS BY TIME ##############################

#find the previous date before 8:00 AM of a specific date (base_time)
def nearest_previous_date(baseDate, dates):
    nearness = {}
    for date in dates:
        if(baseDate.timestamp() - date.timestamp() >= 0):
            nearness[baseDate.timestamp() - date.timestamp()] = date
    if len(nearness)==0:
        return
    else:
        return nearness[min(nearness.keys())]

#find the previous date 48 hours before 8:00 AM of a specific date (base_time)
def nearest_previous_2_days(baseDate, dates):
    #date_ = baseDate.
    nearness = {}
    for date in dates:
        if(baseDate.timestamp() - date.timestamp() > timedelta(days=2).total_seconds()):
            nearness[baseDate.timestamp() - date.timestamp()] = date
    if len(nearness)==0:
        return
    else:
        return nearness[min(nearness.keys())]

############################## (3) ANALYSIS FOR DWELL CARS (2nd report) ##############################

#Returns true if a car is sitting idle at a speficic date        
def idle_car(base_date, data_frame):
    dates_ = data_frame['utc_time'].tolist()
    nearest_date = nearest_previous_date(base_date, dates_)
    nearest_48_h = nearest_previous_2_days(base_date, dates_)
    row_1 = data_frame[data_frame['utc_time'] == nearest_date]
    row_2 = data_frame[data_frame['utc_time'] == nearest_48_h]
    row_1.sort_index(axis=1).sort_index(inplace = True)
    row_2.sort_index(axis=1).sort_index(inplace = True)
    city_1 = row_1['City'].squeeze() #return tha scalar value of the dataframe
    city_2 = row_2['City'].squeeze()
    if (city_1 == city_2):
        return 0
    else: 
        return 1


#range of dates that are appropriate to find out dwell cars
def appropriate_range_for_dwell_analysis(time_period):
    #time_period = range_date(list(df['utc_time']))
    dates_list = [] 
    for i in range(0, (time_period[1] - time_period[0]).days -2):
        d = time_period[1].timestamp() - timedelta(days=i).total_seconds()
        dates_list.append( datetime.fromtimestamp(d) )
    return dates_list
    


#Inputs: Grouped dataframe by AssetIDs, period of time
#returns a dictionary where key is date and value is list of (assetID, idle) for each date
def assets_are_idle_daily_in_a_time_period(input_grouped_df_by_ID, period_of_time):
    assets_results_dict = {}
    for d in period_of_time:
        val_list = []
        for name, group in input_grouped_df_by_ID:
            idle = idle_car(d, input_grouped_df_by_ID.get_group(name))
            val_list.append((name, idle))
        assets_results_dict[d] = val_list
    return assets_results_dict

#count number of idle assets from the input dictionary
#returns a new dictionary where keys are dates and values are number of idle assets
def count_idle_assets_daily_in_a_time_period(assets_results_dict):
    dates_and_idle_cars = {}
    for k, values in assets_results_dict.items():
        count_idles = 0
        for v in values:
            if v[1] == True:
                count_idles = count_idles + 1
        dates_and_idle_cars[k] = count_idles
    return dates_and_idle_cars


############################## (4) ANALYSIS FOR DWELL DURATIONS ##############################
#This function finds out how long (in hours) a car is not moving within 10 kilometers
#at a specific point of time at 8:00 (base_time)
#This only works on grouped data farme in a for loop, not the lambda function
def duration(base_index, cleaned_data_frame):
    idle_dict = {}
    base_lat = cleaned_data_frame.loc[base_index]['Latitude']
    base_lon = cleaned_data_frame.loc[base_index]['Longitude']
    #return new data_frame for the rows where row_index > base_index (times are decending)
    #new_data_frame = data_frame.query('row_index > base_index')
    new_data_frame = cleaned_data_frame[cleaned_data_frame['row_index'] > base_index]
    lats = list(new_data_frame['Latitude'])
    lons = list(new_data_frame['Longitude'])
    coordinates = list(zip (lats, lons))
    coordinates_index = 0
    
    idle_dict[base_index] = cleaned_data_frame.loc[base_index]['utc_time']
    
    for row in new_data_frame.itertuples(index = False):
        if(vincenty((base_lat, base_lon), coordinates[coordinates_index]).km < 10 ):
            idle_dict[row.row_index] = row.utc_time
            coordinates_index = coordinates_index + 1
    #idle_duraiton in seconds
    idle_duration = cleaned_data_frame.loc[base_index]['utc_time'].timestamp()-idle_dict[max(idle_dict)].timestamp()
    # if duration is less than one hour
    if (idle_duration < 3600):
        return 0 
    else: #retun duration in seconds
        return (idle_duration/3600) 


#returns a tuple (row_index and the date of the nearest previous date compared to a specific point of time(baseDate))
#use as a helper function to find out the base_index for duration(base_index, data_frame) function
def nearest_previous_index_and_date(baseDate, cleaned_data_frame):
    dates = list(cleaned_data_frame['utc_time'])
    nearness = {}
    for row in cleaned_data_frame.itertuples(index = False):
        diff = baseDate.timestamp() - row.utc_time.timestamp()
        if(diff >= 0):
            nearness[diff] = (row.row_index, row.utc_time)
    return nearness[min(nearness.keys())] 

#returns a dictionary where key is the AssetID and value is idle duration at the specific input_date
def cars_idle_duration(grouped_input_data_frame, input_date):
    id_idle_duration = {}
    for name, group in grouped_input_data_frame:
        group_index_date_base = nearest_previous_index_and_date(input_date, grouped_input_data_frame.get_group(name))
        id_idle_duration[name] = duration(group_index_date_base[0], grouped_df.get_group(name))
    return id_idle_duration

############################## (5) ANALYSIS FOR CYCLE TIMES ##############################






############################## (6) UI FUNCTIONSS: PARSE INPUT FILES ##############################
#returns the dictionary of the cars that are idle, idle duration is more than 48 hours
def is_idle(cars_dict):
    idle_cars = {}
    for key, val in cars_dict.items():
        if (val > 48):
            idle_cars[key] = val
    return idle_cars
    

# file upload function and clean data, return a dataframe
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')

    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            data_frame = pd.read_csv(
                io.StringIO(decoded.decode('utf-8')))
            ######## This part does not transfer to call backs
            #covert string to date time
            #times = pd.to_datetime(data_frame['Breadcrumb Date UTC'], format= '%Y-%m-%d %H:%M:%S')
            #append the times as utc_time column to the dataframe
            #data_frame.loc[:, "utc_time"] = pd.Series(times , index = data_frame.index)
            
            #slice by required columns
            #required_columns_list = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
            #sliced_data_frame = slice_data_frame_by_required_columns(data_frame, required_columns_list)
            
            #add missing dates for each asset
            #range_dates = range_date(list(sliced_data_frame['utc_time']))
            #grouped_data_frame = sliced_data_frame.groupby('AssetID')
            #new_data_frame = data_frame_by_new_dates_added(grouped_data_frame, range_dates)
            
            #remove duplicate rows
            #set_of_columns = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
            #remove_duplicate_rows(new_data_frame , set_of_columns)
            
            #add row index
            #add_row_index_column(new_data_frame)
            #########
            
        elif 'xls' in filename:
            # Assume that the user uploaded an excel file
            data_frame = pd.read_excel(io.BytesIO(decoded))

    except Exception as e:
        print(e)
        return None

    return data_frame


def generate_table(dataframe, max_rows=10):
    return html.Table(
        # Header
        [html.Tr([html.Th(col) for col in dataframe.columns])] +

        # Body
        [html.Tr([
            html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
        ]) for i in range(min(len(dataframe), max_rows))]
    )

############################## ########################## ##############################
#color codes for the dwell cars on map
scl = [[0, 'rgb(255, 0, 0)'],[1,'rgb(34,139,34)']]


app.layout = html.Div([

    html.H5("Upload Files to Start Analytics"),
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        multiple=False),
    

    html.Br(),
    #html.H5("Updated Table"),
    html.Div(id='table'), #(dte.DataTable(rows=[{}], id='table')),



    html.Div([
        html.H6("Select a date to view the location of the rail-cars"),
        dcc.DatePickerSingle(
            id='date-picker-single',
            date= (datetime.utcnow()).date()
        )
    ]),

    html.Br(),
    html.H5("Daily Location Of Railcars"),
    html.Div(
        dcc.Graph(
            id="mapbox-graph",
            figure = {
                'data': [go.Scattermapbox(
                    lat = 49.258682,
                    lon = -122.766464,
                    mode='markers',
                    marker=Marker(
                        size=14,
                        symbol = 'rail',
                        opacity= 1,
                    ),
                #text = results["AssetID"],
                )],
                'layout': go.Layout(
                    title = 'Daily Railcars Location at 7:59' ,
                    mapbox=dict(
                        accesstoken=mapbox_access_token,
                        bearing=0,
                        center=dict(
                            lat = 49.258682,
                            lon = -122.766464,
                        ),
                        pitch=0,
                        zoom=5,  
                    ),
                    height = 800,
                    width = 1200
                )
            }
        )
    ),

    #mapbox-graph


    html.Br(),
    html.Div([
        html.H3("Dwell Report"),
    ], ),
    

    html.Div([
        
        html.Div([
            html.H6("Start Date"),
            dcc.DatePickerSingle(
                id='start_date',
                date= datetime.utcnow()
            )],
            style={'width': '48%', 'display': 'inline-block'}
        ),

        
        html.Div([
            html.H6("End Date"),
           dcc.DatePickerSingle(
                id='start_date',
                date= datetime.utcnow()
            )],
            style={'width': '48%', 'float': 'right', 'display': 'inline-block'} 
        )

    ]),



    html.Div([
        dcc.Graph(
            id ='idle_cars_stackbar', 
            figure = {
                'data' : [
                    {'x': ['2018-1-1'] , 'y': [10] , 'type': 'bar' , 'color': '(255,51,51)' , 'name': 'Idle cars'},
                    {'x': ['2018-1-1'], 'y': [4], 'type' : 'bar' , 'color': 'rgb(0,155,0)', 'name': 'Not idle'}
                ],
                'layout': {
                    'title' : 'Idle Cars',
                    'barmode' : 'stack'
                }
            }
        )
    ]),


    html.Br(),
    html.Div([
        html.H3("Cycle Time Report"),
    ], 
        #style={'width': '48%', 'float': 'center', 'display': 'inline-block'}
        ),
    
    html.Div([
        dcc.Graph(id ='cars-cycle-time-horizontal-chart')
    ]),

    html.Div([
        dcc.Graph(id ='cities-travel-time-horizontal-chart')
    ]),
])


# Functions


    


# callback table creation
@app.callback(Output('table', 'rows'),
              [Input('upload-data', 'contents'),
               Input('upload-data', 'filename')])
def update_output(contents, filename):
    if contents is not None:
        df = parse_contents(contents, filename)
        if df is not None:
            return df.to_dict('records')
        else:
            return [{}]
    else:
        return [{}]





#call back update of the mapbox
@app.callback(
    dash.dependencies.Output('mapbox-graph', 'figure'),
    [   Input('date-picker-single', 'date'),
        Input('table','rows')])

#def update_graph_daily(daily_dropdown_value, table_rows):
def update_graph_daily(daily_dropdown_value, table_rows):
    
    time_ = datetime.strptime("7:59:59", '%H:%M:%S').time()
    date_ = (datetime.strptime(daily_dropdown_value, '%Y-%m-%d')).date()
    base_time = datetime.combine(date_, time_)
    
        
    #base_time = datetime.datetime.strptime(daily_dropdown_value, '%Y-%m-%d %H:%M')
        
    df_ = pd.DataFrame(table_rows)

    #######
    #times = pd.to_datetime(df_['Breadcrumb Date UTC'], format= '%Y-%m-%d %H:%M:%S')
    
    times = pd.to_datetime(df_['utc_time'], format= '%Y-%m-%d %H:%M:%S')
    #append the times as utc_time column to the dataframe
    df_.loc[:, "utc_time"] = pd.Series(times , index = df_.index)
            
    #slice by required columns
    #required_columns_list = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
    #sliced_data_frame = slice_data_frame_by_required_columns(df_, required_columns_list)
            
    #add missing dates for each asset
    #range_dates = range_date(list(sliced_data_frame['utc_time']))
    #grouped_data_frame = sliced_data_frame.groupby('AssetID')
    #new_data_frame = data_frame_by_new_dates_added(grouped_data_frame, range_dates)
            
    #remove duplicate rows
    #set_of_columns = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
    #remove_duplicate_rows(new_data_frame , set_of_columns)
            
    #add row index
    #add_row_index_column(new_data_frame)
    ########

    #df_["utc_time"] = pd.to_datetime(df_["utc_time"], format="%Y-%m-%d %H:%M:%S")
    #df.index = df["Breadcrumb Date UTC"]
    assets_groups = df_.groupby("AssetID").apply(lambda x: nearest_previous_date(base_time, x['utc_time'])).reset_index(name="utc_time")

    columns=["AssetID", "utc_time"]
    results = assets_groups.join(df_.set_index(columns), on = columns)
        
    results_2 = df_.groupby('AssetID').apply(lambda x: idle_car(base_time, x)).reset_index(name='idle')

    return {
        'data': [go.Scattermapbox(
            lat = results["Latitude"],
            lon = results["Longitude"],
            mode='markers',
            marker=Marker(
                size=14,
                colorscale= scl,
                color = list(results_2['idle']),
                cmin= 0,
                cmax = 1,
                #reversescale= True,
                #symbol = 'rail',
                opacity= 1,
                
                
            ),
            text = results["AssetID"],
        )],
        'layout': go.Layout(
            title = 'Daily Railcars Location at ' + base_time.strftime("%Y-%m-%d %H:%M:%S"),
            mapbox=dict(
                accesstoken=mapbox_access_token,
                bearing=0,
                center=dict(
                    lat= results.iloc[0]["Latitude"],
                    lon= results.iloc[0]["Longitude"]
                ),
            pitch=0,
            zoom=5,  
            ),
            height = 800,
            width = 1200
        )
    }

@app.callback(
    Output('idle_cars_stackbar', 'figure'),
    [Input('table', 'rows')]
)
def update_stackbar(table_rows):
    df_ = pd.DataFrame(table_rows)

    #covert string to date time
    #times = pd.to_datetime(df_['Breadcrumb Date UTC'], format= '%Y-%m-%d %H:%M:%S')
    times = pd.to_datetime(df_['utc_time'], format= '%Y-%m-%d %H:%M:%S')
    #append the times as utc_time column to the dataframe
    df_.loc[:, "utc_time"] = pd.Series(times , index = df_.index)

    df = df_.loc[:,['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude','new_index']]


    new_df = df.drop_duplicates(subset=['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude'])
       
    #slice by required columns
    #required_columns_list = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
    #sliced_data_frame = slice_data_frame_by_required_columns(df_, required_columns_list)
            
    #add missing dates for each asset
    #range_dates = range_date(list(sliced_data_frame['utc_time']))
    #grouped_data_frame = sliced_data_frame.groupby('AssetID')
    #new_data_frame = data_frame_by_new_dates_added(grouped_data_frame, range_dates)
            
    #remove duplicate rows
    #set_of_columns = ['AssetID','utc_time', 'City', 'Province','Country','Latitude','Longitude']
    #remove_duplicate_rows(new_data_frame , set_of_columns)
            
    #add row index
    #new_df = add_row_index_column(new_data_frame)

    #range_date of the df_
    #data_range = range_date(list(new_df['utc_time']))

    #list of dates in the range_date
    #dates_list = appropriate_range_for_dwell_analysis(data_range)
    data_range = range_date(list(new_df['utc_time']))

    dates_list = []
    for i in range(0, (data_range[1] - data_range[0]).days -1):
        d = data_range[1].timestamp() - timedelta(days=i).total_seconds()
        dates_list.append( datetime.fromtimestamp(d) )
    #dates_list.append( (data_range[1] - timedelta(days = i)).date())
    

    grouped_df = new_df.groupby('AssetID')
    

    dates_idle_cars = count_idle_assets_daily_in_a_time_period(assets_are_idle_daily_in_a_time_period(grouped_df, dates_list))

    x_axis_data = []
    y_axis_data_idle = []
    for k, v in dates_idle_cars.items():
        x_axis_data.append(k)
        y_axis_data_idle.append(v)

    y_axis_data_not_idle = []
    for i in y_axis_data_idle:
        y_axis_data_not_idle.append(TOTAL_NUMBER_OF_ASSETS - i)

    return {
        'data' : [go.Bar(
            x = x_axis_data,
            y = y_axis_data_idle,
            name = 'idle Cars',
            marker = Marker(color = 'rgb(255,51,51)') #Darker: (204,0,0)
            ),
            go.Bar(
                x = x_axis_data,
                y = y_axis_data_not_idle,
                name = 'Not idle',
                marker = Marker(color = 'rgb(0,155,0)')
                )], 
            'layout': go.Layout(
                barmode = 'stack', 
                title = 'Idle Cars',
                xaxis = XAxis(
                    title = 'Date - Dec 13/2017 to Jan 16/2018'
                ),
                yaxis = YAxis(
                    title = 'Number'
                )
                )
    }










@app.callback(
    Output('cars-cycle-time-horizontal-chart', 'figure'),
    [Input('table', 'rows')]
)
def update_stackbar(table_rows):
    
    list_of_horizaontal_barchart_columns = ['Clavet', 'Edmonton', 'Port Coquitlam', 'East Hoquiam', 'Clavet to Port Coquitlam', 'Port Coquitlam to Clavet', 'East Hoquiam to Edmonton', 'Port Coquitlam to East Hoquiam', 'Edmonton to Port Coquitlam', 'Clavet to Edmonton']
    traces = {'CGAX9054': [1, 0, 22, 0, 2, 0, 0, 0, 0, 0], 'CGAX9440': [0, 0, 12, 0, 2, 0, 0, 0, 0, 0], 'CGEX1089': [0, 0, 4, 0, 0, 0, 0, 0, 0, 0], 'CGEX1348': [0, 0, 15, 0, 2, 0, 0, 0, 0, 0], 'CGEX1456': [0, 0, 3, 0, 15, 0, 0, 0, 0, 0], 'CGEX1480': [2, 0, 15, 0, 2, 4, 0, 0, 0, 0], 'CGEX1584': [2, 0, 15, 0, 2, 4, 0, 0, 0, 0], 'CGEX1787': [2, 0, 4, 0, 0, 4, 0, 0, 0, 0], 'CGEX1797': [1, 0, 15, 0, 2, 0, 0, 0, 0, 0], 'CGOX5460': [0, 0, 15, 0, 2, 0, 0, 0, 0, 0], 'GATX26893': [9, 1, 0, 1, 0, 0, 9, 6, 2, 2], 'GATX26921': [9, 0, 0, 1, 0, 0, 9, 6, 2, 1], 'GATX35120': [9, 1, 0, 1, 0, 0, 9, 5, 2, 2], 'GATX94155': [8, 5, 0, 2, 0, 0, 0, 8, 2, 2]}

    traces_df = pd.DataFrame.from_dict(traces, orient= 'index')
    traces_df.columns = list_of_horizaontal_barchart_columns
    names = list(traces.keys())

    return {
        'data' : [ go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[0]]),
    name=list_of_horizaontal_barchart_columns[0],
    orientation = 'h',
    width = [0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8],
    marker = dict(
        color = 'rgba(255, 0, 0, 0.6)',
        line = dict(
            color = 'rgba(255, 0, 0, 1.0)',
            width = 1)
    )
    )  ,
            go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[9]]),
    name=list_of_horizaontal_barchart_columns[9],
    orientation = 'h',
    width = [0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5],
    marker = dict(
        color = 'rgba(102, 0, 0, 0.6)',
        line = dict(
            color = 'rgba(102, 0, 0, 1.0)',
            width = 1)
    )
    ),
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[1]]),
    name=list_of_horizaontal_barchart_columns[1],
    orientation = 'h',
    width = [0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8],
    marker = dict(
        color = 'rgba(240, 171, 80, 0.6)',
        line = dict(
            color = 'rgba(240, 171, 0, 1.0)',
            width = 1)
    )
    ),
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[8]]),
    name=list_of_horizaontal_barchart_columns[8],
    orientation = 'h',
    width = [0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5],
    marker = dict(
        color = 'rgba(158, 71, 80, 0.6)',
        line = dict(
            color = 'rgba(158, 71, 80, 1.0)',
            width = 1)
    )
    ),
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[2]]),
    name=list_of_horizaontal_barchart_columns[2],
    orientation = 'h',
    width = [0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8],
    marker = dict(
        color = 'rgba(58, 171, 80, 0.6)',
        line = dict(
            color = 'rgba(58, 171, 80, 1.0)',
            width = 1)
    )
    ),
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[7]]),
    name=list_of_horizaontal_barchart_columns[7],
    orientation = 'h',
    width = [0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5],
    marker = dict(
        color = 'rgba(58, 71, 180, 0.6)',
        line = dict(
            color = 'rgba(58, 71, 180, 1.0)',
            width = 1)
    )
    ),
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[3]]),
    name=list_of_horizaontal_barchart_columns[3],
    orientation = 'h',
    width = [0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8,0.8],
    marker = dict(
        color = 'rgba(204, 0, 204, 0.6)',
        line = dict(
            color = 'rgba(204, 0, 204, 1.0)',
            width = 1)
    )
    ),
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[4]]),
    name=list_of_horizaontal_barchart_columns[4],
    orientation = 'h',
    width = [0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5],
    marker = dict(
        color = 'rgba(58, 101, 80, 0.6)',
        line = dict(
            color = 'rgba(58, 101, 80, 1.0)',
            width = 1)
    )
    ),
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[5]]),
    name=list_of_horizaontal_barchart_columns[5],
    orientation = 'h',
    width = [0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5],
    marker = dict(
        color = 'rgba(58, 171, 0, 0.6)',
        line = dict(
            color = 'rgba(58, 171, 0, 1.0)',
            width = 1)
    )
    ) ,
    go.Bar(
    y=names,
    x=list(traces_df[list_of_horizaontal_barchart_columns[6]]),
    name=list_of_horizaontal_barchart_columns[6],
    orientation = 'h',
    width = [0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5],
    marker = dict(
        color = 'rgba(158, 71, 180, 0.6)',
        line = dict(
            color = 'rgba(158, 71, 180, 1.0)',
            width = 1)
    )
    )

    ], 
            'layout': go.Layout(
                barmode='stack',
                title = 'Cycle Time/Dwell Time of Cars in Days', 
                xaxis = XAxis(title = 'Days' ),
                yaxis = YAxis( dtick = 1 , title = 'Railcars'),
                margin = Margin(l = 280)
            )
    }



@app.callback(
    Output('cities-travel-time-horizontal-chart', 'figure'),
    [Input('table', 'rows')]
)
def update_stackbar(table_rows):
    
    list_of_horizaontal_barchart_columns = ['Clavet', 'Edmonton', 'Port Coquitlam', 'East Hoquiam', 'Clavet to Port Coquitlam', 'Port Coquitlam to Clavet', 'East Hoquiam to Edmonton', 'Port Coquitlam to East Hoquiam', 'Edmonton to Port Coquitlam', 'Clavet to Edmonton']
    traces = {'CGAX9054': [1, 0, 22, 0, 2, 0, 0, 0, 0, 0], 'CGAX9440': [0, 0, 12, 0, 2, 0, 0, 0, 0, 0], 'CGEX1089': [0, 0, 4, 0, 0, 0, 0, 0, 0, 0], 'CGEX1348': [0, 0, 15, 0, 2, 0, 0, 0, 0, 0], 'CGEX1456': [0, 0, 3, 0, 15, 0, 0, 0, 0, 0], 'CGEX1480': [2, 0, 15, 0, 2, 4, 0, 0, 0, 0], 'CGEX1584': [2, 0, 15, 0, 2, 4, 0, 0, 0, 0], 'CGEX1787': [2, 0, 4, 0, 0, 4, 0, 0, 0, 0], 'CGEX1797': [1, 0, 15, 0, 2, 0, 0, 0, 0, 0], 'CGOX5460': [0, 0, 15, 0, 2, 0, 0, 0, 0, 0], 'GATX26893': [9, 1, 0, 1, 0, 0, 9, 6, 2, 2], 'GATX26921': [9, 0, 0, 1, 0, 0, 9, 6, 2, 1], 'GATX35120': [9, 1, 0, 1, 0, 0, 9, 5, 2, 2], 'GATX94155': [8, 5, 0, 2, 0, 0, 0, 8, 2, 2]}

    traces_df = pd.DataFrame.from_dict(traces, orient= 'index')
    traces_df.columns = list_of_horizaontal_barchart_columns
    cars = list(traces.keys())
    names = list_of_horizaontal_barchart_columns
    return {
        'data' : [ go.Bar(
            y=names,
            x=list(traces_df.iloc[0]),  
        name=cars[0],
        orientation = 'h',
        marker = dict(
            color = 'rgba(255, 0, 0, 0.6)',
        line = dict(
            color = 'rgba(255, 0, 0, 1.0)',
            width = 1)
        )
        ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[1]),
        name=cars[1],
        orientation = 'h',
        marker = dict(  
            color = 'rgba(102, 0, 0, 0.6)',
        line = dict(
            color = 'rgba(102, 0, 0, 1.0)',
            width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[2]),
        name=cars[2],
        orientation = 'h',
        marker = dict(
            color = 'rgba(240, 171, 80, 0.6)',
            line = dict(
            color = 'rgba(240, 171, 0, 1.0)',
            width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[3]),
        name=cars[3],
        orientation = 'h',
        marker = dict(
            color = 'rgba(158, 71, 80, 0.6)',
            line = dict(
                color = 'rgba(158, 71, 80, 1.0)',
                width = 1)
         )  
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[4]),
        name=cars[4],
        orientation = 'h',
        marker = dict(
            color = 'rgba(58, 171, 80, 0.6)',
            line = dict(
                color = 'rgba(58, 171, 80, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[5]),
        name=cars[5],
        orientation = 'h',
        marker = dict(
            color = 'rgba(58, 71, 180, 0.6)',
            line = dict(
                color = 'rgba(58, 71, 180, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[6]),
        name=cars[6],
        orientation = 'h',
        marker = dict(
            color = 'rgba(204, 0, 204, 0.6)',
            line = dict(
                color = 'rgba(204, 0, 204, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[7]),
        name=cars[7],
        orientation = 'h',
        marker = dict(
            color = 'rgba(58, 101, 80, 0.6)',
            line = dict(
                color = 'rgba(58, 101, 80, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[8]),
        name=cars[8],
        orientation = 'h',
        marker = dict(
            color = 'rgba(58, 171, 0, 0.6)',
            line = dict(
                color = 'rgba(58, 171, 0, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[9]),
        name=cars[9],
        orientation = 'h',
        marker = dict(
            color = 'rgba(158, 71, 180, 0.6)',
            line = dict(
                color = 'rgba(158, 71, 180, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[10]),
        name=cars[10],
        orientation = 'h',
        marker = dict(
            color = 'rgba(10, 1, 180, 0.6)',
            line = dict(
                color = 'rgba(158, 71, 180, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[11]),
        name=cars[11],
        orientation = 'h',
        marker = dict(
            color = 'rgba(158, 10, 0, 0.6)',
            line = dict(
                color = 'rgba(158, 71, 180, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[12]),
        name=cars[12],
        orientation = 'h',
        marker = dict(
            color = 'rgba(100, 71, 180, 0.6)',
            line = dict(
               color = 'rgba(158, 71, 180, 1.0)',
                width = 1)
        )
    ),
    go.Bar(
        y=names,
        x=list(traces_df.iloc[13]),
        name=cars[13],
        orientation = 'h',
        marker = dict(      
            color = 'rgba(158, 171, 180, 0.6)',
            line = dict(
                color = 'rgba(158, 71, 180, 1.0)',
                width = 1)
        )
    )
    ], 
    'layout': go.Layout(
        barmode='stack',
        title = 'Duration of Travel Time/Dwell Time of Cities in Days',
        xaxis = XAxis(title = 'Days' ),
        yaxis = YAxis( dtick = 1),
        margin = Margin(l = 280)
        )
}







app.css.append_css({
    "external_url": "https://codepen.io/chriddyp/pen/bWLwgP.css"
})

if __name__ == '__main__':
    app.run_server(debug=True)