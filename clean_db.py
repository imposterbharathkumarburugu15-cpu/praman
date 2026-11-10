import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database URL – fallback to default SQLite used by the app
db_url = os.getenv('DATABASE_URL', 'sqlite:///./data/db.sqlite')
engine = create_engine(db_url, echo=False, future=True)
Session = sessionmaker(bind=engine)

tables = [
    'evidence',
    'audit_log',
    'evidence_duplicate',
    'evidence_forensic',
    'evidence_image',
]

with Session() as session:
    # Disable FK checks if SQLite
    if db_url.startswith('sqlite'):
        session.execute(text('PRAGMA foreign_keys = OFF'))
    for tbl in tables:
        session.execute(text(f'DELETE FROM {tbl}'))
        if db_url.startswith('sqlite'):
            session.execute(text(f'DELETE FROM sqlite_sequence WHERE name="{tbl}"'))
    if db_url.startswith('sqlite'):
        session.execute(text('PRAGMA foreign_keys = ON'))
    session.commit()
print('Database cleaned')

