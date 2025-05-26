import pandas as pd
from numpy import nan
from pathlib import Path
from datetime import datetime
import requests

class LMWTimeseries:
    
    def __init__(self, configfile = None):
        """
        Initialize the LMWTimeseries object.

        """
        self.data = None
        self.date_formatstring = "%Y-%m-%dT%H:%M:%S.000+01:00"
        self.date_formatstring_day = "%Y-%m-%dT00:00:00.000+01:00"

        self.url_data_ophalen = ('https://waterwebservices.rijkswaterstaat.nl/' +
                        'ONLINEWAARNEMINGENSERVICES_DBO/OphalenWaarnemingen')
        
        self.attributes =  self.read_config(configfile) if configfile is not None else {}

    def get_data(self, skip_leap_days = False):
        """ 
        Returns the timeseries data as a pandas Series. 
        If the data is not already loaded, it is read from the specified files in the config file.
        :param skip_leap_days: If True, skip leap days in the data
        :return: DataFrame with the timeseries data
        """
        if self.data is None:
            data_files = []
            if 'static_data_files' in self.attributes:
                data_files = self.attributes['static_data_files'].copy()
            if 'current_data_file' in self.attributes:
                data_files.append(self.attributes['current_data_file'])
            #print(data_files)
            self.data = self.read_data_files(data_files)

        df = self.data.copy()
        if skip_leap_days:
            # hulpkolom toevoegen met dagen van het jaar
            df = df.to_frame()
            df['day'] = df.index.strftime("%m-%d")
            # alle schrikkeldagen eruit gooien
            df = df[~(df['day'] == '02-29')]
            df = df.drop(columns=['day'])
        return df.squeeze()
        
    def read_data_files(self, data_files):
        """
        Read data from the specified files and return a list of data points.

        :param data_files: List of file paths to read data from
        :return: List of data points
        """

        data = pd.DataFrame()

        for data_file in data_files:
            f = Path(data_file)
            if f.is_file():
                dfq = pd.read_csv(data_file)
                dfq['timestamp'] = pd.to_datetime(dfq['timestamp'], format = 'ISO8601')
                dfq = dfq.set_index('timestamp')
                dfq = dfq.resample('D').mean()
                #dfq = dfq.rename(columns = {'QLobith':'Q'})

                data = pd.concat([data,dfq], axis=0).sort_index()
       
        return data.squeeze()

    def update(self, append=True):
        """
        Update the timeseries data by fetching new data from the web service.

        :param append: If True, append the new data to the existing data. If False, overwrite the existing data.
        :return: Metadata and data from the web service
        """

        if append:
            df_current = self.read_data_files([self.attributes['current_data_file']])
        else:
            df_current = pd.DataFrame()
        
        # start_date = laatste datum in de huidige data 
        # end_date = start van vandaag (laaste waarden van de dag ervoor)
        if len(df_current) == 0:
            start_date = (pd.Timestamp.today() - pd.Timedelta(30,'d')).strftime(self.date_formatstring_day)
        else:
            start_date = df_current.index[-1].strftime(self.date_formatstring_day)
        end_date = (pd.Timestamp.today() + pd.Timedelta(7,'d')).strftime(self.date_formatstring_day)

        locatie = {'Code': self.attributes['LMW_loc_code'], 
                   'X': self.attributes['LMW_loc_X'], 
                   'Y': self.attributes['LMW_loc_Y']}
        request = {
            "AquoPlusWaarnemingMetadata": {
                "AquoMetadata": {
                    "Grootheid": {'Code' : self.attributes['LMW_grootheid_code']}
                }
            },
            "Locatie": locatie,
            "Periode": {
                "Begindatumtijd": start_date,
                "Einddatumtijd": end_date
            }
        }

        resp = requests.post(self.url_data_ophalen, json=request)
        meta, data = self.parse_response(resp)

        if meta['has_data']:
            dfm = data['data']['Waarde_Numeriek'].squeeze()

            # controleren op ontbrekende waarden 
            dfm.loc[dfm > 20000] = nan

            dfm = dfm.resample('D').mean()
            dfm = dfm.rename(self.attributes['LMW_grootheid_code'])
            if len(df_current) == 0:
                df_current = dfm
            else:
                df_current= pd.concat([df_current, dfm[:-1]], axis=0).sort_index()

            # dubbele waarden eruit halen
            df_current = df_current[~df_current.index.duplicated(keep='first')]
            df_current.to_csv(self.attributes['current_data_file'], index=True, index_label='timestamp', float_format='%.2f')
        return meta, data['metadata']

    def parse_response (self,resp):
        """
        Extract a dataframe of observations from the JSON object returned by the API
          {responsereturncode, error, data {locatie, metadata, data} }
        """
        
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
        
                ts = datetime.strptime(d['Tijdstip'], self.date_formatstring)
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

        else:
            data_dict = {'locatie': None, 'metadata': None, 'data': None}

        return response, data_dict

    def current_year(self):
        """
        Get the current year from the timeseries data.

        :return: Current year
        """
        df = self.get_data(skip_leap_days=False)
        currentyear = df.index[-1].year
        return currentyear
    
    def range_max(self, ref_yr = None):
        """
        Calculate the maximum range for the timeseries data.

        :param ref_yr: Reference year for the calculation. If not provided, the entire dataset is used.
        :return: Maximum range
        """
        df = self.get_data(skip_leap_days=False)

        if not ref_yr is None:
            # als er een referentiejaar is opgegeven, dan wordt de data van dat jaar gebruikt
            df = df[df.index.year == ref_yr]
        
        return (int(df.max()/1000)+1)*1000
    
    def time_range(self, mode = 'years'):
        """
        Get the time range of the timeseries data.

        :param mode: Mode for the time range:
            'days'    : return  start date and end date
            'years'   : return start year and end year
            'climate' : return the most recent period of 30 years
            'marks'   : return a dict with 5 or 10-year {label:year} intervals, depending on the length of the timeseries
        :return: a tuple or a dict, depending on the mode
        """
        df = self.get_data(skip_leap_days=False)
        num_years = df.index[-1].year - df.index[0].year + 1
        if num_years < 60:
            yr_interval = 5
        else:
            yr_interval = 10

        if mode == 'years':
            return (df.index[0].year, df.index[-1].year)
        elif mode == 'days':
            return (df.index[0], df.index[-1])
        elif mode == 'climate':
            offset = (df.index[-1].year - 1 )% yr_interval
            end = df.index[-1].year - 1 - offset
            return (end - 29, end)
        elif mode == 'marks':
            # de eerste markering is het eerste jaar van de tijdreeks
            marks = {df.index[0].year: str(df.index[0].year)}

            # de start van reeks markeringen is het startjaar van het eerste volledige decennium
            offset = df.index[0].year % yr_interval
            start = df.index[0].year + yr_interval - offset
            
            # de laatste markering is het startjaar van het laatste volledige decennium of het laatste decennium
            offset = df.index[-1].year % yr_interval
            if offset < 4:
                end = df.index[-1].year - offset - yr_interval
            else:
                end = df.index[-1].year - offset 

            for i in range(start, end + 1, yr_interval):
                marks[i] = f'{i}'

            # de laatste markering is het laatste jaar van de tijdreeks
            marks[self.current_year()] = f'{self.current_year()}'
            return marks
        else:
            raise ValueError("Invalid mode. Use 'years', 'days', 'climate', 'marks'.")

    
    def calculate_stats(self,start_yr, end_yr, quantiles,smoothing_window = 5):
        """
        Calculate statistics for the timeseries data.

        :param start_yr: Start year for the statistics
        :param end_yr: End year for the statistics
        :param smoothing_window: Window size for smoothing
        :return: DataFrame with calculated statistics
        """

        df = self.get_data(skip_leap_days=True).to_frame()
        df['day'] = df.index.strftime("%m-%d")
    
        stat_data = df[(df.index.year >=start_yr) & (df.index.year <= end_yr)].groupby('day')
        stats = stat_data.quantile(quantiles).reset_index(level=1)
        stats = stats.rename(columns = {'level_1':'quantiles'})

        stats['stat'] = ['p' + format(int(q * 100),"02d") for q in stats['quantiles']]
        stats = stats.pivot(columns = 'stat', values = self.attributes['LMW_grootheid_code'])

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

    def __repr__(self):
        """
        String representation of the LMWTimeseries object.

        :return: String representation
        """
        return f"LMWTimeseries(data={self.data}, timestamps={self.timestamps})"
    
    def read_config(self,file):
        with open(file, 'r') as f:
            lines = f.readlines()
        config = {}
        for line in lines:
            if line.strip() and not line.startswith('#'):
                key, value = line.split('=')
                config[key.strip()] = value.strip()

        if 'static_data_files' in config:
            config['static_data_files'] = config['static_data_files'].split(',')
        return config

    def write_config(self,file, config):
        with open(file, 'w') as f:
            for key, value in config.items():
                f.write(f"{key} = {value}\n")