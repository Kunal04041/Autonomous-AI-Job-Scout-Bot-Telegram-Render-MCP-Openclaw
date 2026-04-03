from composio import ComposioToolSet
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('COMPOSIO_API_KEY')

print(f'Starting Composio with key: {api_key[:10]}...')
try:
    toolset = ComposioToolSet(api_key=api_key)
    entity = toolset.get_entity('default')
    # Initiate whatsapp connection
    connection = entity.initiate_connection('whatsapp')
    print('Connection object:')
    print(connection)
except Exception as e:
    print(f'Error: {e}')
