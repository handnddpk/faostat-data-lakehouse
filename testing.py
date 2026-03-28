import faostat
import requests

dataset_code = 'Trade_CropsLivestock'
output_path = './data'

api_url = f"https://bulks-faostat.fao.org/production/{dataset_code}_E_All_Data.zip"
response = requests.get(api_url)
if response.status_code == 200:
    zip_path= f"{output_path}/{dataset_code}.zip"
    with open(zip_path, 'wb') as f:
        f.write(response.content)
        
        