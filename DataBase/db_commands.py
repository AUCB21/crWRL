import psycopg2
from config import DB_Config, Schema

class QueryParams:
    def __init__(self, **kwargs):
        self.table = kwargs.get('table', '')
        self.columns = kwargs.get('columns', '')
        self.condition = kwargs.get('condition', '')
        self.schema = kwargs.get('schema', '')

class Query:
    def __init__(self):
        return
    
    def run_query(self, q_type: str, params: QueryParams):
        __q_types = ["SELECT", "INSERT", "DELETE", "UPDATE"]

        switcher = {
            "type": q_type in __q_types
        }
        if not switcher["type"]:
            print("[-] Invalid query type: {}".format(q_type))
            return None
        else:
            if q_type == "SELECT":
                query = f"SELECT {params.columns} FROM {params.schema}.{params.table} WHERE {params.condition if params.condition != '' else '1 = 1'};"
                return query
            elif q_type == "INSERT":
                query = f"INSERT INTO {params.schema}.{params.table} ({params.columns}) VALUES ({params.condition});"
                return query
            elif q_type == "DELETE":
                query = f"DELETE FROM {params.schema}.{params.table} WHERE {params.condition};"
                return query

class Command:
    def __init__(self, db_config: DB_Config):
        self.db_config = db_config
        self.connection = db_config.connect_db()

    def execute_query(self, query: Query):
        if not self.connection:
            print("[-] No paramsbase connection available.")
            return None

        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            print(f"[-] Error executing query: {e}")
            return None
