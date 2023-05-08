import lobith_data_update as lobith
import datetime

file_lob = 'data/Q_Lobith_all.csv'
file_log = 'qlobith_task_log.txt'

res = lobith.read_lobith_file(file_lob)
with open(file_log,'a') as f:
    f.write(f'{datetime.datetime.now()} - read {file_lob}\n')
    f.write(f'    Returned: {res[0]}\n')
df = res[1]

start_date = df.index[-1].strftime(lobith.date_formatstring_day)
res = lobith.lobith_update(df, start_date,lobith.url_data_ophalen,file_lob)
with open(file_log,'a') as f:
    f.write(f'{datetime.datetime.now()} - update {file_lob}\n')
    f.write(f"    Returned: {res['message']}\n")