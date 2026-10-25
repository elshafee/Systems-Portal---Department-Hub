import os
from sqlalchemy import create_engine, inspect, text
from app import app, db, Document, User, Contact
from models import KeepAlive

def auto_migrate():
    engine = db.engine
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        for model in [Document, User, Contact, KeepAlive]:
            table_name = model.__tablename__
            
            # If table doesn't exist, create it all
            if table_name not in inspector.get_table_names():
                print(f"Creating table {table_name}")
                model.__table__.create(engine)
                continue
                
            # Table exists, check for missing columns
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            
            for column in model.__table__.columns:
                if column.name not in existing_columns:
                    col_type = column.type.compile(dialect=engine.dialect)
                    print(f"Adding column {column.name} ({col_type}) to {table_name}")
                    
                    # Construct ALTER TABLE query
                    # Simple mapping for common defaults, though mostly nullable=True is used
                    query = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"
                    if not column.nullable and column.default is not None:
                        # try to add default if simple
                        if hasattr(column.default.arg, '__call__'):
                            pass # skip complex defaults in SQL
                        elif isinstance(column.default.arg, bool):
                            query += f" DEFAULT {'TRUE' if column.default.arg else 'FALSE'}"
                        elif isinstance(column.default.arg, str):
                            query += f" DEFAULT '{column.default.arg}'"
                    
                    conn.execute(text(query))
                    conn.commit()

if __name__ == "__main__":
    with app.app_context():
        print(f"Migrating database for: {os.environ.get('SYSTEM_OFFICE_CODE', 'Unknown')}")
        auto_migrate()
        print("Done!")
