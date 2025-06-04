import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, ctx
import dash_bootstrap_components as dbc
#import lobith_data_update as lobith
from LMWTimeseries import LMWTimeseries

bckgr_quantiles = {'numeric':[.02, 0.1, .3, .5, .7, .9, .98],
                   'names':['p02', 'p10', 'p30', 'p50', 'p70', 'p90', 'p98'],
                   'colours': ['rgba(255,  0,  0,0.5)',
                               'rgba(255,165,  0,0.5)',
                               'rgba( 28,218, 59,0.5)',
                               'rgba(  0,171,255,0.5)',
                               'rgba(  7, 90,132,0.5)',
                               'rgba(110, 28,218,0.5)'
                              ]
                   }
extra_yrs_colors = ['black', 'blue', 'green']
extra_yrs_dash = ['dot', 'dash', 'dashdot']

def build_graph (LMW_series, LMW_prediction = None, ref_yr = None, extra_years = [], qrange = [0,12000], 
                 stats_period = [1991,2020], window = 5, quantiles = bckgr_quantiles['numeric']):
    """
    """

    if (ref_yr is None):
        date_year = LMW_series.current_year()
    else:
        date_year = ref_yr

    x = pd.date_range(start=f"{date_year}-01-01",end=f"{date_year}-12-31")

    df_stat = LMW_series.calculate_stats(stats_period[0], stats_period[1], quantiles, window)
    dfq = LMW_series.get_data()

    fig = go.Figure()

    fig.add_trace(go.Scatter(x = x, y= df_stat[bckgr_quantiles['names'][0]], mode = 'none', fill= 'tonexty', fillcolor = 'rgba(0,0,0,0)', name = ''))

    for i in range(1,len(bckgr_quantiles['names'])):
        fig.add_trace(go.Scatter(x=x, y= df_stat[bckgr_quantiles['names'][i]], fill = 'tonexty' ,fillcolor = bckgr_quantiles['colours'][i-1],
                      name = bckgr_quantiles['names'][i-1] + ' - ' + bckgr_quantiles['names'][i], mode = 'none'))

    fig.add_trace(go.Scatter(x=x, y=df_stat['min'], mode = 'lines', name = 'minimum', line= dict(color='green', width = 2, dash = 'dot')))

    i=0
    for yr in extra_years:
        Qy = dfq[dfq.index.year == yr]
        i += 1

        if i <= (len(extra_yrs_colors)*len(extra_yrs_dash)):
            line_dict = dict(
                             color=extra_yrs_colors[(i-1) // len(extra_yrs_dash)],
                             dash = extra_yrs_dash[(i-1) % len(extra_yrs_dash)],
                             width = 1
                            )
        else:
            line_dict = dict(
                             color=extra_yrs_colors[-1],
                             dash = extra_yrs_dash[-1],
                             width = 1
                            )
        fig.add_trace(go.Scatter(
                                  x=x, y=Qy,
                                  mode = 'lines', name = yr,
                                  line= line_dict
                                )
                      )


    if not (ref_yr is None):
        fill_series = pd.Series(np.nan, index = pd.date_range(start=f"{ref_yr}-01-01",end=f"{ref_yr}-12-31"))

        Q_refyr = fill_series.copy()
        Q_refyr.update(dfq[dfq.index.year == ref_yr])
        ref_yr_label = str(ref_yr)

        fig.add_trace(go.Scatter(x=x, y=Q_refyr, mode = 'lines', name = ref_yr, line= dict(color='black')))

        if ref_yr == LMW_series.current_year():
            if not (LMW_prediction is None):
                Q_pred = fill_series.copy()
                Q_pred.update(LMW_prediction.get_data())
                fig.add_trace(go.Scatter(x=x, y=Q_pred, mode = 'lines', name = 'verwacht', line= dict(color='grey', dash = 'dash')))
    else:
        ref_yr_label = ''

    fig.update_layout(xaxis_title='datum', yaxis_title='Afvoer [m3/s]')
    fig.update_yaxes(range=qrange)
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))

    return fig

def create_subtitle(stat_range):
    return f'ten opzichte van statistiek {str(stat_range[0])}-{str(stat_range[1])}'

def build_page(LMW_series, LMW_prediction,prefix):
    """
    Build the page with the given LMW_series and prefix.
    """
    return([dbc.Row(html.H2('Afvoer ' + LMW_series.attributes['name'] + ' ' + str(LMW_series.current_year()), id=prefix + 'title')),
            dbc.Row(html.H5(create_subtitle([1991, 2020]), id=prefix + 'subtitle')),
            dbc.Row([
                dbc.Col(dcc.RangeSlider(id=prefix + 'qRange', min=0, max=LMW_series.range_max(),
                                        value=[0, LMW_series.range_max(LMW_series.current_year())],
                                        #step=range_step, 
                                        vertical=True), width=1),
                dbc.Col(dcc.Graph(id=prefix + 'graph', figure=build_graph(LMW_series, LMW_prediction)), width=9),
                dbc.Col([
                    dbc.Row(html.H6("Referentiejaar")),
                    dbc.Row([
                        dcc.Dropdown(id=prefix + 'ref_yr', options=LMW_series.get_data().index.year.unique(),
                                     value=LMW_series.current_year()),
                        html.H6("Extra jaren"),
                        dcc.Dropdown(id=prefix + 'extra_yrs',
                                     options=LMW_series.get_data().index.year.unique(), value=[], multi=True)
                    ])
                ])
            ]),
            dbc.Row([
             dbc.Col([
                      dbc.Label('Statistiek berekenen over'),
                      dcc.RangeSlider(id=prefix + 'stats',
                                      min= min(LMW_series.time_range('years')),
                                      max = max(LMW_series.time_range('years')),
                                      #step = None,
                                      value = list(LMW_series.time_range('climate')),
                                      pushable = 20,
                                      marks = LMW_series.time_range('marks')
                                      #marks={}
                                    )
                      ],
                      width=10
                    ),
            dbc.Col([
                     dbc.FormText("Smoothing window"),
                     dcc.Input(id=prefix + 'sm_window',type="number", min=1, max=10, step=1, value= 5)
                    ])
           ])
    ])

external_stylesheets = [dbc.themes.FLATLY]

app = Dash(__name__, external_stylesheets=external_stylesheets, suppress_callback_exceptions=True)

#Qday, currentyear = read_base_data()

Rijn = LMWTimeseries('lobith.cfg')
Rijn_verw = LMWTimeseries('lobith_verwacht.cfg')
Maas = LMWTimeseries('stpieter.cfg')
Maas_verw = LMWTimeseries('stpieter_verwacht.cfg')

#Rijn.update()
Rijn_verw.update(append=False)
#Maas.update()
Maas_verw.update(append=False)

p1 = build_page(Rijn, Rijn_verw,'r_')
p2 = build_page(Maas, Maas_verw, 'm_')
#p3 = [item for p in [p1,p2] for item in p]

card = dbc.Card(
    [
        dbc.CardHeader(dbc.Tabs(
                        [
                            dbc.Tab(label="Afvoer Rijn", tab_id="r_tab"),
                            dbc.Tab(label="Afvoer Maas", tab_id="m_tab")
                        ],
                        id="tabs", 
                        active_tab="r_tab"
                )),
        dbc.CardBody(html.Div(p1, id='card-content')),
    ],
    style={"width": "100%", "margin-top": "40px"},
)

#app.layout = dbc.Container(p3)
app.layout = dbc.Container(card)
#app.title = 'Afvoer Rijn en Maas'

@app.callback(
    Output(component_id='card-content', component_property='children'),[
    Input(component_id='tabs', component_property='active_tab')
    ]
)
def render_content(tab):
    if tab == 'r_tab':
        return p1
    elif tab == 'm_tab':
        return p2
    else:
        return p1

@app.callback(
    Output(component_id='r_graph', component_property='figure'),[
    Input(component_id='r_ref_yr', component_property='value'),
    Input(component_id='r_extra_yrs', component_property='value'),
    Input(component_id='r_stats', component_property='value'),
    Input(component_id='r_sm_window', component_property='value'),
    Input(component_id='r_qRange', component_property='value')
    ]
)
def r_UpdateGraph(ref_yr,extra_years,stats_range,window,qrange):
    #dfs = calculate_stats(Qday,stats_range[0], stats_range[1], window)
    if ctx.triggered_id == 'r_ref_yr':
         qrange=[0,Rijn.range_max(ref_yr)]
    return build_graph(Rijn,Rijn_verw,ref_yr, extra_years= extra_years,qrange=qrange, stats_period=stats_range,window=window)

@app.callback(
    Output(component_id='r_title', component_property='children'),
    Input(component_id='r_ref_yr', component_property='value'),
)
def r_ChangeTitle(ref_yr):
    if ref_yr is None:
        return 'Afvoer Rijn (Lobith)'
    else:
        return 'Afvoer Rijn (Lobith) ' + str(ref_yr)

@app.callback(
    Output(component_id='r_qRange', component_property='value'),
    Input(component_id='r_ref_yr', component_property='value'),
)
def r_reset_qRange(ref_yr):
    return [0,Rijn.range_max(ref_yr)]

@app.callback(
    Output(component_id='r_subtitle', component_property='children'),
    Input(component_id='r_stats', component_property='value'),
)
def r_ChangeSubtitle(stat_range):
    return create_subtitle(stat_range)


@app.callback(
    Output(component_id='m_graph', component_property='figure'),[
    Input(component_id='m_ref_yr', component_property='value'),
    Input(component_id='m_extra_yrs', component_property='value'),
    Input(component_id='m_stats', component_property='value'),
    Input(component_id='m_sm_window', component_property='value'),
    Input(component_id='m_qRange', component_property='value')
    ]
)
def UpdateGraph(ref_yr,extra_years,stats_range,window,qrange):
    #dfs = calculate_stats(Qday,stats_range[0], stats_range[1], window)
    if ctx.triggered_id == 'm_ref_yr':
         qrange=[0,Maas.range_max(ref_yr)]
    return build_graph(Maas,Maas_verw, ref_yr, extra_years= extra_years,qrange=qrange, stats_period=stats_range,window=window)

@app.callback(
    Output(component_id='m_title', component_property='children'),
    Input(component_id='m_ref_yr', component_property='value'),
)
def ChangeTitle(ref_yr):
    if ref_yr is None:
        return 'Afvoer Maas (St. Pieter)'
    else:
        return 'Afvoer Maas (St. Pieter) ' + str(ref_yr)

@app.callback(
    Output(component_id='m_qRange', component_property='value'),
    Input(component_id='m_ref_yr', component_property='value'),prevent_initial_call=True
)
def reset_qRange(ref_yr):
    return [0,Maas.range_max(ref_yr)]

@app.callback(
    Output(component_id='m_subtitle', component_property='children'),
    Input(component_id='m_stats', component_property='value'),
)
def ChangeSubtitle(stat_range):
    return create_subtitle(stat_range)



if __name__ == '__main__':
    app.run(debug=True)
