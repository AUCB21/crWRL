class DB_Config:
    def __init__(
            self
            , db_endpoint: str
            , db_port: int
        ):
        self.db_endpoint = db_endpoint
        self.db_port = db_port

        print(f"[+] Config initialized with DB endpoint: {self.db_endpoint}:{self.db_port}")

    def connect_db(self):
        import os
        import psycopg2

        try:
            connection = psycopg2.connect(
                host=self.db_endpoint,
                port=self.db_port
            )

            db_name = connection.get_dsn_parameters()['dbname']

            print(f"[+] Connected to database {db_name} at {self.db_endpoint}:{self.db_port}")
            return connection
        except Exception as e:
            print(f"[-] Error connecting to database: {e}")
            return None
        
    def close(self):
        if self.connection:
            self.connection.close()
            print(f"[+] Database connection closed.")

class Schema:
    def __init__(self, table_name: str, columns: dict):
        self.table_name = table_name
        self.columns = columns

    def get_schema_string(self) -> str:
        schema_parts = [f"{col} {dtype}" for col, dtype in self.columns.items()]
        return ', '.join(schema_parts)
