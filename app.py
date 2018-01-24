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
import operator
import os

import base64
import io

import plotly.plotly as py
from plotly.graph_objs import *
import plotly.graph_objs as go

app = dash.Dash()

app.scripts.config.serve_locally = True
app.config['suppress_callback_exceptions'] = True

mapbox_access_token = "pk.eyJ1IjoibXlkYXNoYW5hbHlzaXMiLCJhIjoiY2pjcDAzbW91MGdibDMybWlocTVjeGMxNyJ9.VzA-rhWiCG4MsRRaeJfvvw"


#find the previous date before 8:00 AM of a specific date (base_time)
def nearest_previous_date(baseDate, dates):
    nearness = {}
    for date in dates:
        if(baseDate.timestamp() - date.timestamp() >= 0):
            nearness[baseDate.timestamp() - date.timestamp()] = date
    return nearness[min(nearness.keys())]

#find the previous date 48 hours before 8:00 AM of a specific date (base_time)
def nearest_previous_2_days(baseDate, dates):
    #date_ = baseDate.
    nearness = {}
    for date in dates:
        if(baseDate.timestamp() - date.timestamp() > datetime.timedelta(days=2).total_seconds()):
            nearness[baseDate.timestamp() - date.timestamp()] = date
    return nearness[min(nearness.keys())]



#return true if a car is idle at a specific point of time (base_time)
def idle_car(base_date, data_frame):
    dates_ = data_frame['Breadcrumb Date UTC'].tolist()
    nearest_date = nearest_previous_date(base_date, dates_)
    nearest_48_h = nearest_previous_2_days(base_date, dates_)
    row_1 = data_frame[data_frame['Breadcrumb Date UTC'] == nearest_date]
    row_2 = data_frame[data_frame['Breadcrumb Date UTC'] == nearest_48_h]
    row_1.sort_index(axis=1).sort_index(inplace = True)
    row_2.sort_index(axis=1).sort_index(inplace = True)
    city_1 = row_1['City'].squeeze() #return tha scalar value of the dataframe
    city_2 = row_2['City'].squeeze()
    if (city_1 == city_2):
        return 1 # True # it is idle
    else: 
        return 0 # False
    
    
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
        dcc.DatePickerSingle(
            id='date-picker-single',
            date=datetime.datetime(2018, 1, 15)
        )
    ]),

    html.Br(),
    html.H5("Daily Location Of Railcars"),
    html.H6("Idle rail-cars are shown in red"),
    html.Div(dcc.Graph(id="mapbox-graph")),



])


# Functions

# file upload function
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')

    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            df = pd.read_csv(
                io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename:
            # Assume that the user uploaded an excel file
            df = pd.read_excel(io.BytesIO(decoded))

    except Exception as e:
        print(e)
        return None

    return df


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
    [
        #dash.dependencies.Input('daily-dropdown', 'value'),
        Input('date-picker-single', 'date'),
    Input('table','rows')]
)

#def update_graph_daily(daily_dropdown_value, table_rows):
def update_graph_daily(daily_dropdown_value, table_rows):
    
    time_ = datetime.datetime.strptime("7:59", '%H:%M').time()
    date_ = (datetime.datetime.strptime(daily_dropdown_value, '%Y-%m-%d')).date()
    base_time = datetime.datetime.combine(date_, time_)

    today = datetime.datetime.utcnow()
    print("today is .... " + today.strftime("%Y-%m-%d %H:%M:%S"))
    print("daily_value_dropdown is .... " + daily_dropdown_value)
    print("date_ is .... " + date_.strftime("%Y-%m-%d %H:%M:%S"))
    print("base_time is .... " + base_time.strftime("%Y-%m-%d %H:%M:%S"))
    print("time_stamp:")
    
    print(".......................................")
    #dff = df.index.day[df['Year'] == year_value]
    if((today.timestamp() - base_time.timestamp()) < 0 ):
        html.Div([
            "Please choose a valid date ...."
        ])

    else: 
        
        #base_time = datetime.datetime.strptime(daily_dropdown_value, '%Y-%m-%d %H:%M')
        
        df_ = pd.DataFrame(table_rows)
        df_["Breadcrumb Date UTC"] = pd.to_datetime(df_["Breadcrumb Date UTC"], format="%Y-%m-%d %H:%M:%S")
        #df.index = df["Breadcrumb Date UTC"]
        assets_groups = df_.groupby("AssetID").apply(lambda x: nearest_previous_date(base_time, x['Breadcrumb Date UTC'])).reset_index(name="Breadcrumb Date UTC")

        columns=["AssetID", "Breadcrumb Date UTC"]
        results = assets_groups.join(df_.set_index(columns), on = columns)
        
        results_2 = df_.groupby('AssetID').apply(lambda x: idle_car(base_time, x)).reset_index(name='idle')

    return {
        'data': [go.Scattermapbox(
            lat = results["Latitude"],
            lon = results["Longitude"],
            mode='markers',
            marker=Marker(
                #symbol = "rail-metro", #The marker.color and marker.size are only available on circle symbol
                size=14,
                colorscale= scl,
                color = list(results_2['idle']),
                cmin= 0,
                cmax = 1,
                reversescale= True,
                opacity= 1,
                
                
            ),
            text = results["AssetID"],
        )],
        'layout': go.Layout(
            title = 'Daily map location at ' + base_time.strftime("%Y-%m-%d %H:%M:%S"),
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


app.css.append_css({
    "external_url": "https://codepen.io/chriddyp/pen/bWLwgP.css"
})

if __name__ == '__main__':
    app.run_server(debug=True)