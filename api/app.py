import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, ctx
import dash_bootstrap_components as dbc

bckgr_quantiles = {'numeric':[.02, 0.1, .3, .5, .7, .9, .98],
                   'names':['q02', 'q10', 'q30', 'q50', 'q70', 'q90', 'q98'],
                   'colours': ['rgba(255,  0,  0,0.5)',
                               'rgba(255,165,  0,0.5)', 
                               'rgba( 28,218, 59,0.5)',
                               'rgba(  0,171,255,0.5)',
                               'rgba(  7, 90,132,0.5)',
                               'rgba(110, 28,218,0.5)'
                              ] 
                   }
#colors = ['red', 'orange', 'green', 'lightblue','darkblue', 'purple']

# data ophalen: oude data inlezen, ophalen nieuwe data en weer wegschrijven in apart script
import api.lobith_data_update as lobith

#df = lobith.read_and_update_lobith('data/Q_Lobith_all.csv')

file_lob = '../data/Q_Lobith_all.csv'

res = lobith.read_lobith_file(file_lob)
df = res[1]

start_date = df.index[-1].strftime(lobith.date_formatstring_day)
res = lobith.lobith_update(df, start_date,lobith.url_data_ophalen,file_lob)
df = res['data']

# reeks aggregeren naar daggemiddelde waarden
Qday = pd.DataFrame(df.resample('D').mean())

# hulpkolom toevoegen met dagen van het jaar
Qday['day'] = Qday.index.strftime("%m-%d")

# alle schrikkeldagen eruit gooien
Qday = Qday[~(Qday['day'] == '02-29')]

currentyear = Qday.index[-1].year

def calculate_stats(df, start_yr, end_yr, smoothing_window = 5):
    
    st_date = str(start_yr) + '-01-01'
    ed_date = str(end_yr) + '-12-31'
    stat_data = df.loc[st_date:ed_date].groupby('day')
    
    #stat_data = df[df.index.year in range(start_yr,end_yr+1)].groupby('day')
    stats = stat_data.quantile(bckgr_quantiles['numeric']).reset_index(level=1)
    stats = stats.rename(columns = {'level_1':'quantiles'})

    stats['stat'] = ['q' + format(int(q * 100),"02d") for q in stats['quantiles']]
    stats = stats.pivot(columns = 'stat', values = 'QLobith')

    stats['min'] = stat_data.min()
    stats['max'] = stat_data.max()

    # Voor een rustiger beeld worden de kwantielen gesmoothed door een zwevend gemiddelde toe te passen.

    # om ook voor de eerste en laatste dagen van het jaar goede waarden te kunnen berekenen, 
    # worden de laatste dagen van december aan het begin van de tabel toegevoegd. Evenzo worden 
    # de eerste dagen van januari aan het eind toegevoegd.
    stats_rolling = pd.concat([stats.tail(smoothing_window), stats, stats.head(smoothing_window)])

    # de daadwerkelijke berekening
    stats_rolling = stats_rolling.rolling(window = smoothing_window, center = True).mean()

    # de extra rijen aan begin en eind van de tabel worden weer verwijderd
    stats_rolling = stats_rolling[smoothing_window:(smoothing_window+365)]

    return stats_rolling

def build_graph (dfq, df_stat, ref_yr = None, extra_years = [], qrange = [0,12000]):
    
    x = pd.date_range(start="2022-01-01",end="2022-12-31")

    fig = go.Figure()

    fig.add_trace(go.Scatter(x = x, y= df_stat[bckgr_quantiles['names'][0]], mode = 'none', fill= 'tonexty', fillcolor = 'rgba(0,0,0,0)', name = ''))

    for i in range(1,len(bckgr_quantiles['names'])):
        fig.add_trace(go.Scatter(x=x, y= df_stat[bckgr_quantiles['names'][i]], fill = 'tonexty' ,fillcolor = bckgr_quantiles['colours'][i-1],
                      name = bckgr_quantiles['names'][i-1] + ' - ' + bckgr_quantiles['names'][i], mode = 'none'))

    fig.add_trace(go.Scatter(x=x, y=df_stat['min'], mode = 'lines', name = 'minimum', line= dict(color='green', width = 2, dash = 'dot')))
    
    for yr in extra_years:
        Qy = dfq[dfq.index.year == yr]['QLobith']
        fig.add_trace(go.Scatter(x=x, y=Qy, mode = 'lines', name = yr, line= dict(color='black', width = 0.5)))


    if not (ref_yr is None):
        Q_refyr = dfq[dfq.index.year == ref_yr]['QLobith']
        ref_yr_label = str(ref_yr)

        if len(Q_refyr) < 365:
            fill_series = pd.Series([np.nan for item in range(len(Q_refyr), 365)])
            Q_refyr = pd.concat([Q_refyr, fill_series])
        fig.add_trace(go.Scatter(x=x, y=Q_refyr, mode = 'lines', name = ref_yr, line= dict(color='black')))
    else:
        ref_yr_label = ''

    fig.update_layout(xaxis_title='datum', yaxis_title='Afvoer [m3/s]')
    fig.update_yaxes(range=qrange)

    return fig

def create_subtitle(stat_range):
    return 'ten opzichte van statistiek {}-{}'.format(str(stat_range[0]), str(stat_range[1])) 

def calculate_rangemax (ref_yr):
    return np.ceil(Qday[Qday.index.year == ref_yr]['QLobith'].max()/1000)*1000

external_stylesheets = [dbc.themes.CERULEAN]

app = Dash(__name__, external_stylesheets=external_stylesheets)

stats_period = [1901,currentyear-1]
dfs = calculate_stats(Qday,stats_period[0], stats_period[1])

fig = build_graph(Qday, dfs, currentyear)

#years = [str(currentyear),'2018', '2003', '1976', '1947', '1921']

app.layout = dbc.Container([
    dbc.Row(html.H2('Afvoer Lobith ' + str(currentyear),id='title')),
    dbc.Row(html.H5(create_subtitle(stats_period), id='subtitle')),
    dbc.Row([
        dbc.Col(dcc.RangeSlider(id='qRange',min = 0, max = 12000, 
                                    value = [0,calculate_rangemax(currentyear)],
                                    step = 1000, vertical = True), width=1),
        dbc.Col(dcc.Graph(id = 'graph', figure = fig), width=9),
        dbc.Col([
            dbc.Row(html.H6("Referentiejaar")),
            dbc.Row([
                dcc.Dropdown(id='ref_yr',options=Qday.index.year.unique(),value=currentyear),
                html.H6("Extra jaren"),
                dcc.Dropdown(id='extra_yrs',options=Qday.index.year.unique(),value=[],multi=True)
            ])

        ])
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Label('Statistiek berekenen over'),
            dcc.RangeSlider(id='stats', 
                            min= 1901, 
                            max = max(Qday.index.year), 
                            value = [1901,currentyear-1],
                            pushable = 10,
                            marks = {1901:'1901',1910:'1910',1920:'1920',1930:'1930',1940:'1940',
                                     1950:'1950',1960:'1960',1970:'1970',1980:'1980',1990:'1990', 
                                     2000:'2000',2010:'2010', currentyear:str(currentyear)}
        )], width=10
    ),
        dbc.Col([
            dbc.FormText("Smoothing window"),
            dcc.Input(id='sm_window',type="number", min=1, max=10, step=1, value= 5)
        ])
    ])
])

@app.callback(
    Output(component_id='graph', component_property='figure'),[
    Input(component_id='ref_yr', component_property='value'),
    Input(component_id='extra_yrs', component_property='value'),
    Input(component_id='stats', component_property='value'),
    Input(component_id='sm_window', component_property='value'),
    Input(component_id='qRange', component_property='value')
    ]  
)
def UpdateGraph(ref_yr,extra_years,stats_range,window,qrange):
    dfs = calculate_stats(Qday,stats_range[0], stats_range[1], window)
    if ctx.triggered_id == 'ref_yr':
         qrange=[0,calculate_rangemax(ref_yr)]
    return build_graph(Qday, dfs, ref_yr, extra_years= extra_years,qrange=qrange)

@app.callback(
    Output(component_id='title', component_property='children'),
    Input(component_id='ref_yr', component_property='value'),
)
def ChangeTitle(ref_yr):
    if ref_yr is None:
        return 'Afvoer Lobith'
    else:
        return 'Afvoer Lobith ' + str(ref_yr)

@app.callback(
    Output(component_id='qRange', component_property='value'),
    Input(component_id='ref_yr', component_property='value'),
)
def reset_qRange(ref_yr):
    return [0,calculate_rangemax(ref_yr)]

@app.callback(
    Output(component_id='subtitle', component_property='children'),
    Input(component_id='stats', component_property='value'),
)
def ChangeSubtitle(stat_range):
    return create_subtitle(stat_range)


if __name__ == '__main__':
    app.run_server(debug=True)
