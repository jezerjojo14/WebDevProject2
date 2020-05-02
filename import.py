import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session,sessionmaker
import csv

engine=create_engine(os.getenv("DATABASE_URL"))
db=scoped_session(sessionmaker(bind=engine))
b=open("books.csv")

reader=csv.reader(b)

if engine.dialect.has_table(engine, "books"):
    db.execute("DROP TABLE books;")
db.execute("CREATE TABLE books (isbn VARCHAR PRIMARY KEY, title VARCHAR, author VARCHAR, year INT);")

firstRow=1

for isbn, title, author, year in reader:
    if firstRow==0:
        db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year);", {'isbn':isbn, 'title':title, 'author':author, 'year':year})
    else: firstRow=0
db.commit()
