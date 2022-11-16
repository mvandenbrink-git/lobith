import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import requests

date_formatstring = "%Y-%m-%dT%H:%M:%S.000+01:00"
date_formatstring_day = "%Y-%m-%dT00:00:00.000+01:00"

url_data_ophalen = ('https://waterwebservices.rijkswaterstaat.nl/' +
                        'ONLINEWAARNEMINGENSERVICES_DBO/' +
                        'OphalenWaarnemingen')

#locatie_code = { 'X':713748.798641064,'Y':5748949.04523234, 'Code':'LOBH'}
locatie_code = {'Code':'LOBI', 'X':713748.841038993,'Y':5748948.95208459}
grootheid_code = {'Code': 'Q'}
eenheid_code = {'Code' : 'm3/s'}
compartiment_code = {"Code":"OW"}


def jprint(obj):
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)
    
def parse_response (resp):
    # extract a dataframe of observations from the JSON object returned by the API
    # {responsereturncode, error, data {locatie, metadata, data} }
        
    if resp.status_code == 200:
        result = resp.json()
        response = {'has_data' : result['Succesvol']}
        if result['Succesvol']:
            response.update({'message':'Success (status code: 200)'})
        else:
            response.update({'message': result['Foutmelding'] + ' (status code: 200)'})
    else:
        response = {'has_data' : False, 'message': 'Request failed (status code: {})'.format(resp.status_code)}
        data_dict = None
    
    if response['has_data']:
        
        df_loc = pd.DataFrame(result['WaarnemingenLijst'][0]['Locatie'], index = ['waarde']).transpose()
        df_meta = pd.DataFrame(result['WaarnemingenLijst'][0]['AquoMetadata']).transpose()
        
        df_list = []
    
        for d in result['WaarnemingenLijst'][0]['MetingenLijst']:
        
            ts = datetime.strptime(d['Tijdstip'], date_formatstring)
            obs = {'timestamp': ts}
            obs.update(d['Meetwaarde'])
            obs.update(d['WaarnemingMetadata'])
        
            obs_clean =  {}
            for k,v in obs.items():
                if isinstance(v,list):
                    if None in v:
                        vl = ['']
                    else:
                        vl = v
                    obs_clean.update({k:','.join(vl)})
                else:
                    obs_clean.update({k:v})
        
            df_list.append(obs_clean)
        
        df = pd.DataFrame(df_list)
        df = df.sort_values('timestamp').set_index('timestamp')
        
        data_dict = {'locatie': df_loc, 'metadata': df_meta, 'data': df}
    
    return response, data_dict

def read_lobith_file (data_file):
    
    dfq = pd.read_csv(data_file)
    dfq['timestamp'] = pd.to_datetime(dfq['timestamp'], format = "%Y-%m-%d %H:%M:%S")
    dfq = dfq.set_index('timestamp').squeeze()

    result_msg = 'Ingelezen: {} waarden tussen {} en {}'.format(len(dfq),
                                         datetime.strftime(dfq.index[0],'%Y-%m-%d %H:%M:%S'),
                                         datetime.strftime(dfq.index[-1],'%Y-%m-%d %H:%M:%S'))
    return [result_msg, dfq]

def lobith_update(df, start_date, url, data_file):
    
    #start_date = dfq.index[-1].strftime(date_formatstring_day)
    end_date = datetime.now().strftime(date_formatstring)
    #end_date = "2021-02-01T21:40:00.000+01:00"

    request = {"AquoPlusWaarnemingMetadata":
       {"AquoMetadata":{"Compartiment":
           compartiment_code,
            "Eenheid":eenheid_code,
            "Grootheid":grootheid_code}},
        "Locatie":locatie_code,
        "Periode":{"Begindatumtijd":start_date,
                   "Einddatumtijd":end_date}}

    resp = requests.post(url, json=request)

    meta, data = parse_response(resp)

    result_msg = meta['message']
    dfq = None

    if meta['has_data']:
        dfm = data['data']
    
        result_msg = result_msg + 'Ingelezen: {} waarden tussen {} en {}'.format(len(dfm),
                              datetime.strftime(dfm.index[0],'%Y-%m-%d %H:%M:%S'),
                              datetime.strftime(dfm.index[-1],'%Y-%m-%d %H:%M:%S'))
    
        # bestaande reeks aanvullen met nieuwe data
        dfq = pd.concat([df,dfm['Waarde_Numeriek']])

        # dubbele waarden eruit halen
        dfq = dfq[~dfq.index.duplicated(keep='first')]

        # sorteren
        dfq = dfq.sort_index()

        # controleren op ontbrekende waarden 
        dfq[dfq > 20000] = np.nan

        # reeks een naam geven
        dfq.name = "QLobith"

        # opgehaalde data wegschrijven naar bestand
        dfq.to_csv(data_file, na_rep = "nan")
    
    return {'message':result_msg, 'data':dfq}

def read_and_update_lobith(lobith_file):

    # read existing data from disk
    res = read_lobith_file(lobith_file)

    # fetch data frame
    df = res[1]

    # get last day that has date. This will be the start day for the update
    start_date = df.index[-1].strftime(date_formatstring_day)

    res = lobith_update(df, start_date,url_data_ophalen,lobith_file)

    

    if res['data'] is None:
        return res['message']
    else:
        return res['data']
