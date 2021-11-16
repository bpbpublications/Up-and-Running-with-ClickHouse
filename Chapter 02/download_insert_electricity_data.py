import pandas as pd
import os
import time
from clickhouse_driver import Client
from datetime import datetime
import numpy as np
import traceback
import requests

################################################################################
#### change date format
################################################################################

def update_date_format(s):
    
    SList = s.split('/')[::-1]
    NewTs = ('-').join(SList)
    
    return NewTs

################################################################################
#### prepare rows to insert to ClickHouse
################################################################################

def gen_rows_for_insert(Data, TimeStampColumn, DateColumn):

    ColumnNames = [str(x) for x in Data.columns]
    OldRows = Data.values.tolist()
    NewRows = []

    print ('TotalRows', len(OldRows))
    start = time.time()

    for ind, row in enumerate(OldRows):


        row = [None if pd.isnull(x) else x for x in row]

        if TimeStampColumn:

            TSColIndx = Data.columns.get_loc(TimeStampColumn)
            row[TSColIndx] = datetime.strptime(row[TSColIndx], "%Y-%m-%d %H:%M:%S")

        if DateColumn:    

            DateColIndx = Data.columns.get_loc(DateColumn)
            row[DateColIndx] = datetime.strptime(row[DateColIndx], "%Y-%m-%d")

        NewRows.append(tuple(row))

    print ('\nTime taken for generating insert data : ', time.time()-start,'\n')

    return ColumnNames, NewRows

################################################################################
#### Insert to ClickHouse
################################################################################

def push_data(Schema, TableName, Data, TimeStampColumn, DateColumn):

    Data = Data.dropna(axis=1,how='all')
    ColumnNames, Rows = gen_rows_for_insert(Data, TimeStampColumn, DateColumn)

    start = time.time()
    client.execute('INSERT INTO ' + Schema+'.'+TableName+ ' ' + \
                    str(tuple(ColumnNames)).replace("""'""", "") + ' VALUES ', Rows, types_check=True)

    print ('Success - Time Taken : ', time.time()-start)


################################################################################
#### Script
################################################################################

## Download dataset fro source

DatasetUrl = 'https://archive.ics.uci.edu/ml/machine-learning-databases/00235/household_power_consumption.zip'
r = requests.get(DatasetUrl, allow_redirects=True)
open('household_power_consumption.zip', 'wb').write(r.content)

## Read Dataset adn add datetime column

df = pd.read_csv('household_power_consumption.zip', compression='zip', delimiter=';', error_bad_lines=False)
print (df.shape)
df['Date'] = df['Date'].apply(update_date_format)
df['DateTime'] = df['Date']+' '+df['Time']
del df['Time']

## Check column data types

NumericCols = ['Global_active_power','Global_reactive_power',
               'Voltage','Global_intensity','Sub_metering_1',
               'Sub_metering_2','Sub_metering_3']
df = df.replace('?', np.nan)

for Col in NumericCols:
    
    df[Col] = pd.to_numeric(df[Col])
    
print (df.dtypes)

## Split to Chunks of 20 and insert to ClickHouse

Chunks = np.array_split(df, 20)
client = Client(host='localhost', port=9000)

for ind,Chunk in enumerate(Chunks):
    
    try:
        
        push_data('electricity', 'consumption', Chunk, 'DateTime', 'Date')        
        print ('Inserted chunk no ', ind+1, 'out of 20 with shape ', Chunk.shape)
        
    except Exception as e:
        
        print(e)