import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
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
import lobith_data_update as lobith

#df = lobith.read_and_update_lobith('data/Q_Lobith_all.csv')

file_lob = 'data/Q_Lobith_all.csv'

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

def build_graph (dfq, df_stat, include_currentyr = True, extra_years = []):
    
    x = pd.date_range(start="2022-01-01",end="2022-12-31")

    fig = go.Figure()

    fig.add_trace(go.Scatter(x = x, y= df_stat[bckgr_quantiles['names'][0]], mode = 'none', fill= 'tonexty', fillcolor = 'rgba(0,0,0,0)', name = ''))

    for i in range(1,len(bckgr_quantiles['names'])):
        fig.add_trace(go.Scatter(x=x, y= df_stat[bckgr_quantiles['names'][i]], fill = 'tonexty' ,fillcolor = bckgr_quantiles['colours'][i-1],
                      name = bckgr_quantiles['names'][i-1] + ' - ' + bckgr_quantiles['names'][i], mode = 'none'))

    fig.add_trace(go.Scatter(x=x, y=df_stat['min'], mode = 'lines', name = 'minimum', line= dict(color='green', width = 2, dash = 'dot')))
    
    for yr in extra_years:
        Qy = dfq[dfq.index.year == yr]['QLobith']
        fig.add_trace(go.Scatter(x=x, y=Qy, mode = 'lines', name = currentyear, line= dict(color='black', width = 0.5)))


    if include_currentyr:
        Q_currentyear = dfq[dfq.index.year == currentyear]['QLobith']
        fill_series = pd.Series([np.nan for item in range(len(Q_currentyear), 365)])
        Q_currentyear = pd.concat([Q_currentyear, fill_series])
        fig.add_trace(go.Scatter(x=x, y=Q_currentyear, mode = 'lines', name = currentyear, line= dict(color='black')))

    fig.update_layout(title= 'Afvoer Lobith ' + str(currentyear), xaxis_title='datum', yaxis_title='Afvoer [m3/s]')
    fig.update_yaxes(range=[0,6000])

    return fig

external_stylesheets = [dbc.themes.BOOTSTRAP]

app = Dash(__name__, external_stylesheets=external_stylesheets)

dfs = calculate_stats(Qday,1901, currentyear-1)

fig = build_graph(Qday, dfs)

years = [str(currentyear),'2018', '2003', '1976', '1947', '1921']

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(dcc.Graph(id = 'graph', figure = fig), width=11),
        dbc.Col(dcc.Checklist(id='years' ,options=years, value = [str(currentyear)]))
    ]),
    dbc.Row([
        dcc.RangeSlider(id='stats', min= min(Qday.index.year), max = max(Qday.index.year),step=10, value = [1920,2018]),
        dcc.Dropdown(id='extra_yr',options=Qday.index.year.unique(),value=[],multi=True)
    ])
])

@app.callback(
    Output(component_id='graph', component_property='figure'),
    Input(component_id='extra_yr', component_property='value')
)
def UpdateGraph(extra_years):
    return build_graph(Qday, dfs, extra_years= extra_years)

if __name__ == '__main__':
    app.run_server(debug=True)
